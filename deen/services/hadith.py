"""Hadith: six collections via fawazahmed0/hadith-api (English + Arabic editions)."""
from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional

from ..cache import Fetched, get_or_fetch
from . import offline

logger = logging.getLogger("deen.hadith")

HADITH_COLLECTIONS = ["bukhari", "muslim", "tirmidhi", "nasai", "abudawud", "ibnmajah"]

# There is no hadith API that tags narrations by emotional "mood" -- that
# classification doesn't exist as authenticated metadata anywhere, so it
# can't be fetched. The accurate workaround (rather than either faking a
# mood tag or silently ignoring --mood, which is what happened before) is
# a keyword search over the REAL, authenticated hadith text returned by the
# API: we look for hadith whose actual (unmodified) English text touches on
# themes associated with each mood, and pick randomly among the matches.
# This never invents or alters hadith text -- it only narrows which
# already-authenticated hadith gets shown. If nothing matches, we say so
# and fall back to an ordinary random authenticated hadith instead of
# fabricating a "match".
MOOD_KEYWORDS: Dict[str, list] = {
    "stressed": ["hardship", "ease", "distress", "relief", "trial", "burden"],
    "anxious": ["fear", "anxiety", "worry", "trust in allah", "peace of mind", "reassur"],
    "grateful": ["gratitude", "thankful", "thanks", "grateful", "blessing", "praise"],
    "sad": ["grief", "sorrow", "sadness", "mourn", "comfort", "patience"],
    "angry": ["anger", "temper", "rage", "furious", "forgive", "calm"],
    "lonely": ["companion", "brotherhood", "brethren", "loneliness", "alone", "ummah"],
    "tired": ["rest", "ease", "burden", "strength", "patience", "weary"],
    "doubtful": ["faith", "certainty", "doubt", "conviction", "belief", "sincerity"],
}

# Not every fawazahmed0 collection has a published Arabic edition under this
# exact naming scheme; we try opportunistically and just omit Arabic text if
# it's missing rather than fabricating/mislabeling anything as Arabic.
_HADITH_ARABIC_EDITION = "ara-{collection}"
_HADITH_ENGLISH_EDITION = "eng-{collection}"


class HadithMixin:
    # ------------------------------------------------------------------
    # Collection access (the one cached fetch everything else builds on)
    # ------------------------------------------------------------------
    def _english_collection(self, collection: str) -> Fetched:
        return get_or_fetch(
            self._hadith_cache,
            f"collection_{collection}_eng",
            self.hadith_ttl,
            lambda: self._fetch_hadith_collection(collection, _HADITH_ENGLISH_EDITION),
        )

    def _cached_collections(self) -> List[str]:
        """Collections whose English edition is already in the (fresh) cache."""
        return [
            c for c in HADITH_COLLECTIONS
            if self._hadith_cache.get(f"collection_{c}_eng", self.hadith_ttl) is not None
        ]

    def _fetch_hadith_collection(self, collection: str, edition_template: str) -> Optional[Dict]:
        base_url = self.config.get("api.hadith_base_url")
        edition = edition_template.format(collection=collection)
        return self._get(f"{base_url}/{edition}.json").json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_random_hadith(self, mood: Optional[str] = None, collection: Optional[str] = None) -> Optional[Dict]:
        """A random authenticated hadith, with Arabic text where available.

        Prefers collections already in cache (mostly) so most calls avoid the
        network. ``collection`` restricts the pick to one collection; an
        unrecognised name is ignored. ``mood`` keyword-matches real hadith
        text (see MOOD_KEYWORDS) and never alters content.
        """
        normalized_collection = None
        if collection:
            c = collection.strip().lower()
            if c in HADITH_COLLECTIONS:
                normalized_collection = c
            else:
                logger.info(f"Unrecognized hadith collection '{collection}'; ignoring")

        if mood:
            matched = self._fetch_mood_hadith(mood, normalized_collection)
            if matched is not None:
                return matched
            logger.info(
                f"No hadith text matched mood '{mood}' in the searched collection(s); "
                "falling back to a random authenticated hadith"
            )

        if normalized_collection:
            collection_choice = normalized_collection
        else:
            cached = self._cached_collections()
            if cached and (len(cached) >= len(HADITH_COLLECTIONS) or random.random() < 0.85):
                collection_choice = random.choice(cached)
            else:
                collection_choice = random.choice(HADITH_COLLECTIONS)

        fetched = self._english_collection(collection_choice)
        if not fetched.ok:
            logger.warning(f"No live or cached hadith data for '{collection_choice}'; using offline fallback")
            return offline.random_hadith()

        hadiths = self._flatten_hadiths(fetched.data)
        if not hadiths:
            return offline.random_hadith()

        h = random.choice(hadiths)
        result = self._build_hadith_result(h, collection_choice, self._get_arabic_map(collection_choice))
        if mood:
            result["mood_matched"] = False
        return result

    def _fetch_mood_hadith(self, mood: str, collection: Optional[str]) -> Optional[Dict]:
        """Keyword-search real hadith text for a mood match.

        Searches warm collections first (no network cost), else Bukhari and
        Muslim, then the rest. Only selects among hadith the API returned.
        """
        keywords = MOOD_KEYWORDS.get(mood.strip().lower())
        if not keywords:
            return None

        if collection:
            search_order = [collection]
        else:
            preferred = self._cached_collections() or ["bukhari", "muslim"]
            search_order = preferred + [c for c in HADITH_COLLECTIONS if c not in preferred]

        for c in search_order:
            hadiths = self.fetch_hadiths_list(c)
            if not hadiths:
                continue
            matches = [h for h in hadiths if any(kw in h["text"].lower() for kw in keywords)]
            if matches:
                chosen = random.choice(matches)
                chosen["mood_matched"] = True
                return chosen
        return None

    def fetch_hadith_categories(self, collection: str) -> Optional[List[Dict]]:
        """The source's own book/section index for a collection."""
        collection = collection.strip().lower()
        if collection not in HADITH_COLLECTIONS:
            return None
        fetched = self._english_collection(collection)
        if not fetched.ok:
            return None

        metadata = fetched.data.get("metadata", {})
        sections = metadata.get("sections", {})
        details = metadata.get("section_details", {})
        categories = []
        for number, name in sections.items():
            if not name:
                continue
            detail = details.get(str(number), {})
            categories.append({
                "number": str(number),
                "name": name,
                "first": detail.get("hadithnumber_first"),
                "last": detail.get("hadithnumber_last"),
            })
        return categories or None

    def fetch_hadiths_list(self, collection: str) -> Optional[List[Dict]]:
        """Every hadith in a collection, formatted (``read-hadith``).

        One cached fetch plus one Arabic lookup map built once -- not a
        per-hadith re-scan (Bukhari has ~7,000).
        """
        collection = collection.strip().lower()
        if collection not in HADITH_COLLECTIONS:
            return None

        fetched = self._english_collection(collection)
        if not fetched.ok:
            logger.warning(f"No live or cached hadith data for '{collection}'; checking offline pool")
            return offline.hadiths()

        hadiths = self._flatten_hadiths(fetched.data)
        if not hadiths:
            return None

        arabic_map = self._get_arabic_map(collection)
        sections = fetched.data.get("metadata", {}).get("sections", {})
        results = []
        for h in hadiths:
            result = self._build_hadith_result(h, collection, arabic_map)
            reference = h.get("reference") or {}
            section_number = reference.get("book") if isinstance(reference, dict) else None
            if section_number is not None:
                section_number = str(section_number)
            result["section_number"] = section_number
            result["section_name"] = sections.get(section_number, "") if section_number else ""
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_hadiths(data: Dict) -> List[Dict]:
        hadiths = []
        for item in data.get("hadiths", []):
            if isinstance(item, dict) and "hadiths" in item:
                hadiths.extend(item["hadiths"])
            elif isinstance(item, list):
                hadiths.extend(item)
            else:
                hadiths.append(item)
        return hadiths

    def _get_arabic_map(self, collection: str) -> Dict[str, str]:
        """Cached {hadith_number: arabic_text}, built once per collection (avoids O(n^2))."""
        fetched = get_or_fetch(
            self._hadith_cache,
            f"arabic_map_{collection}",
            self.hadith_ttl,
            lambda: self._build_arabic_map(collection),
        )
        return fetched.data or {}

    def _build_arabic_map(self, collection: str) -> Optional[Dict[str, str]]:
        try:
            arabic_data = self._fetch_hadith_collection(collection, _HADITH_ARABIC_EDITION)
        except Exception as e:
            logger.debug(f"Arabic edition unavailable for '{collection}': {e}")
            return None
        if not arabic_data:
            return None
        m = {}
        for h in self._flatten_hadiths(arabic_data):
            num = h.get("hadithnumber") or h.get("hadithNumber") or str(h.get("number", ""))
            if num and h.get("text"):
                m[str(num)] = h["text"]
        return m or None

    def _build_hadith_result(self, h: Dict, collection: str, arabic_map: Optional[Dict[str, str]] = None) -> Dict:
        narrator = (
            h.get("narrator")
            or h.get("narratorEnglish")
            or h.get("narratorenglish")
            or "A companion of the Prophet \ufdfa"
        )
        hadith_number = h.get("hadithnumber") or h.get("hadithNumber") or str(h.get("number", "N/A"))
        text = h.get("text", "Hadith text unavailable")

        explicit_grade = str(h.get("grade", "")).strip().lower()
        if "sahih" in explicit_grade:
            grade = "Sahih"
        elif "hasan" in explicit_grade:
            grade = "Hasan"
        elif collection in ["bukhari", "muslim"]:
            grade = "Sahih"
        else:
            grade = "Hasan"

        reference = f"{collection.title().replace('Ibnmajah', 'Ibn Majah')} {hadith_number}"

        # Best-effort: matching Arabic text for this exact hadith number,
        # from the same (cached) Arabic edition. If the Arabic edition
        # doesn't exist for this collection or the numbering doesn't line
        # up, we simply omit Arabic rather than showing something
        # mislabeled as Arabic (e.g. the English narrator name, which the
        # previous version did).
        if arabic_map is None:
            arabic_map = self._get_arabic_map(collection)
        arabic_text = arabic_map.get(str(hadith_number))

        return {
            "id": hadith_number,
            "collection": collection,
            "text": text,
            "narrator": narrator,
            "grade": grade,
            "reference": reference,
            "arabic": arabic_text or "",
        }
