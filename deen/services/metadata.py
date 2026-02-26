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
        Returns list of {id: str, name: str, country: str}
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/methods",
                headers={"User-Agent": "deen-cli/0.1"},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            # DEBUG: Log actual response structure
            logger.debug(f"Aladhan methods response keys: {list(data.keys())}")
            if "data" in data:
                logger.debug(f"Methods data keys: {list(data['data'].keys())[:3]}")
            
            # CORRECT PARSING: Aladhan API returns methods under data.{id} where id is string key
            methods = []
            for method_key, method_data in data.get("data", {}).items():
                # Handle both string and numeric IDs
                method_id = str(method_data.get("id", method_key))
                method_name = method_data.get("name", f"Method {method_id}")
                
                # Extract country/region hint from name if available
                country = ""
                if "karachi" in method_name.lower() or "pakistan" in method_name.lower():
                    country = "Pakistan"
                elif "saudi" in method_name.lower() or "makkah" in method_name.lower():
                    country = "Saudi Arabia"
                elif "egypt" in method_name.lower():
                    country = "Egypt"
                elif "north america" in method_name.lower() or "isna" in method_name.lower():
                    country = "North America"
                elif "world league" in method_name.lower() or "mwl" in method_name.lower():
                    country = "Global"
                
                methods.append({
                    "id": method_id,
                    "name": method_name,
                    "country": country,
                    "params": method_data.get("params", {})
                })
            
            if not methods:
                logger.warning("No methods found in API response")
                return None
            
            # Sort by numeric ID
            methods.sort(key=lambda x: int(x["id"]) if x["id"].isdigit() else 999)
            return methods
            
        except Exception as e:
            logger.warning(f"Failed to fetch calculation methods: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def get_schools(self) -> Optional[List[Dict]]:
        """
        Fetch madhab/school options
        Returns list of {id: str, name: str}
        """
        # Aladhan API doesn't have a dedicated endpoint for schools
        # Using documented values from their API spec
        return [
            {"id": "0", "name": "Shafi'i, Maliki, Hanbali (Standard)"},
            {"id": "1", "name": "Hanafi"}
        ]
    
    def get_mood_categories(self) -> List[str]:
        """Return supported mood categories"""
        return ["stressed", "anxious", "grateful", "sad", "angry", "lonely", "tired", "doubtful"]