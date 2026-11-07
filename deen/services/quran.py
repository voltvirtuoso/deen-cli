"""Quran: random ayah, full surah, surah index (alquran.cloud)."""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Tuple

from ..cache import Fetched, fetch_live_first, get_or_fetch
from . import offline

logger = logging.getLogger("deen.quran")


class QuranMixin:
    def _quran_editions(self) -> Tuple[str, str, str, str, str]:
        """(base_url, arabic, translation, transliteration, 'a,b,c') from config."""
        base_url = self.config.get("api.quran_base_url")
        arabic = self.config.get("api.quran_edition_arabic", "quran-uthmani")
        translation = self.config.get("api.quran_edition_translation", "en.sahih")
        translit = self.config.get("api.quran_edition_transliteration", "en.transliteration")
        return base_url, arabic, translation, translit, f"{arabic},{translation},{translit}"

    def fetch_random_ayah(self) -> Optional[Dict]:
        """A random ayah (Arabic + translation + transliteration).

        Live-first (see ``fetch_live_first``): the endpoint itself is random,
        so a TTL cache would show the same ayah for a day. Falls back to the
        last good ayah, then the offline pool.
        """
        result = fetch_live_first(self._ayah_cache, "last_known_good", self._fetch_random_ayah_live)
        return result.data if result.ok else offline.random_ayah()

    def _fetch_random_ayah_live(self) -> Optional[Dict]:
        base_url, arabic, translation, translit, editions = self._quran_editions()
        # Per-request nonce: stops a CDN from serving one cached "random" response.
        resp = self._get(
            f"{base_url}/ayah/random/editions/{editions}",
            params={"_": f"{time.time_ns()}"},
        )
        data = resp.json()["data"]
        edition_map = {item["edition"]["identifier"]: item for item in data}

        surah_name = data[0]["surah"]["englishName"]
        return {
            "id": f"{data[0]['surah']['number']}:{data[0]['numberInSurah']}",
            "arabic": edition_map[arabic]["text"],
            "translation": edition_map[translation]["text"],
            "transliteration": edition_map.get(translit, {}).get("text", ""),
            "surah_english": surah_name,
            "source": f"Surah {surah_name}",
        }

    def fetch_ayahs_by_surah(self, surah: str) -> Optional[List[Dict]]:
        """Every ayah in surah 1-114 (for ``read-surah``). Cached long: the text never changes."""
        surah_num = surah.strip()
        if not surah_num.isdigit() or not (1 <= int(surah_num) <= 114):
            return None
        result = get_or_fetch(
            self._ayah_cache, f"surah_{surah_num}", self.surah_ttl,
            lambda: self._fetch_surah_live(surah_num),
        )
        return result.data or None

    def _fetch_surah_live(self, surah_num: str) -> Optional[List[Dict]]:
        base_url, arabic, translation, translit, editions = self._quran_editions()
        resp = self._get(f"{base_url}/surah/{surah_num}/editions/{editions}")
        data = resp.json()["data"]
        edition_map = {item["edition"]["identifier"]: item for item in data}

        arabic_ayahs = edition_map[arabic]["ayahs"]
        translation_ayahs = edition_map[translation]["ayahs"]
        translit_ayahs = edition_map.get(translit, {}).get("ayahs", [])
        surah_name = edition_map[arabic].get("englishName") or edition_map[translation].get("englishName")

        results = []
        for i, a in enumerate(arabic_ayahs):
            results.append({
                "id": f"{surah_num}:{a['numberInSurah']}",
                "arabic": a["text"],
                "translation": translation_ayahs[i]["text"] if i < len(translation_ayahs) else "",
                "transliteration": translit_ayahs[i]["text"] if i < len(translit_ayahs) else "",
                "surah_english": surah_name,
                "source": f"Surah {surah_name} ({surah_num}:{a['numberInSurah']})",
            })
        return results or None

    def fetch_surah_list(self) -> Fetched:
        """All 114 surahs (``deen quran list``).

        No bundled offline copy on purpose (a spelling error in hand-typed
        names would go unnoticed); if API and cache both fail, ``data`` is None.
        """
        return get_or_fetch(self._misc_cache, "surah_list", self.surah_ttl, self._fetch_surah_list_live)

    def _fetch_surah_list_live(self) -> Optional[List[Dict]]:
        base_url = self.config.get("api.quran_base_url")
        return self._get(f"{base_url}/surah").json().get("data")
