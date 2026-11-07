"""Dua: Hisn al-Muslim via api.islamic.app."""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Dict, List, Optional

from ..cache import Fetched, fetch_live_first, get_or_fetch
from . import offline

logger = logging.getLogger("deen.dua")

OFFLINE_SHORTCUTS = ["morning", "evening", "before-sleep", "protection", "after-prayer"]

# Names people actually use, mapped to words in the English chapter titles.
# Each one is checked against the Hisn al-Muslim chapter index: e.g. chapter 26 is
# titled "For seeking guidance in forming a decision or choosing the proper course"
# and never says "istikhara" in English (only its Arabic title does).
SEARCH_ALIASES = {
    "istikhara": "guidance",
    "istikharah": "guidance",
    "adhan": "athan",
    "azan": "athan",
    "wudu": "ablution",
    "wudhu": "ablution",
    "ruku": "bowing",
    "sujud": "prostrat",
    "sujood": "prostrat",
    "witr": "witr",
    "qunut": "qunoot",
}


def search_dua_categories(categories: List[Dict], query: str) -> List[Dict]:
    """Categories matching ``query`` by number, English title or Arabic title.

    English matches must start at a word boundary, so "sin" finds "Upon committing
    a sin" but not "choosing"; "prostrat" still finds "prostrating". Arabic is
    matched as a substring (Arabic attaches prefixes like ال to words).
    """
    q = query.strip().casefold()
    if not q:
        return []
    q = SEARCH_ALIASES.get(q, q)
    word_start = re.compile(r"\b" + re.escape(q))
    return [
        c for c in categories
        if q == str(c.get("number", "")).casefold()
        or word_start.search((c.get("en") or "").casefold())
        or q in (c.get("ar") or "")
    ]


class DuaMixin:
    def fetch_random_dua(self, category: Optional[str] = None) -> Optional[Dict]:
        """A dua from Hisn al-Muslim.

        - With a category: the category's full list is cached (static, like a
          hadith collection) and one is picked locally, so repeated calls
          cycle through the whole chapter.
        - Without: ``/random`` is served ``no-store`` by the API, so it's
          live-first with only the last success kept as a fallback.
        """
        if category:
            duas = self.fetch_duas_list(category)
            if duas:
                return random.choice(duas)
            logger.warning(f"No live or cached duas for category '{category}'; using offline fallback")
            return offline.random_dua(category)

        result = fetch_live_first(self._dua_cache, "last_known_good", self._fetch_random_dua_live)
        return result.data if result.ok else offline.random_dua(None)

    def _fetch_random_dua_live(self) -> Optional[Dict]:
        base_url = self.config.get("api.dua_base_url")
        resp = self._get(f"{base_url}/random", params={"_": f"{time.time_ns()}"})
        entry = resp.json().get("data")
        return self._format_dua_entry(entry) if entry else None

    def fetch_duas_list(self, category: str) -> Optional[List[Dict]]:
        """Every dua in a category, formatted (``read-dua`` and the random pick)."""
        result = get_or_fetch(
            self._dua_cache, f"category_{category.lower()}", self.dua_ttl,
            lambda: self._fetch_dua_category_live(category),
        )
        if result.data:
            return [self._format_dua_entry(d) for d in result.data]
        logger.warning(f"No live or cached duas for category '{category}'; checking offline pool")
        return offline.duas(category)

    def _fetch_dua_category_live(self, category: str) -> Optional[List[Dict]]:
        base_url = self.config.get("api.dua_base_url")
        resp = self._get(f"{base_url}/{category.strip().lower()}")
        return resp.json().get("data", {}).get("duas") or None

    @staticmethod
    def _format_dua_entry(entry: Dict) -> Dict:
        category_info = entry.get("category", {}) or {}
        source = entry.get("source", {}) or {}
        transliteration = entry.get("transliteration", {}) or {}
        source_label = source.get("en") or (
            f"Hisn al-Muslim, Ch. {category_info.get('number', '?')}: {category_info.get('en', 'Dua')}"
        )
        return {
            "arabic": (entry.get("ar") or {}).get("text", ""),
            "translation": (entry.get("en") or {}).get("text", ""),
            "transliteration": transliteration.get("en") or "",
            "source": source_label,
            "category": category_info.get("en") or "general",
        }

    def fetch_dua_categories(self) -> Fetched:
        """Categories + named shortcuts (``deen dua list``).

        When nothing live or cached exists, returns a minimal shortcut list
        with ``is_offline=True``.
        """
        result = get_or_fetch(self._misc_cache, "dua_categories", self.dua_ttl, self._fetch_dua_categories_live)
        if result.ok:
            return result
        logger.warning("No live or cached dua categories; using a minimal offline shortcut list")
        return Fetched({"shortcuts": OFFLINE_SHORTCUTS, "categories": []}, is_offline=True)

    def _fetch_dua_categories_live(self) -> Optional[Dict]:
        base_url = self.config.get("api.dua_base_url")
        return self._get(base_url).json().get("data")
