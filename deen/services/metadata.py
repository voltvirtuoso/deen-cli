"""Fetch prayer calculation metadata from Aladhan API with smart region detection."""
import logging
from typing import Dict, List, Optional, Tuple

from ..cache import Cache, Fetched, get_or_fetch
from ..http import http_get

logger = logging.getLogger("deen.metadata")

# Real Aladhan calculation-method IDs/names (https://aladhan.com/prayer-times-api,
# "method" parameter), bundled as an offline fallback for when the /methods
# endpoint is unreachable and nothing is cached yet. These are static,
# officially documented values -- not invented placeholders -- so unlike the
# previous 5-method stand-in list, this fallback covers the same methods the
# live API would normally return, with the same region metadata used by
# `_detect_region` below.
OFFLINE_METHODS: List[Dict] = [
    {"id": "0", "name": "Shia Ithna-Ashari, Leva Institute, Qum", "region": "☪️ Shia"},
    {"id": "1", "name": "University of Islamic Sciences, Karachi", "region": "🇵🇰 Pakistan"},
    {"id": "2", "name": "Islamic Society of North America (ISNA)", "region": "🇺🇸 North America"},
    {"id": "3", "name": "Muslim World League", "region": "🌍 Global"},
    {"id": "4", "name": "Umm Al-Qura University, Makkah", "region": "🇸🇦 Saudi Arabia"},
    {"id": "5", "name": "Egyptian General Authority of Survey", "region": "🇪🇬 Egypt"},
    {"id": "7", "name": "Institute of Geophysics, University of Tehran", "region": "🇮🇷 Iran"},
    {"id": "8", "name": "Gulf Region", "region": "🇦🇪 Gulf Region"},
    {"id": "9", "name": "Kuwait", "region": "🇰🇼 Kuwait"},
    {"id": "10", "name": "Qatar", "region": "🇶🇦 Qatar"},
    {"id": "11", "name": "Majlis Ugama Islam Singapura, Singapore", "region": "🇸🇬 Singapore"},
    {"id": "12", "name": "Union Organization islamic de France", "region": "🇫🇷 France"},
    {"id": "13", "name": "Diyanet İşleri Başkanlığı, Turkey", "region": "🇹🇷 Turkey"},
    {"id": "14", "name": "Spiritual Administration of Muslims of Russia", "region": "🇷🇺 Russia"},
    {"id": "15", "name": "Moonsighting Committee Worldwide", "region": "🌙 Moonsighting-based"},
    {"id": "17", "name": "Jabatan Kemajuan Islam Malaysia (JAKIM)", "region": "🇲🇾 Malaysia"},
    {"id": "18", "name": "Tunisia", "region": "🇹🇳 Tunisia"},
    {"id": "19", "name": "Algeria", "region": "🇩🇿 Algeria"},
    {"id": "20", "name": "Kementerian Agama Republik Indonesia", "region": "🇮🇩 Indonesia"},
    {"id": "21", "name": "Morocco", "region": "🇲🇦 Morocco"},
    {"id": "23", "name": "Jordan", "region": "🇯🇴 Jordan"},
]


class MetadataService:
    def __init__(self, config: "DeenConfig"):
        self.config = config
        self.base_url = config.get("api.aladhan_base_url", "https://api.aladhan.com/v1")
        self.timeout = config.get("api.timeout_seconds", 10)
        self.max_retries = int(config.get("api.max_retries", 2))
        self.ttl_seconds = float(config.get("cache.metadata_ttl_hours", 168)) * 3600
        self.cache = Cache("metadata", enabled=config.get("cache.enable", True))

    def get_calculation_methods(self, location_hint: str = "") -> Fetched:
        """Fetch calculation methods, using the cache -> live -> stale-cache -> bundled-offline chain.

        ``is_offline`` is True when we fell back to the bundled static list
        rather than anything fetched from the API (live or cached).
        """
        location_lower = location_hint.lower() if location_hint else ""

        fetched = get_or_fetch(
            self.cache, "calculation_methods", self.ttl_seconds, self._fetch_methods_raw
        )
        raw_methods = fetched.data

        if raw_methods is None:
            logger.warning("No live or cached calculation methods; using bundled offline list")
            methods = [dict(m, is_default_for=self._get_default_regions(m["id"])) for m in OFFLINE_METHODS]
            methods = [m for m in methods if m["id"] != "99" or "custom" in location_lower]
            methods.sort(key=lambda x: (
                0 if any(r in location_lower for r in x["is_default_for"]) else 1,
                int(x["id"]) if x["id"].isdigit() else 999,
            ))
            return Fetched(methods, is_offline=True)

        if fetched.is_stale:
            logger.info("Calculation methods served from stale cache")

        methods = []
        for method_key, method_data in raw_methods.items():
            method_id = str(method_data.get("id", method_key))
            method_name = method_data.get("name", f"Method {method_id}")
            region = self._detect_region(method_name, method_id, location_lower)

            if method_id == "99" and "custom" not in location_lower:
                continue

            methods.append({
                "id": method_id,
                "name": method_name,
                "region": region,
                "is_default_for": self._get_default_regions(method_id),
            })

        if not methods:
            return Fetched(None)

        methods.sort(key=lambda x: (
            0 if any(r in location_lower for r in x["is_default_for"]) else 1,
            int(x["id"]) if x["id"].isdigit() else 999,
        ))

        return Fetched(methods, is_stale=fetched.is_stale)

    def _fetch_methods_raw(self) -> Optional[Dict]:
        resp = http_get(f"{self.base_url}/methods", timeout=self.timeout, max_retries=self.max_retries)
        data = resp.json().get("data", {})
        return data or None

    def _detect_region(self, method_name: str, method_id: str, location_hint: str) -> str:
        """Detect region/country from method name."""
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
        """Return location keywords for which this method is the regional standard."""
        defaults = {
            "1": ["pakistan", "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "multan"],
            "2": ["usa", "canada", "america", "united states", "north america"],
            "3": ["europe", "uk", "britain", "germany", "france", "global"],
            "4": ["saudi arabia", "makkah", "mecca", "madinah", "riyadh", "jeddah"],
            "5": ["egypt", "cairo", "alexandria"],
            "99": ["custom", "advanced"],
        }
        return defaults.get(method_id, [])

    def get_schools(self) -> List[Dict]:
        """Madhab/school options (fixed set defined by the Aladhan API's `school` parameter)."""
        return [
            {"id": "0", "name": "Shafi'i, Maliki, Hanbali (Standard)"},
            {"id": "1", "name": "Hanafi"},
        ]

    def get_smart_default_method(self, location: str) -> str:
        """Get smart default method ID based on location."""
        location_lower = location.lower()

        pak_cities = ["islamabad", "karachi", "lahore", "rawalpindi", "faisalabad", "multan", "peshawar", "quetta"]
        if any(city in location_lower for city in pak_cities) or "pakistan" in location_lower:
            return "1"

        sa_cities = ["riyadh", "jeddah", "makkah", "mecca", "madinah", "dammam"]
        if any(city in location_lower for city in sa_cities) or "saudi arabia" in location_lower:
            return "4"

        if "egypt" in location_lower or "cairo" in location_lower:
            return "5"

        na_regions = ["usa", "united states", "canada", "america", "new york", "los angeles", "toronto"]
        if any(region in location_lower for region in na_regions):
            return "2"

        return "3"  # Muslim World League: sane global default

    def get_smart_default_school(self, location: str) -> str:
        """Get smart default madhab based on location."""
        location_lower = location.lower()

        if any(x in location_lower for x in ["pakistan", "india", "bangladesh", "karachi", "lahore", "delhi", "dhaka"]):
            return "1"  # Hanafi

        return "0"  # Shafi'i/Maliki/Hanbali
