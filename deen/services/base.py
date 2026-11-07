"""Shared plumbing for every API-backed service: config, TTLs, caches, HTTP."""
from __future__ import annotations

import httpx

from ..cache import Cache
from ..config import DeenConfig
from ..http import http_get


class BaseService:
    def __init__(self, config: DeenConfig):
        self.config = config
        self.timeout = config.get("api.timeout_seconds", 10)
        self.max_retries = int(config.get("api.max_retries", 2))
        cache_enabled = config.get("cache.enable", True)

        def hours(key: str, default: float) -> float:
            return float(config.get(f"cache.{key}", default)) * 3600

        self.ayah_ttl = hours("ayah_ttl_hours", 24)
        self.hadith_ttl = hours("hadith_ttl_hours", 720)
        self.dua_ttl = hours("dua_ttl_hours", 720)
        self.surah_ttl = hours("surah_ttl_hours", 720)
        self.prayer_ttl = hours("prayer_times_ttl_hours", 12)

        self._ayah_cache = Cache("ayah", enabled=cache_enabled)
        self._hadith_cache = Cache("hadith", enabled=cache_enabled)
        self._dua_cache = Cache("dua", enabled=cache_enabled)
        self._prayer_cache = Cache("prayer_times", enabled=cache_enabled)
        self._misc_cache = Cache("misc", enabled=cache_enabled)

    def _get(self, url: str, **kwargs) -> httpx.Response:
        return http_get(url, timeout=self.timeout, max_retries=self.max_retries, **kwargs)
