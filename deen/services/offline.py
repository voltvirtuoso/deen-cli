"""Last-resort content from the bundled offline pool, shaped like live results.

All SQL lives in ``deen.database.fetch_offline_rows``; this module only maps
rows to the same dict shapes the live services return, so callers never
care where an item came from.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..database import fetch_offline_rows


def _hadith(row: Dict) -> Dict:
    return {
        "id": "offline",
        "text": row["text_english"],
        "reference": row["source"],
        "grade": row["grade"] or "Authenticated",
        "narrator": row["category"] or "Verified narrator",
        "collection": "offline_pool",
        "arabic": row["text_arabic"] or "",
    }


def _ayah(row: Dict) -> Dict:
    source = row["source"]
    # "Quran 94:5" -> "94:5" so the panel title doesn't repeat the same string.
    verse_ref = source.replace("Quran", "").strip() or source
    return {
        "id": verse_ref,
        "arabic": row["text_arabic"] or "",
        "translation": row["text_english"],
        "transliteration": row["transliteration"] or "",
        "surah_english": None,
        "source": source,
    }


def _dua(row: Dict) -> Dict:
    return {
        "arabic": row["text_arabic"],
        "translation": row["text_english"],
        "source": row["source"],
        "category": row["category"] or "general",
        "transliteration": row["transliteration"] or "",
    }


def random_hadith() -> Optional[Dict]:
    rows = fetch_offline_rows("hadith", random_order=True, limit=1)
    return _hadith(rows[0]) if rows else None


def random_ayah() -> Optional[Dict]:
    rows = fetch_offline_rows("ayah", random_order=True, limit=1)
    return _ayah(rows[0]) if rows else None


def hadiths() -> Optional[List[Dict]]:
    rows = fetch_offline_rows("hadith")
    return [_hadith(r) for r in rows] or None


def duas(category: str) -> Optional[List[Dict]]:
    rows = fetch_offline_rows("dua", category)
    return [_dua(r) for r in rows] or None


def random_dua(category: Optional[str] = None) -> Optional[Dict]:
    """A random offline dua; if the category has none, any offline dua beats an error."""
    rows = fetch_offline_rows("dua", category, random_order=True, limit=1) if category else []
    if not rows:
        rows = fetch_offline_rows("dua", random_order=True, limit=1)
    return _dua(rows[0]) if rows else None
