"""Configuration management with industry-standard practices."""
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import tomli_w
from platformdirs import user_log_dir

try:
    import tomllib as tomli  # Python 3.11+: stdlib, read-only
except ModuleNotFoundError:
    import tomli  # Python <3.11: backport package (declared in pyproject.toml)

logger = logging.getLogger("deen.config")

# Guard against re-configuring the root logger every time DeenConfig() is
# instantiated (it's constructed at the top of nearly every CLI command).
# Without this, each new instance added another FileHandler/StreamHandler,
# so log lines and stdout output would duplicate N times per process.
_LOGGING_CONFIGURED = False


class DeenConfig:
    def __init__(self):
        # User data (config + local sqlite db) stays under ~/.deen for
        # backwards compatibility with existing installs. Transient/
        # re-fetchable data (HTTP cache) lives in the OS cache dir instead
        # -- see deen/cache.py.
        self.config_dir = Path.home() / ".deen"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / "config.toml"

        # OS-aware log directory (Linux: XDG state/cache dir, macOS:
        # ~/Library/Logs, Windows: %LOCALAPPDATA%). Falls back to the
        # legacy ~/.deen/logs location if it can't be created (e.g. no
        # write permission), so logging never blocks the CLI from running.
        try:
            self.logs_dir = Path(user_log_dir("deen-cli", "deen-cli"))
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.logs_dir = self.config_dir / "logs"
            self.logs_dir.mkdir(exist_ok=True)

        self._config = self._load_or_create()
        self._setup_logging()

    def _load_or_create(self) -> Dict[str, Any]:
        """Load config or create with defaults (TOML-safe - no None values)."""
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                loaded = tomli.load(f)
            # Backfill any new default keys added in later versions without
            # clobbering the user's existing settings.
            merged = self._merge_defaults(loaded)
            # Auto-upgrade any endpoint saved with http:// (e.g. from an
            # install predating this fix) to https://. Living with a stale
            # http:// URL means every request eats a 301 redirect -- and
            # since httpx doesn't follow redirects by default, that used to
            # fail outright and silently fall back to cached/stale content
            # instead of fetching anything fresh.
            if self._upgrade_insecure_urls(merged):
                logger.info("Upgraded one or more api.*_url settings from http:// to https://")
                with open(self.config_path, "wb") as f:
                    tomli_w.dump(merged, f)
            return merged

        default_config = self._default_config()
        with open(self.config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        return default_config

    @staticmethod
    def _upgrade_insecure_urls(cfg: Dict[str, Any]) -> bool:
        """In-place upgrade any api.*_url value from http:// to https://. Returns True if changed."""
        changed = False
        api_section = cfg.get("api")
        if not isinstance(api_section, dict):
            return False
        for key, value in list(api_section.items()):
            if key.endswith("_url") and isinstance(value, str) and value.startswith("http://"):
                api_section[key] = "https://" + value[len("http://"):]
                changed = True
        return changed

    def _default_config(self) -> Dict[str, Any]:
        return {
            "user": {
                "name": "",
                "location": "",
                "created_at": datetime.now().isoformat(),
                # latitude/longitude omitted until set during init
            },
            "prayer": {
                # calculation_method and school omitted until set during init
                "midnight_mode": "0",
                "latitude_adjustment": "1",
            },
            "api": {
                "quran_base_url": "https://api.alquran.cloud/v1",
                "hadith_base_url": "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions",
                "aladhan_base_url": "https://api.aladhan.com/v1",
                "nominatim_base_url": "https://nominatim.openstreetmap.org",
                "dua_base_url": "https://api.islamic.app/v1/dhikr",
                # alquran.cloud edition identifiers used for the ayah
                # endpoint. Configurable so users can pick a different
                # translation without a code change.
                "quran_edition_arabic": "quran-uthmani",
                "quran_edition_translation": "en.sahih",
                "quran_edition_transliteration": "en.transliteration",
                "timeout_seconds": 10,
                "max_retries": 2,
            },
            "cache": {
                "enable": True,
                "ayah_ttl_hours": 24,
                "hadith_ttl_hours": 720,  # 30 days
                "dua_ttl_hours": 720,  # 30 days (category listings; /random is never cached)
                "surah_ttl_hours": 720,  # 30 days (Quran text never changes)
                "metadata_ttl_hours": 168,  # 7 days
                "prayer_times_ttl_hours": 12,
                "location_ttl_hours": 24,
            },
            "logging": {
                "level": "INFO",
                "console": False,
                "max_bytes": 1_000_000,
                "backup_count": 3,
            },
        }

    def _merge_defaults(self, loaded: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively fill in any keys missing from an existing config file."""
        defaults = self._default_config()

        def merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
            for k, v in src.items():
                if k not in dst:
                    dst[k] = v
                elif isinstance(v, dict) and isinstance(dst.get(k), dict):
                    merge(dst[k], v)
            return dst

        return merge(loaded, defaults)

    def _setup_logging(self):
        """Configure logging once per process (idempotent across instances)."""
        global _LOGGING_CONFIGURED
        if _LOGGING_CONFIGURED:
            return

        log_level = str(self.get("logging.level", "INFO")).upper()
        log_file = self.logs_dir / "deen.log"
        max_bytes = int(self.get("logging.max_bytes", 1_000_000))
        backup_count = int(self.get("logging.backup_count", 3))

        handlers = []
        try:
            handlers.append(
                logging.handlers.RotatingFileHandler(
                    log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
                )
            )
        except OSError:
            # If we truly can't write logs anywhere, fall back to console
            # only rather than crashing the whole CLI over logging.
            pass

        if self.get("logging.console", False):
            handlers.append(logging.StreamHandler())

        if not handlers:
            handlers.append(logging.NullHandler())

        root = logging.getLogger()
        root.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        for h in handlers:
            h.setFormatter(formatter)
            root.addHandler(h)

        _LOGGING_CONFIGURED = True

    def get(self, path: str, default=None):
        """Get config value using dot notation."""
        keys = path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, path: str, value):
        """Set config value using dot notation (ensures TOML-safe types)."""
        keys = path.split(".")
        target = self._config
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        if value is None:
            return  # TOML doesn't support null; skip rather than write garbage
        elif isinstance(value, (float, bool, int)):
            target[keys[-1]] = value
        else:
            target[keys[-1]] = str(value)

        self._save()

    def _save(self):
        """Persist config to disk."""
        with open(self.config_path, "wb") as f:
            tomli_w.dump(self._config, f)

    @property
    def is_initialized(self) -> bool:
        """Check if user has completed initialization."""
        return bool(
            self.get("user.name")
            and self.get("user.location")
            and self.get("prayer.calculation_method") is not None
            and self.get("prayer.school") is not None
        )
