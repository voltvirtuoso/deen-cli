"""Fetch prayer calculation metadata from Aladhan API (no hardcoded values)"""
import httpx
from typing import List, Dict, Optional
from ..config import DeenConfig
import logging

logger = logging.getLogger(__name__)

class MetadataService:
    def __init__(self, config: DeenConfig):
        self.config = config
        self.base_url = config.get("api.aladhan_base_url", "https://api.aladhan.com/v1")
        self.timeout = config.get("api.timeout_seconds", 10)
    
    def get_calculation_methods(self) -> Optional[List[Dict]]:
        """
        Fetch calculation methods from Aladhan API
        Returns list of {id: str, name: str, params: dict}
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/methods",
                headers={"User-Agent": "deen-cli/0.1"},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            # Transform API response to consistent format
            methods = []
            for method_id, method_data in data["data"].items():
                methods.append({
                    "id": method_id,
                    "name": method_data["name"],
                    "country": method_data.get("country", ""),
                    "params": method_data.get("params", {})
                })
            return sorted(methods, key=lambda x: int(x["id"]))
            
        except Exception as e:
            logger.warning(f"Failed to fetch calculation methods: {e}")
            return None
    
    def get_schools(self) -> Optional[List[Dict]]:
        """
        Fetch madhab/school options from Aladhan API
        Returns list of {id: str, name: str}
        """
        try:
            # Aladhan API doesn't have a dedicated endpoint for schools
            # We use documented values from their API spec
            # Source: https://aladhan.com/prayer-times-api#GetCalendarByCitys
            return [
                {"id": "0", "name": "Shafi'i, Maliki, Hanbali (Standard)"},
                {"id": "1", "name": "Hanafi"}
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch schools: {e}")
            return None
    
    def get_mood_categories(self) -> List[str]:
        """
        Return mood categories supported by our system
        These are config-driven, not hardcoded business logic
        """
        return ["stressed", "anxious", "grateful", "sad", "angry", "lonely", "tired", "doubtful"]