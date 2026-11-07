"""Prayer times and Hijri date (Aladhan)."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional

from ..cache import Fetched, get_or_fetch

logger = logging.getLogger("deen.prayer")

PRAYER_KEYS = ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")


class PrayerMixin:
    def fetch_prayer_times(self, lat: float, lon: float, date: str) -> Fetched:
        """Prayer timings for a location/date.

        ``is_stale`` is set when the result came from an expired cache entry
        because the live API (and its MWL retry) failed. There is
        intentionally no hardcoded "typical" table: made-up times for the
        wrong day or place are worse than a clear failure (``data`` is None).
        """
        method = self.config.get("prayer.calculation_method", "3")
        school = self.config.get("prayer.school", "0")
        cache_key = f"{round(lat, 3)}_{round(lon, 3)}_{date}_{method}_{school}"
        return get_or_fetch(
            self._prayer_cache, cache_key, self.prayer_ttl,
            lambda: self._fetch_prayer_times_live(lat, lon, date, method, school),
        )

    def _fetch_prayer_times_live(self, lat: float, lon: float, date: str, method: str, school: str) -> Optional[Dict]:
        base_url = self.config.get("api.aladhan_base_url")

        def _request(m: str) -> Dict:
            resp = self._get(
                f"{base_url}/timings/{date}",
                params={"latitude": lat, "longitude": lon, "method": m, "school": school},
            )
            timings = resp.json()["data"]["timings"]
            return {k: timings[k][:5] for k in PRAYER_KEYS}

        try:
            return _request(method)
        except Exception as e:
            logger.warning(f"Primary prayer-time method '{method}' failed ({e}); retrying with MWL (3)")
            try:
                return _request("3")
            except Exception as fallback_e:
                logger.warning(f"Fallback prayer-time method also failed: {fallback_e}")
                return None

    def current_prayer(self) -> str:
        """Which prayer's window it is right now (Isha if the times are unavailable)."""
        lat, lon = self.config.get("user.latitude"), self.config.get("user.longitude")
        if not (lat and lon):
            return "Isha"
        now = datetime.now()
        prayers = self.fetch_prayer_times(float(lat), float(lon), now.strftime("%Y-%m-%d")).data
        if not prayers:
            return "Isha"

        order = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
        current_time = now.strftime("%H:%M")
        current = "Isha"
        for i, prayer in enumerate(order):
            start = prayers.get(prayer)
            if start and current_time >= start:
                if i + 1 < len(order):
                    if current_time < prayers.get(order[i + 1], "23:59"):
                        current = prayer
                        break
                else:
                    current = prayer
                    break
        return current

    def fetch_islamic_date(self) -> Fetched:
        """Today's Hijri date, cached for a day. ``data`` is None if unavailable."""
        today = datetime.now().strftime("%Y-%m-%d")
        return get_or_fetch(
            self._misc_cache, f"hijri_{today}", 24 * 3600,
            lambda: self._fetch_islamic_date_live(today),
        )

    def _fetch_islamic_date_live(self, today: str) -> Optional[str]:
        base_url = self.config.get("api.aladhan_base_url")
        hijri = self._get(f"{base_url}/gregorian/{today}").json()["data"]["hijri"]
        return f"{hijri['day']} {hijri['month']['en']} {hijri['year']} AH"
