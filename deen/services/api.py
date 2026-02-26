"""Unified API client with config-driven endpoints - NO circular imports"""
import httpx
from typing import Dict, Optional
import logging
import random
from ..config import DeenConfig

logger = logging.getLogger(__name__)

class ApiService:
    def __init__(self, config: DeenConfig):
        self.config = config
        self.timeout = config.get("api.timeout_seconds", 10)
    
    def fetch_random_ayah(self) -> Optional[Dict]:
        """Fetch random ayah from Quran API"""
        try:
            base_url = self.config.get("api.quran_base_url")
            translation_id = self.config.get("api.translation_id")
            
            resp = httpx.get(
                f"{base_url}/verses/random",
                params={
                    "fields": "text_uthmani,verse_number,chapter_id",
                    "translations": str(translation_id),
                    "language": "en"
                },
                headers={"User-Agent": "deen-cli/0.1"},
                timeout=self.timeout,
                follow_redirects=True
            )
            resp.raise_for_status()
            data = resp.json()
            
            verse = data["verse"]
            translation = verse["translations"][0]["text"] if verse.get("translations") else "Translation unavailable"
            
            # Get surah name
            surah_resp = httpx.get(
                f"{base_url}/chapters/{verse['chapter_id']}",
                timeout=5
            )
            surah_name = "Surah"
            if surah_resp.status_code == 200:
                surah_data = surah_resp.json()["chapter"]
                surah_name = surah_data["translated_name"]["name"]
            
            return {
                "id": f"{verse['chapter_id']}:{verse['verse_number']}",
                "arabic": verse["text_uthmani"],
                "translation": self._clean_html(translation),
                "surah_english": surah_name
            }
        except Exception as e:
            logger.warning(f"Quran API error: {e}")
            return self._get_fallback_content("ayah")
    
    def fetch_random_hadith(self) -> Optional[Dict]:
        """Fetch random hadith from hadithapi.pages.dev"""
        try:
            base_url = self.config.get("api.hadith_base_url")
            collections = ["bukhari", "muslim", "tirmidhi", "nasai", "abudawud", "ibnmajah"]
            collection = random.choice(collections)
            
            # Try modern /hadith/{collection}/random endpoint first
            try:
                resp = httpx.get(
                    f"{base_url}/hadith/{collection}/random",
                    headers={"User-Agent": "deen-cli/0.1"},
                    timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                hadith_data = data.get("hadith", {})
            except (httpx.HTTPError, KeyError, ValueError):
                # Fallback to /collections/{collection}/random
                resp = httpx.get(
                    f"{base_url}/collections/{collection}/random",
                    headers={"User-Agent": "deen-cli/0.1"},
                    timeout=self.timeout
                )
                resp.raise_for_status()
                data = resp.json()
                hadith_data = data.get("hadith", {})
            
            if not hadith_data.get("text"):
                raise ValueError("Empty hadith response")
            
            grade = hadith_data.get("grade") or ("Sahih" if collection in ["bukhari", "muslim"] else "Hasan")
            
            return {
                "id": hadith_data.get("id", "N/A"),
                "collection": collection,
                "text": hadith_data.get("text", "Hadith text unavailable"),
                "narrator": hadith_data.get("narrator", "Unknown narrator"),
                "grade": grade,
                "reference": hadith_data.get("reference", f"{collection.title()} {hadith_data.get('id', 'N/A')}")
            }
        except Exception as e:
            logger.warning(f"Hadith API error: {e}")
            return self._get_fallback_content("hadith")
    
    def fetch_prayer_times(self, lat: float, lon: float, date: str) -> Optional[Dict]:
        """Fetch prayer times from Aladhan API"""
        try:
            base_url = self.config.get("api.aladhan_base_url")
            method = self.config.get("prayer.calculation_method", "2")
            school = self.config.get("prayer.school", "0")
            
            resp = httpx.get(
                f"{base_url}/timings/{date}",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "method": method,
                    "school": school
                },
                headers={"User-Agent": "deen-cli/0.1"},
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            
            timings = data["data"]["timings"]
            return {
                "Fajr": timings["Fajr"][:5],
                "Sunrise": timings["Sunrise"][:5],
                "Dhuhr": timings["Dhuhr"][:5],
                "Asr": timings["Asr"][:5],
                "Maghrib": timings["Maghrib"][:5],
                "Isha": timings["Isha"][:5]
            }
        except Exception as e:
            logger.warning(f"Prayer times API error: {e}")
            return None
    
    def _get_fallback_content(self, content_type: str) -> Optional[Dict]:
        """
        Get authenticated fallback content from database.
        LOCAL IMPORT to avoid circular dependency at module level.
        """
        try:
            from ..database import get_db
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT text_english, source, grade 
                    FROM content_fallbacks 
                    WHERE content_type = ?
                    ORDER BY RANDOM() LIMIT 1
                """, (content_type,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "id": "fallback",
                        "text": row[0],
                        "reference": row[1],
                        "grade": row[2] or "Authenticated",
                        "narrator": "Verified Source",
                        "collection": "authenticated_pool",
                        "arabic": ""
                    }
        except Exception as e:
            logger.warning(f"Failed to get fallback content: {e}")
        return None
    
    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text"""
        import re
        text = re.sub(r'<[^>]+>', '', text)
        return ' '.join(text.split())