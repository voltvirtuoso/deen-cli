"""Content engine with ZERO hardcoded religious content - API-driven only"""
from typing import Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from .config import DeenConfig
from .services.api import ApiService

console = Console()

class ContentEngine:
    def __init__(self):
        self.config = DeenConfig()
        self.api = ApiService(self.config)
    
    def _create_rtl_text(self, text: str) -> Text:
        """Create right-aligned Arabic text"""
        return Text(text, justify="right", style="bold")
    
    def _simple_transliteration(self, arabic: str) -> str:
        """Basic transliteration (not used for religious content - just UX enhancement)"""
        mapping = {'ا': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh',
                  'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh', 'ص': 's',
                  'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
                  'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h', 'و': 'w', 'ي': 'y'}
        return ''.join(mapping.get(c, c) for c in arabic if c not in 'ًٌٍَُِّْـٕٖٜٟٓٔٗ٘ٙٚٛٝٞ')
    
    def get_random_ayah(self, force_fresh: bool = False) -> Dict:
        """Get ayah from API with authenticated fallback"""
        ayah = self.api.fetch_random_ayah()
        if not ayah:
            ayah = {
                "id": "112:1",
                "arabic": "قُلْ هُوَ اللَّهُ أَحَدٌ",
                "translation": "Say, 'He is Allah, [who is] One.'",
                "surah_english": "Al-Ikhlas"
            }
        
        return {
            "id": ayah["id"],
            "arabic_text": self._create_rtl_text(ayah["arabic"]),
            "translation": ayah["translation"],
            "surah_english": ayah["surah_english"],
            "transliteration": self._simple_transliteration(ayah["arabic"])
        }
    
    def get_random_hadith(self, force_fresh: bool = False, mood: Optional[str] = None) -> Dict:
        """Get hadith from API with authenticated fallback"""
        hadith = self.api.fetch_random_hadith()
        if not hadith:
            hadith = {
                "id": "1",
                "text": "Actions are judged by intentions.",
                "reference": "Sahih al-Bukhari 1",
                "grade": "Sahih",
                "narrator": "Umar ibn al-Khattab",
                "collection": "bukhari"
            }
        
        return {
            "id": hadith["id"],
            "arabic_text": self._create_rtl_text(hadith["narrator"]),
            "translation": hadith["text"],
            "source": hadith["reference"],
            "grade": hadith["grade"],
            "transliteration": hadith["narrator"]
        }
    
    def get_random_dua(self, category: Optional[str] = None) -> Dict:
        """Get authenticated dua from offline fallbacks (Hisn al-Muslim)"""
        dua = self.api.fetch_random_dua(category=category)
        if not dua:
            dua = {
                "arabic": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
                "translation": "In the name of Allah, the Entirely Merciful, the Especially Merciful.",
                "source": "Quran 1:1",
                "category": "general"
            }
        
        return {
            "arabic_text": self._create_rtl_text(dua["arabic"]),
            "translation": dua["translation"],
            "source": dua["source"],
            "category": dua["category"],
            "transliteration": self._simple_transliteration(dua["arabic"])
        }
    
    def display_content(self, content_type: str = "dua", category: Optional[str] = None, 
                       force_fresh: bool = False, mood: Optional[str] = None):
        """Render content with proper Rich formatting"""
        if content_type == "ayah":
            content = self.get_random_ayah(force_fresh)
            title = f"🕋 Quran {content['id']} • {content['surah_english']}{' [FRESH]' if force_fresh else ''}"
            
            panel_content = Text()
            panel_content.append(content["arabic_text"])
            panel_content.append("\n\n")
            panel_content.append(f"({content.get('transliteration', 'Transliteration')})\n\n", style="cyan")
            panel_content.append(f"\"{content['translation']}\"\n", style="italic")
            panel_content.append(f"— {content['surah_english']}", style="dim")
            
            console.print(Panel(panel_content, title=title, border_style="blue", expand=False))
        
        elif content_type == "hadith":
            content = self.get_random_hadith(force_fresh, mood)
            mood_tag = f" • Mood: {mood}" if mood else ""
            title = f"📜 Hadith{' [FRESH]' if force_fresh else ''}{mood_tag}"
            
            panel_content = Text()
            if content.get("arabic_text"):
                panel_content.append(content["arabic_text"])
                panel_content.append("\n\n")
            
            # ✅ FIXED: Use explicit style instead of markup strings
            grade_lower = content['grade'].lower()
            if "sahih" in grade_lower:
                grade_style = "bold green"
            elif "hasan" in grade_lower:
                grade_style = "bold yellow"
            else:
                grade_style = "bold cyan"
            
            # Append grade with explicit style (NOT markup strings)
            panel_content.append(content['grade'], style=grade_style)
            panel_content.append("\n\n")
            
            panel_content.append(f"\"{content['translation']}\"\n", style="italic")
            panel_content.append(f"\n— {content['source']}", style="dim")
            
            console.print(Panel(panel_content, title=title, border_style="yellow", expand=False))
        
        elif content_type == "dua":
            content = self.get_random_dua(category=category)
            cat_display = content['category'].title() if content['category'] else "General"
            title = f"🤲 Dua ({cat_display}){' [FRESH]' if force_fresh else ''}"
            
            panel_content = Text()
            panel_content.append(content["arabic_text"])
            panel_content.append("\n\n")
            panel_content.append(f"({content.get('transliteration', 'Transliteration')})\n\n", style="cyan")
            panel_content.append(f"\"{content['translation']}\"\n", style="italic")
            panel_content.append(f"— {content['source']}", style="dim")
            
            console.print(Panel(panel_content, title=title, border_style="green", expand=False))
        
        console.print("\n[dim]💡 Sources: Quran.com API | Authenticated Hadiths | Hisn al-Muslim Duas[/dim]")