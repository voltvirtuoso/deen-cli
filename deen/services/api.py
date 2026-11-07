"""``ApiService``: the one object the rest of the app talks to for content.

It is a facade composed from per-domain modules, each of which owns its
endpoints, caching strategy and offline fallback:

    quran.py   random ayah, surah text, surah index
    hadith.py  collections, sections, mood search
    dua.py     Hisn al-Muslim categories and duas
    prayer.py  prayer times, Hijri date

Shared plumbing (config, TTLs, caches, HTTP) lives in ``base.py``. Anything
that can be absent or stale returns a ``deen.cache.Fetched``; "random"
lookups return the item (or None).
"""
from .base import BaseService
from .dua import DuaMixin
from .hadith import HADITH_COLLECTIONS, MOOD_KEYWORDS, HadithMixin
from .prayer import PrayerMixin
from .quran import QuranMixin

__all__ = ["ApiService", "HADITH_COLLECTIONS", "MOOD_KEYWORDS"]


class ApiService(QuranMixin, HadithMixin, DuaMixin, PrayerMixin, BaseService):
    pass
