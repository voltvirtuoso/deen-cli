"""Fetch prayer calculation metadata from Aladhan API with smart region detection"""
import httpx
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class MetadataService:
    def __init__(self, config: 'DeenConfig'):
        self.config = config
        self.base_url = config.get("api.aladhan_base_url", "https://api.aladhan.com/v1")
        self.timeout = config.get("api.timeout_seconds", 10)
    
    def get_calculation_methods(self, location_hint: str = "") -> Optional[List[Dict]]:
        """
        Fetch calculation methods with smart region detection.
        location_hint: City/country name to set smart defaults (e.g., "Islamabad", "Pakistan")
        """
        try:
            resp = httpx.get(
                f"{self.base_url}/methods",
                headers={"User-Agent": "deen-cli/0.1"},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            methods = []
            location_lower = location_hint.lower() if location_hint else ""
            
            for method_key, method_data in data.get("data", {}).items():
                # ✅ FIXED: Properly access 'name' field with .get() fallback
                method_id = str(method_data.get("id", method_key))
                method_name = method_data.get("name", f"Method {method_id}")
                
                # Smart region detection
                region = self._detect_region(method_name, method_id, location_lower)
                
                # Skip method 99 for regular users
                if method_id == "99" and "custom" not in location_lower:
                    continue
                
                methods.append({
                    "id": method_id,
                    "name": method_name,
                    "region": region,
                    "is_default_for": self._get_default_regions(method_id)
                })
            
            if not methods:
                logger.warning("No methods found in API response")
                return None
            
            # Sort with location-relevant methods first
            methods.sort(key=lambda x: (
                0 if any(r in location_lower for r in x["is_default_for"]) else 1,
                int(x["id"]) if x["id"].isdigit() else 999
            ))
            
            return methods
            
        except Exception as e:
            logger.warning(f"Failed to fetch calculation methods: {e}")
            return None
    
    def _detect_region(self, method_name: str, method_id: str, location_hint: str) -> str:
        """Detect region/country from method name"""
        name_lower = method_name.lower()
        
        if "karachi" in name_lower or "islamic sciences" in name_lower:
            return "🇵🇰 Pakistan"
        if "umm al-qura" in name_lower or "makkah" in name_lower or "mecca" in name_lower:
            return "🇸🇦 Saudi Arabia"
        if "egypt" in name_lower or "cairo" in name_lower:
            return "🇪🇬 Egypt"
        if "isna" in name_lower or "north america" in name_lower:
            return "🇺🇸 North America"
        if "muslim world league" in name_lower or "mwl" in name_lower:
            return "🌍 Global"
        if "tehran" in name_lower or "iran" in name_lower:
            return "🇮🇷 Iran"
        if "gulf" in name_lower:
            return "🇦🇪 Gulf Region"
        if "kuwait" in name_lower:
            return "🇰🇼 Kuwait"
        if "qatar" in name_lower:
            return "🇶🇦 Qatar"
        if "singapore" in name_lower:
            return "🇸🇬 Singapore"
        if "france" in name_lower:
            return "🇫🇷 France"
        if "turkey" in name_lower:
            return "🇹🇷 Turkey"
        if "russia" in name_lower:
            return "🇷🇺 Russia"
        if "moonsighting" in name_lower:
            return "🌙 Moonsighting-based"
        if "dubai" in name_lower:
            return "🇦🇪 UAE (Dubai)"
        if "jakim" in name_lower or "malaysia" in name_lower:
            return "🇲🇾 Malaysia"
        if "tunisia" in name_lower:
            return "🇹🇳 Tunisia"
        if "algeria" in name_lower:
            return "🇩🇿 Algeria"
        if "indonesia" in name_lower:
            return "🇮🇩 Indonesia"
        if "morocco" in name_lower:
            return "🇲🇦 Morocco"
        if "jordan" in name_lower:
            return "🇯🇴 Jordan"
        if "shia" in name_lower or "ithna-ashari" in name_lower:
            return "☪️ Shia"
        if method_id == "99":
            return "⚙️ Custom Parameters"
        
        return "🌍 Global"
    
    def _get_default_regions(self, method_id: str) -> List[str]:
        """Return regions where this method is standard"""
        defaults = {
            "1": ["pakistan", "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan"],
            "2": ["usa", "canada", "america", "united states", "north america"],
            "3": ["europe", "uk", "britain", "germany", "france", "global"],
            "4": ["saudi arabia", "makkah", "mecca", "madinah", "riyadh", "jeddah"],
            "5": ["egypt", "cairo", "alexandria"],
            "99": ["custom", "advanced"]
        }
        return defaults.get(method_id, [])
    
    def get_schools(self) -> List[Dict]:
        """Fetch madhab/school options"""
        return [
            {"id": "0", "name": "Shafi'i, Maliki, Hanbali (Standard)"},
            {"id": "1", "name": "Hanafi"}
        ]
    
    def get_smart_default_method(self, location: str) -> str:
        """Get smart default method ID based on location"""
        location_lower = location.lower()
        
        # Pakistan cities → Method 1 (Karachi)
        pak_cities = ["islamabad", "karachi", "lahore", "rawalpindi", "faisalabad", "multan", "peshawar", "quetta"]
        if any(city in location_lower for city in pak_cities) or "pakistan" in location_lower:
            return "1"
        
        # Saudi Arabia → Method 4 (Umm Al-Qura)
        sa_cities = ["riyadh", "jeddah", "makkah", "mecca", "madinah", "dammam"]
        if any(city in location_lower for city in sa_cities) or "saudi arabia" in location_lower:
            return "4"
        
        # Egypt → Method 5
        if "egypt" in location_lower or "cairo" in location_lower:
            return "5"
        
        # North America → Method 2 (ISNA)
        na_regions = ["usa", "united states", "canada", "america", "new york", "los angeles", "toronto"]
        if any(region in location_lower for region in na_regions):
            return "2"
        
        # Default: MWL (Method 3) for global users
        return "3"
    
    def get_smart_default_school(self, location: str) -> str:
        """Get smart default madhab based on location"""
        location_lower = location.lower()
        
        # Pakistan/India/Bangladesh → Hanafi (majority)
        if any(x in location_lower for x in ["pakistan", "india", "bangladesh", "karachi", "lahore", "delhi", "dhaka"]):
            return "1"  # Hanafi
        
        # Default: Shafi'i/Maliki/Hanbali (Method 0)
        return "0"