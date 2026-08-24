"""Location auto-detection with multi-provider fallback (no single point of failure)."""
import logging
from typing import Optional, Tuple

import httpx

from ..cache import Cache, get_or_fetch

logger = logging.getLogger("deen.location")


class LocationService:
    def __init__(self, config: "DeenConfig"):
        self.config = config
        self.base_url = config.get("api.nominatim_base_url", "https://nominatim.openstreetmap.org")
        self.ttl_seconds = float(config.get("cache.location_ttl_hours", 24)) * 3600
        self.cache = Cache("location", enabled=config.get("cache.enable", True))

    def get_current_location(self) -> Optional[Tuple[str, float, float]]:
        """Auto-detect location using multiple fallback providers, with short-TTL caching.

        IP-based geolocation rarely changes within a day, so we cache the
        result to avoid hitting three external providers on every command
        that needs a location hint.
        """
        result, is_stale = get_or_fetch(
            self.cache, "ip_geolocation", self.ttl_seconds, self._detect_via_providers
        )
        if result is None:
            return None
        if is_stale:
            logger.info("Using cached (stale) IP location")
        return tuple(result)  # cache round-trips through JSON as a list

    def _detect_via_providers(self) -> Optional[Tuple[str, float, float]]:
        providers = [
            self._detect_via_ipinfo,
            self._detect_via_ipgeolocation,
            self._detect_via_ipapi,
        ]

        for provider in providers:
            try:
                result = provider()
                if result:
                    city, lat, lon = result
                    logger.info(f"Location detected via {provider.__name__}: {city}")
                    return (city, lat, lon)
            except Exception as e:
                logger.debug(f"{provider.__name__} failed: {e}")
                continue

        logger.warning("All location providers failed")
        return None

    def _detect_via_ipinfo(self) -> Optional[Tuple[str, float, float]]:
        """Most reliable free provider: ipinfo.io."""
        resp = httpx.get("https://ipinfo.io/json", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("loc")
            if loc and "," in loc:
                lat, lon = map(float, loc.split(","))
                city = data.get("city") or "Unknown"
                return (city, lat, lon)
        return None

    def _detect_via_ipgeolocation(self) -> Optional[Tuple[str, float, float]]:
        """Fallback: ipgeolocation.io."""
        resp = httpx.get("https://api.ipgeolocation.io/ipgeo?fields=city,lat,lon", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city") or "Unknown"
            lat = data.get("lat")
            lon = data.get("lon")
            if lat and lon:
                return (city, float(lat), float(lon))
        return None

    def _detect_via_ipapi(self) -> Optional[Tuple[str, float, float]]:
        """Fallback: ipapi.co (often rate-limited)."""
        resp = httpx.get("https://ipapi.co/json/", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            city = data.get("city") or "Unknown"
            lat = data.get("latitude")
            lon = data.get("longitude")
            if lat and lon:
                return (city, float(lat), float(lon))
        return None

    def search_location(self, query: str) -> Optional[Tuple[str, float, float]]:
        """Search location by name using Nominatim (not cached: an explicit user query)."""
        try:
            resp = httpx.get(
                f"{self.base_url}/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": 1,
                },
                headers={"User-Agent": "deen-cli/0.1 (https://github.com/voltvirtuoso/deen-cli)"},
                timeout=8,
            )
            resp.raise_for_status()
            data = resp.json()

            if data:
                display_name = data[0]["display_name"]
                city = display_name.split(",")[0].strip()
                return (city, float(data[0]["lat"]), float(data[0]["lon"]))
            return None
        except Exception as e:
            logger.warning(f"Location search failed: {e}")
            return None
