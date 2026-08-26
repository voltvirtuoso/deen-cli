"""Unified API client with config-driven endpoints, caching, and retries."""
import logging
import random
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

import httpx

from ..cache import Cache, get_or_fetch
from ..config import DeenConfig

logger = logging.getLogger("deen.api")

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


class ApiService:
    def __init__(self, config: DeenConfig):
        self.config = config
        self.timeout = config.get("api.timeout_seconds", 10)
        self.max_retries = int(config.get("api.max_retries", 2))
        cache_enabled = config.get("cache.enable", True)
        self.ayah_ttl = float(config.get("cache.ayah_ttl_hours", 24)) * 3600
        self.hadith_ttl = float(config.get("cache.hadith_ttl_hours", 720)) * 3600
        self.dua_ttl = float(config.get("cache.dua_ttl_hours", 720)) * 3600
        self.surah_ttl = float(config.get("cache.surah_ttl_hours", 720)) * 3600
        self.prayer_ttl = float(config.get("cache.prayer_times_ttl_hours", 12)) * 3600

        self._ayah_cache = Cache("ayah", enabled=cache_enabled)
        self._hadith_cache = Cache("hadith", enabled=cache_enabled)
        self._dua_cache = Cache("dua", enabled=cache_enabled)
        self._prayer_cache = Cache("prayer_times", enabled=cache_enabled)
        self._misc_cache = Cache("misc", enabled=cache_enabled)

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------
    def _get(self, url: str, **kwargs) -> httpx.Response:
        """GET with a small retry/backoff for transient network errors.

        Only retries on connection/timeout failures and 5xx responses --
        4xx client errors (bad request, not found) fail fast since retrying
        won't help.
        """
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", {}).setdefault("User-Agent", "deen-cli/0.1")
        # httpx does NOT follow redirects by default. Without this, an
        # endpoint that's moved to https (or added a trailing slash, etc.)
        # returns a 301 that we then just... retried against the same dead
        # URL 3 times and gave up, silently falling back to stale/cached
        # content instead of actually fetching anything.
        kwargs.setdefault("follow_redirects", True)

        last_exc = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = httpx.get(url, **kwargs)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Server error {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as e:
                last_exc = e
                if attempt < self.max_retries:
                    backoff = 0.5 * (2 ** attempt)
                    logger.debug(f"Request to {url} failed ({e}); retrying in {backoff}s")
                    time.sleep(backoff)
                else:
                    logger.warning(f"Request to {url} failed after {attempt + 1} attempt(s): {e}")
        raise last_exc

    # ------------------------------------------------------------------
    # Qur'an
    # ------------------------------------------------------------------
    def fetch_random_ayah(self) -> Optional[Dict]:
        """Fetch a random ayah (Arabic + translation + transliteration).

        Unlike hadith (where we cache a whole collection and pick randomly
        from it locally), the ayah endpoint itself returns a new random ayah
        per request and is a single cheap call -- so we always try live
        first for actual variety, and only fall back to the last
        successfully fetched ayah (regardless of its age) or the offline DB
        pool if the live call fails. Caching this behind a TTL would mean
        showing the exact same ayah for up to a day, defeating "random".
        """
        try:
            result = self._fetch_random_ayah_live()
        except Exception as e:
            logger.warning(f"Live ayah fetch failed: {e}")
            result = None

        if result is not None:
            self._ayah_cache.set("last_known_good", result)
            return result

        stale = self._ayah_cache.get_stale("last_known_good")
        if stale is not None:
            logger.info("Serving last known-good ayah (live fetch failed)")
            return stale

        return self._get_fallback_content("ayah")

    def _fetch_random_ayah_live(self) -> Optional[Dict]:
        base_url = self.config.get("api.quran_base_url")
        arabic_edition = self.config.get("api.quran_edition_arabic", "quran-uthmani")
        translation_edition = self.config.get("api.quran_edition_translation", "en.sahih")
        transliteration_edition = self.config.get("api.quran_edition_transliteration", "en.transliteration")
        editions = f"{arabic_edition},{translation_edition},{transliteration_edition}"

        # Cache-bust with a per-request nonce: the URL is otherwise
        # identical on every call, so a CDN/reverse-proxy in front of the
        # API is free to serve the same cached response for a window of
        # time -- which looks exactly like "randomness isn't working" even
        # though our own code never caches this call.
        resp = self._get(
            f"{base_url}/ayah/random/editions/{editions}",
            params={"_": f"{time.time_ns()}"},
        )
        data = resp.json()["data"]
        edition_map = {item["edition"]["identifier"]: item for item in data}

        surah_name = data[0]["surah"]["englishName"]
        return {
            "id": f"{data[0]['surah']['number']}:{data[0]['numberInSurah']}",
            "arabic": edition_map[arabic_edition]["text"],
            "translation": edition_map[translation_edition]["text"],
            "transliteration": edition_map.get(transliteration_edition, {}).get("text", ""),
            "surah_english": surah_name,
            "source": f"Surah {surah_name}",
        }

    def fetch_ayahs_by_surah(self, surah: str) -> Optional[list]:
        """Return every ayah in a surah (for `deen read-surah`).

        Accepts a surah number 1-114. Cached for a long TTL (surah_ttl) since
        Qur'an text never changes -- unlike fetch_random_ayah, there's no
        "must be fresh" concern here.
        """
        surah_num = surah.strip()
        if not surah_num.isdigit() or not (1 <= int(surah_num) <= 114):
            return None

        data, is_stale = get_or_fetch(
            self._ayah_cache, f"surah_{surah_num}", self.surah_ttl, lambda: self._fetch_surah_live(surah_num)
        )
        if not data:
            return None
        if is_stale:
            logger.info(f"Serving Surah {surah_num} from stale cache")
        return data

    def _fetch_surah_live(self, surah_num: str) -> Optional[list]:
        base_url = self.config.get("api.quran_base_url")
        arabic_edition = self.config.get("api.quran_edition_arabic", "quran-uthmani")
        translation_edition = self.config.get("api.quran_edition_translation", "en.sahih")
        transliteration_edition = self.config.get("api.quran_edition_transliteration", "en.transliteration")
        editions = f"{arabic_edition},{translation_edition},{transliteration_edition}"

        resp = self._get(f"{base_url}/surah/{surah_num}/editions/{editions}")
        data = resp.json()["data"]
        edition_map = {item["edition"]["identifier"]: item for item in data}

        arabic_ayahs = edition_map[arabic_edition]["ayahs"]
        translation_ayahs = edition_map[translation_edition]["ayahs"]
        translit_ayahs = edition_map.get(transliteration_edition, {}).get("ayahs", [])
        surah_name = edition_map[arabic_edition].get("englishName") or edition_map[translation_edition].get("englishName")

        results = []
        for i, a in enumerate(arabic_ayahs):
            translit_text = translit_ayahs[i]["text"] if i < len(translit_ayahs) else ""
            translation_text = translation_ayahs[i]["text"] if i < len(translation_ayahs) else ""
            results.append({
                "id": f"{surah_num}:{a['numberInSurah']}",
                "arabic": a["text"],
                "translation": translation_text,
                "transliteration": translit_text,
                "surah_english": surah_name,
                "source": f"Surah {surah_name} ({surah_num}:{a['numberInSurah']})",
            })
        return results or None

    def fetch_surah_list(self) -> Tuple[Optional[list], bool]:
        """List all 114 surahs (number + names), for discoverability (`deen surahs`).

        Returns (surahs, is_offline_fallback). We deliberately don't bundle
        a hardcoded offline copy of all 114 surah names (too much risk of a
        transliteration/spelling error going unnoticed in something we
        never re-verify) -- if the API and cache are both unavailable, we
        say so plainly instead. Surah *numbers* 1-114 always work with
        ``read-surah`` even without this endpoint.
        """
        data, is_stale = get_or_fetch(
            self._misc_cache, "surah_list", self.surah_ttl, self._fetch_surah_list_live
        )
        if data is not None:
            if is_stale:
                logger.info("Serving surah list from stale cache")
            return data, False
        return None, True

    def _fetch_surah_list_live(self) -> Optional[list]:
        base_url = self.config.get("api.quran_base_url")
        resp = self._get(f"{base_url}/surah")
        return resp.json().get("data")

    # ------------------------------------------------------------------
    # Hadith
    # ------------------------------------------------------------------
    def fetch_random_hadith(self, mood: Optional[str] = None, collection: Optional[str] = None) -> Optional[Dict]:
        """Fetch a random authenticated hadith, with matching Arabic text where available.

        Preferentially reuses collections we've already cached instead of
        always picking a brand-new random collection: with 6 collections
        (english + arabic each), picking uniformly at random on every call
        meant most calls missed the cache and hit the network anyway. Once
        a few collections are warm, we mostly serve from cache and only
        occasionally fetch a new collection to keep variety.

        ``collection``, when given, restricts the pick to that single
        collection (same collection names as ``read-hadith``: bukhari, muslim,
        tirmidhi, nasai, abudawud, ibnmajah) -- mirroring how `--category`
        already scopes the random pick for dua. An unrecognized collection
        name is ignored (falls back to picking across all collections)
        rather than silently erroring.

        ``mood``, when given, is resolved via `_fetch_mood_hadith` -- a
        keyword match over real, already-authenticated hadith text (see
        MOOD_KEYWORDS). It is never used to fabricate or alter content.
        """
        normalized_collection = None
        if collection:
            c = collection.strip().lower()
            if c in HADITH_COLLECTIONS:
                normalized_collection = c
            else:
                logger.info(f"Unrecognized hadith collection '{collection}' for --category; ignoring")

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
            cached_collections = [
                c for c in HADITH_COLLECTIONS
                if self._hadith_cache.get(f"collection_{c}_eng", self.hadith_ttl) is not None
            ]
            if cached_collections and (
                len(cached_collections) >= len(HADITH_COLLECTIONS) or random.random() < 0.85
            ):
                collection_choice = random.choice(cached_collections)
            else:
                collection_choice = random.choice(HADITH_COLLECTIONS)

        english_data, is_stale = get_or_fetch(
            self._hadith_cache,
            f"collection_{collection_choice}_eng",
            self.hadith_ttl,
            lambda: self._fetch_hadith_collection(collection_choice, _HADITH_ENGLISH_EDITION),
        )

        if english_data is None:
            logger.warning(f"No live or cached hadith data for '{collection_choice}'; using offline fallback")
            return self._get_fallback_content("hadith")

        if is_stale:
            logger.info(f"Serving '{collection_choice}' hadiths from stale cache")

        hadiths = self._flatten_hadiths(english_data)
        if not hadiths:
            return self._get_fallback_content("hadith")

        h = random.choice(hadiths)
        arabic_map = self._get_arabic_map(collection_choice)
        result = self._build_hadith_result(h, collection_choice, arabic_map)
        if mood:
            result["mood_matched"] = False
        return result

    def _fetch_mood_hadith(self, mood: str, collection: Optional[str]) -> Optional[Dict]:
        """Keyword-search real (already fetched/cached) hadith text for a mood match.

        Searches whichever collections are already warm in the cache first
        (no extra network cost); if nothing is cached yet, searches Bukhari
        and Muslim (the two largest, most commonly available collections)
        before giving up rather than fetching all six up front. Only ever
        selects among hadith already returned by the API -- nothing here
        alters or invents hadith text.
        """
        keywords = MOOD_KEYWORDS.get(mood.strip().lower())
        if not keywords:
            return None

        if collection:
            search_order = [collection]
        else:
            cached = [
                c for c in HADITH_COLLECTIONS
                if self._hadith_cache.get(f"collection_{c}_eng", self.hadith_ttl) is not None
            ]
            preferred = cached or ["bukhari", "muslim"]
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

    def fetch_hadiths_list(self, collection: str) -> Optional[list]:
        """Return every hadith in a collection, formatted (for `deen read-hadith`).

        Large collections (Sahih al-Bukhari has ~7,000 hadiths) are still a
        single cached fetch + one Arabic lookup map built once, rather than
        the O(n^2) per-hadith re-scan a naive implementation would do.
        """
        collection = collection.strip().lower()
        if collection not in HADITH_COLLECTIONS:
            return None

        english_data, is_stale = get_or_fetch(
            self._hadith_cache,
            f"collection_{collection}_eng",
            self.hadith_ttl,
            lambda: self._fetch_hadith_collection(collection, _HADITH_ENGLISH_EDITION),
        )
        if english_data is None:
            logger.warning(f"No live or cached hadith data for '{collection}'; checking offline pool")
            return self._get_offline_hadiths_list()

        if is_stale:
            logger.info(f"Serving '{collection}' hadiths from stale cache")

        hadiths = self._flatten_hadiths(english_data)
        if not hadiths:
            return None

        arabic_map = self._get_arabic_map(collection)
        return [self._build_hadith_result(h, collection, arabic_map) for h in hadiths]

    def _fetch_hadith_collection(self, collection: str, edition_template: str) -> Optional[Dict]:
        base_url = self.config.get("api.hadith_base_url")
        edition = edition_template.format(collection=collection)
        resp = self._get(f"{base_url}/{edition}.json")
        return resp.json()

    @staticmethod
    def _flatten_hadiths(data: Dict) -> list:
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
        """Cached {hadith_number: arabic_text} map for a collection, built once.

        Built (and cached) as a single lookup table instead of re-scanning
        the whole Arabic edition per hadith -- that would be O(n^2) for a
        full collection listing (e.g. ~7,000 hadiths in Bukhari).
        """
        result, is_stale = get_or_fetch(
            self._hadith_cache,
            f"arabic_map_{collection}",
            self.hadith_ttl,
            lambda: self._build_arabic_map(collection),
        )
        return result or {}

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

    def fetch_random_dua(self, category: Optional[str] = None) -> Optional[Dict]:
        """Fetch a dua from the Hisn al-Muslim (Fortress of the Muslim) collection.

        Sourced live from api.islamic.app's /v1/dhikr endpoints (268 duas
        across 132 categories, with named shortcuts like "morning",
        "evening", "protection", "before-sleep" etc.) -- see
        `fetch_dua_categories()` for the full, dynamically-fetched list
        rather than a hardcoded few. Falls back to the small offline
        authenticated pool only if the live API and cache both fail.

        - With a category: the category's full dua list is cached (it's
          static content, like a hadith collection), and we pick randomly
          from it locally each call -- so repeated calls for "morning"
          cycle through all ~25 duas in that chapter instead of always
          returning the same one.
        - Without a category: hits /v1/dhikr/random, which the API
          explicitly serves as `Cache-Control: no-store` (a fresh draw from
          the whole 268-dua collection every time), so we don't cache it
          either -- only the last successful draw is kept as a stale
          fallback if a later call fails offline.
        """
        if category:
            duas = self.fetch_duas_list(category)
            if duas:
                return random.choice(duas)
            logger.warning(f"No live or cached duas for category '{category}'; using offline fallback")
            return self._get_offline_dua_fallback(category)

        try:
            entry = self._fetch_dua_random_live()
        except Exception as e:
            logger.warning(f"Live random-dua fetch failed: {e}")
            entry = None

        if entry is not None:
            formatted = self._format_dua_entry(entry)
            self._dua_cache.set("last_known_good", formatted)
            return formatted

        stale = self._dua_cache.get_stale("last_known_good")
        if stale is not None:
            logger.info("Serving last known-good dua (live fetch failed)")
            return stale

        return self._get_offline_dua_fallback(None)

    def fetch_duas_list(self, category: str) -> Optional[list]:
        """Return every dua in a category (all ~25 for "morning", etc.), already formatted.

        Used both by `fetch_random_dua` (picks one locally) and by
        `deen read-dua` (pages through all of them) -- the category's
        dua list is static content, so it's cached like a hadith
        collection rather than re-fetched per call.
        """
        duas, is_stale = get_or_fetch(
            self._dua_cache,
            f"category_{category.lower()}",
            self.dua_ttl,
            lambda: self._fetch_dua_category_live(category),
        )
        if duas:
            if is_stale:
                logger.info(f"Serving dua category '{category}' from stale cache")
            return [self._format_dua_entry(d) for d in duas]

        logger.warning(f"No live or cached duas for category '{category}'; checking offline pool")
        return self._get_offline_duas_list(category)

    def _fetch_dua_category_live(self, category: str) -> Optional[list]:
        base_url = self.config.get("api.dua_base_url")
        resp = self._get(f"{base_url}/{category.strip().lower()}")
        data = resp.json().get("data", {})
        return data.get("duas") or None

    def _fetch_dua_random_live(self) -> Optional[Dict]:
        base_url = self.config.get("api.dua_base_url")
        # Same cache-busting rationale as the ayah endpoint (see
        # _fetch_random_ayah_live): avoids a CDN serving the same "random"
        # response repeatedly.
        resp = self._get(f"{base_url}/random", params={"_": f"{time.time_ns()}"})
        return resp.json().get("data")

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

    def fetch_dua_categories(self) -> Tuple[Optional[Dict], bool]:
        """List all dua categories + named shortcuts, for discoverability (`deen categories`).

        Returns (data, is_offline_fallback). data has "shortcuts" (list of
        str) and "categories" (list of {number, en, ar, count}) when live,
        or just a static "shortcuts" list when we had to fall back offline.
        """
        data, is_stale = get_or_fetch(
            self._misc_cache, "dua_categories", self.dua_ttl, self._fetch_dua_categories_live
        )
        if data is not None:
            if is_stale:
                logger.info("Serving dua categories from stale cache")
            return data, False

        logger.warning("No live or cached dua categories; using a minimal offline shortcut list")
        return {
            "shortcuts": ["morning", "evening", "before-sleep", "protection", "after-prayer"],
            "categories": [],
        }, True

    def _fetch_dua_categories_live(self) -> Optional[Dict]:
        base_url = self.config.get("api.dua_base_url")
        resp = self._get(base_url)
        return resp.json().get("data")

    def _get_offline_dua_fallback(self, category: Optional[str]) -> Optional[Dict]:
        """Last-resort dua from the small local authenticated pool (see database.py)."""
        result = self.fetch_random_dua_offline(category)
        return result

    def _get_offline_duas_list(self, category: str) -> Optional[list]:
        """Last-resort dua list for ``read-dua``, from the small local offline pool.

        The offline pool only has a handful of entries per category (unlike
        the live API's ~25), but showing what we do have beats a hard
        error when the API and cache are both unavailable.
        """
        try:
            from ..database import get_db

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT text_arabic, text_english, source, category, transliteration
                    FROM content_fallbacks
                    WHERE content_type = 'dua' AND LOWER(category) = LOWER(?)
                    """,
                    (category,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return None
                return [
                    {
                        "arabic": row[0],
                        "translation": row[1],
                        "source": row[2],
                        "category": row[3] or "general",
                        "transliteration": row[4] or "",
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.warning(f"Offline dua list fetch error: {e}")
            return None

    def fetch_random_dua_offline(self, category: Optional[str] = None) -> Optional[Dict]:
        """Read a dua from the local offline pool only (used as the final fallback)."""
        try:
            from ..database import get_db

            with get_db() as conn:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        """
                        SELECT text_arabic, text_english, source, category, transliteration
                        FROM content_fallbacks
                        WHERE content_type = 'dua' AND LOWER(category) = LOWER(?)
                        ORDER BY RANDOM() LIMIT 1
                        """,
                        (category,),
                    )
                    row = cursor.fetchone()
                    if row is None:
                        # No exact offline match for this category (our offline
                        # pool only covers a handful) -- any authenticated dua
                        # beats an error.
                        cursor.execute(
                            """
                            SELECT text_arabic, text_english, source, category, transliteration
                            FROM content_fallbacks
                            WHERE content_type = 'dua'
                            ORDER BY RANDOM() LIMIT 1
                            """
                        )
                        row = cursor.fetchone()
                else:
                    cursor.execute(
                        """
                        SELECT text_arabic, text_english, source, category, transliteration
                        FROM content_fallbacks
                        WHERE content_type = 'dua'
                        ORDER BY RANDOM() LIMIT 1
                        """
                    )
                    row = cursor.fetchone()

                if row:
                    return {
                        "arabic": row[0],
                        "translation": row[1],
                        "source": row[2],
                        "category": row[3] or "general",
                        "transliteration": row[4] or "",
                    }
        except Exception as e:
            logger.warning(f"Offline dua fetch error: {e}")
        return None

    # ------------------------------------------------------------------
    # Prayer times
    # ------------------------------------------------------------------
    def fetch_prayer_times(self, lat: float, lon: float, date: str) -> Tuple[Optional[Dict], bool]:
        """Fetch prayer times for a location/date.

        Returns (timings, is_stale). ``is_stale`` is True when the result
        came from an expired cache entry because the live API (and its
        method-3/MWL retry) both failed -- callers should tell the user
        they're seeing a cached, possibly-outdated schedule rather than
        silently presenting it as current. There is intentionally no
        hardcoded "typical" prayer-time table: showing made-up times for the
        wrong day/location is worse than clearly failing.
        """
        method = self.config.get("prayer.calculation_method", "3")
        school = self.config.get("prayer.school", "0")
        cache_key = f"{round(lat, 3)}_{round(lon, 3)}_{date}_{method}_{school}"

        result, is_stale = get_or_fetch(
            self._prayer_cache,
            cache_key,
            self.prayer_ttl,
            lambda: self._fetch_prayer_times_live(lat, lon, date, method, school),
        )
        return result, is_stale

    def _fetch_prayer_times_live(self, lat: float, lon: float, date: str, method: str, school: str) -> Optional[Dict]:
        base_url = self.config.get("api.aladhan_base_url")

        def _request(m: str) -> Dict:
            resp = self._get(
                f"{base_url}/timings/{date}",
                params={"latitude": lat, "longitude": lon, "method": m, "school": school},
            )
            timings = resp.json()["data"]["timings"]
            return {k: timings[k][:5] for k in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")}

        try:
            return _request(method)
        except Exception as e:
            logger.warning(f"Primary prayer-time method '{method}' failed ({e}); retrying with MWL (3)")
            try:
                return _request("3")
            except Exception as fallback_e:
                logger.warning(f"Fallback prayer-time method also failed: {fallback_e}")
                return None

    # ------------------------------------------------------------------
    # Offline fallback content
    # ------------------------------------------------------------------
    def _get_offline_hadiths_list(self) -> Optional[list]:
        """Every hadith in the small local offline pool, formatted like fetch_hadiths_list."""
        try:
            from ..database import get_db

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT text_english, source, grade, text_arabic, category
                    FROM content_fallbacks WHERE content_type = 'hadith'
                    """
                )
                rows = cursor.fetchall()
                if not rows:
                    return None
                return [
                    {
                        "id": "offline",
                        "text": text_english,
                        "reference": source,
                        "grade": grade or "Authenticated",
                        "narrator": category or "Verified narrator",
                        "collection": "offline_pool",
                        "arabic": text_arabic or "",
                    }
                    for (text_english, source, grade, text_arabic, category) in rows
                ]
        except Exception as e:
            logger.warning(f"Offline hadith list fetch error: {e}")
            return None

    def _get_fallback_content(self, content_type: str) -> Optional[Dict]:
        """Get authenticated fallback content from the local database (last resort)."""
        try:
            from ..database import get_db

            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT text_english, source, grade, text_arabic, transliteration, category
                    FROM content_fallbacks
                    WHERE content_type = ?
                    ORDER BY RANDOM() LIMIT 1
                    """,
                    (content_type,),
                )

                row = cursor.fetchone()
                if row:
                    text_english, source, grade, text_arabic, transliteration, category = row
                    if content_type == "hadith":
                        return {
                            "id": "offline",
                            "text": text_english,
                            "reference": source,
                            "grade": grade or "Authenticated",
                            "narrator": category or "Verified narrator",
                            "collection": "offline_pool",
                            "arabic": text_arabic or "",
                        }
                    # ayah -- "source" looks like "Quran 94:5"; split it so the
                    # panel title doesn't repeat the same string twice.
                    verse_ref = source.replace("Quran", "").strip() or source
                    return {
                        "id": verse_ref,
                        "arabic": text_arabic or "",
                        "translation": text_english,
                        "transliteration": transliteration or "",
                        "surah_english": None,
                        "source": source,
                    }
        except Exception as e:
            logger.warning(f"Failed to get offline fallback content: {e}")
        return None

    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text."""
        import re

        text = re.sub(r"<[^>]+>", "", text)
        return " ".join(text.split())

    def fetch_islamic_date(self) -> str:
        """Get today's Islamic (Hijri) date, cached for a day since it only changes daily."""
        today = datetime.now().strftime("%Y-%m-%d")
        result, is_stale = get_or_fetch(
            self._misc_cache, f"hijri_{today}", 24 * 3600, lambda: self._fetch_islamic_date_live(today)
        )
        if result:
            return result
        return "Hijri date unavailable (offline and no cached value)"

    def _fetch_islamic_date_live(self, today: str) -> Optional[str]:
        base_url = self.config.get("api.aladhan_base_url")
        resp = self._get(f"{base_url}/gregorian/{today}")
        data = resp.json()
        hijri = data["data"]["hijri"]
        return f"{hijri['day']} {hijri['month']['en']} {hijri['year']} AH"
