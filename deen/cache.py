"""OS-aware, TTL-based JSON caching layer.

Uses `platformdirs` to resolve the correct cache directory for the current
operating system:

- Linux:   ``$XDG_CACHE_HOME/deen-cli`` (usually ``~/.cache/deen-cli``)
- macOS:   ``~/Library/Caches/deen-cli``
- Windows: ``%LOCALAPPDATA%\\deen-cli\\Cache``

This keeps deen-cli's transient/re-fetchable data (API responses) separate
from user data (``~/.deen/data.db``, ``~/.deen/config.toml``), and follows
each platform's own conventions instead of dumping everything under a single
hardcoded ``~/.deen`` folder.

The cache implements a get -> live-fetch -> stale-cache fallback chain via
``get_or_fetch``, so callers get graceful degradation (with clear logging)
instead of ad-hoc hardcoded fallback values scattered through the codebase.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional, TypeVar

from platformdirs import user_cache_dir

logger = logging.getLogger("deen.cache")

APP_NAME = "deen-cli"
APP_AUTHOR = "deen-cli"

T = TypeVar("T")


class Fetched(NamedTuple):
    """The one result type every fetch in deen-cli returns.

    ``data`` is None when nothing could be obtained at all.
    ``is_stale``: served from an *expired* cache entry because the live
    fetch failed -- callers should tell the user it may be outdated.
    ``is_offline``: served from bundled/offline data because neither the
    live API nor any cache had anything.
    """

    data: Any = None
    is_stale: bool = False
    is_offline: bool = False

    @property
    def ok(self) -> bool:
        return self.data is not None


def get_cache_dir() -> Path:
    """Resolve the OS-appropriate cache directory, creating it if needed."""
    cache_dir = Path(user_cache_dir(APP_NAME, APP_AUTHOR))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


class Cache:
    """Simple namespaced JSON file cache with TTL support and stale reads."""

    def __init__(self, namespace: str = "default", enabled: bool = True):
        self.enabled = enabled
        self.dir = get_cache_dir() / namespace
        if self.enabled:
            try:
                self.dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create cache dir {self.dir}: {e}")
                self.enabled = False

    def _path_for(self, key: str) -> Path:
        safe_key = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.dir / f"{safe_key}.json"

    def _read(self, key: str) -> Optional[dict]:
        path = self._path_for(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"Cache read failed for '{key}': {e}")
            return None

    def get(self, key: str, ttl_seconds: Optional[float] = None) -> Optional[Any]:
        """Return the cached value if present and within ttl_seconds (None = never expires)."""
        if not self.enabled:
            return None
        payload = self._read(key)
        if payload is None:
            return None
        cached_at = payload.get("cached_at", 0)
        if ttl_seconds is not None and (time.time() - cached_at) > ttl_seconds:
            return None
        return payload.get("value")

    def get_stale(self, key: str) -> Optional[Any]:
        """Return the cached value regardless of age (last-resort fallback)."""
        if not self.enabled:
            return None
        payload = self._read(key)
        return payload.get("value") if payload else None

    def age_seconds(self, key: str) -> Optional[float]:
        payload = self._read(key)
        if payload is None:
            return None
        return time.time() - payload.get("cached_at", 0)

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        path = self._path_for(key)
        try:
            tmp_path = path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"cached_at": time.time(), "value": value}, f)
            tmp_path.replace(path)
        except OSError as e:
            logger.debug(f"Cache write failed for '{key}': {e}")

    def clear(self) -> int:
        """Delete all entries in this namespace. Returns count removed."""
        if not self.dir.exists():
            return 0
        removed = 0
        for f in self.dir.glob("*.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        return removed


def get_or_fetch(
    cache: Cache,
    key: str,
    ttl_seconds: float,
    fetch_fn: Callable[[], Optional[T]],
    allow_stale_on_error: bool = True,
) -> Fetched:
    """Cache-first strategy: fresh cache -> live fetch -> stale cache.

    Use this for static content (collections, listings, prayer times) where
    a cached copy within its TTL is as good as a live one.
    """
    fresh = cache.get(key, ttl_seconds)
    if fresh is not None:
        logger.debug(f"Cache hit for '{key}'")
        return Fetched(fresh)

    try:
        result = fetch_fn()
    except Exception as e:
        logger.warning(f"Live fetch failed for '{key}': {e}")
        result = None

    if result is not None:
        cache.set(key, result)
        logger.debug(f"Cache refreshed for '{key}'")
        return Fetched(result)

    if allow_stale_on_error:
        stale = cache.get_stale(key)
        if stale is not None:
            age = cache.age_seconds(key)
            age_desc = f"{age / 3600:.1f}h old" if age is not None else "unknown age"
            logger.warning(f"Live fetch for '{key}' failed; using stale cache ({age_desc})")
            return Fetched(stale, is_stale=True)

    logger.warning(f"No live or cached data available for '{key}'")
    return Fetched(None)


def fetch_live_first(
    cache: Cache,
    key: str,
    fetch_fn: Callable[[], Optional[T]],
) -> Fetched:
    """Live-first strategy: live fetch -> last known good value.

    Use this for endpoints that are *meant* to return something different on
    every call (random ayah / random dua). A TTL cache would defeat the
    randomness, so we always try live and only remember the last success as
    a fallback for when the network is down.
    """
    try:
        result = fetch_fn()
    except Exception as e:
        logger.warning(f"Live fetch failed for '{key}': {e}")
        result = None

    if result is not None:
        cache.set(key, result)
        return Fetched(result)

    stale = cache.get_stale(key)
    if stale is not None:
        logger.info(f"Serving last known-good value for '{key}' (live fetch failed)")
        return Fetched(stale, is_stale=True)

    return Fetched(None)
