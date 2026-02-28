"""Configuration management with industry-standard practices"""
from pathlib import Path
from typing import Dict, Any
import tomli
import tomli_w
from datetime import datetime
import logging

class DeenConfig:
    def __init__(self):
        self.config_dir = Path.home() / ".deen"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / "config.toml"
        self.cache_dir = self.config_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.logs_dir = self.config_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        self._config = self._load_or_create()
        self._setup_logging()
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load config or create with defaults (TOML-safe - no None values)"""
        if self.config_path.exists():
            with open(self.config_path, "rb") as f:
                return tomli.load(f)
        
        # Minimal default config - NO None values (TOML doesn't support null)
        default_config = {
            "user": {
                "name": "",
                "location": "",
                "created_at": datetime.now().isoformat()
                # latitude/longitude omitted until set during init
            },
            "prayer": {
                # calculation_method and school omitted until set during init
                "midnight_mode": "0",
                "latitude_adjustment": "1"
            },
            "api": {
                "quran_base_url": "http://api.alquran.cloud/v1",
                "hadith_base_url": "https://hadithapi.pages.dev/api",
                "aladhan_base_url": "https://api.aladhan.com/v1",
                "nominatim_base_url": "https://nominatim.openstreetmap.org",
                "translation_id": 20,
                "timeout_seconds": 10
            },
            "cache": {
                "ayah_ttl_days": 1,
                "hadith_ttl_days": 30,
                "metadata_ttl_hours": 168,
                "enable": True
            },
            "logging": {
                "level": "INFO",
                "file": str(self.logs_dir / "deen.log"),
                "console": True
            }
        }
        
        with open(self.config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        
        return default_config
    
    def _setup_logging(self):
        """Setup logging based on config"""
        log_level = self.get("logging.level", "INFO")
        log_file = self.get("logging.file", str(self.logs_dir / "deen.log"))
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler() if self.get("logging.console", True) else logging.NullHandler()
            ]
        )
    
    def get(self, path: str, default=None):
        """Get config value using dot notation"""
        keys = path.split(".")
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, path: str, value):
        """Set config value using dot notation (ensures TOML-safe types)"""
        keys = path.split(".")
        target = self._config
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Convert to TOML-safe type
        if value is None:
            return  # Skip None values (TOML doesn't support null)
        elif isinstance(value, float):
            target[keys[-1]] = value
        elif isinstance(value, bool):
            target[keys[-1]] = value
        else:
            target[keys[-1]] = str(value)
        
        self._save()
    
    def _save(self):
        """Persist config to disk"""
        with open(self.config_path, "wb") as f:
            tomli_w.dump(self._config, f)
    
    @property
    def is_initialized(self) -> bool:
        """Check if user has completed initialization"""
        return bool(
            self.get("user.name") and 
            self.get("user.location") and
            self.get("prayer.calculation_method") is not None and
            self.get("prayer.school") is not None
        )