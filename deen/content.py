"""Content engine with API-driven content and correct RTL rendering."""
import logging
import textwrap
from typing import Callable, Dict, List, Optional

from .arabic import prepare_arabic
from .pager import page_text
from rich import box
from rich.cells import cell_len
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from .config import DeenConfig
from .services.api import ApiService

logger = logging.getLogger("deen.content")
console = Console()


class ContentEngine:
    def __init__(self):
        self.config = DeenConfig()
        self.api = ApiService(self.config)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _content_width(self) -> int:
        """A comfortable, consistent reading-column width for card content.

        Capped so cards don't stretch edge-to-edge and turn into one long
        unbroken line on a very wide terminal (reads like a book/article
        column instead, same idea as `man`/`bat`/`glow`'s default line
        length), but still shrinks gracefully on narrow ones.

        Using ONE width for both the Arabic block and the English block is
        what actually matters here: previously the Arabic wrap width was
        capped independently of whatever width Rich picked for the English
        text, so the two blocks wrapped to different widths and the card
        looked lopsided (a narrow ragged Arabic column next to a much wider
        English paragraph). Now both are wrapped to the same width before
        rendering.
        """
        try:
            w = console.width
        except Exception:
            w = 100
        return max(28, min(w - 8, 76))

    # ------------------------------------------------------------------
    # Arabic shaping / wrapping
    # ------------------------------------------------------------------
    @staticmethod
    def _wrap_by_cells(text: str, width: int) -> List[str]:
        """Word-wrap by terminal cell width, not len().

        The fully-vocalized Uthmani Qur'an text includes tashkeel
        (diacritic) combining marks, which take zero visual width in a
        terminal but count in a plain len(). Wrapping on cell_len keeps
        line breaks matched to what's actually on screen instead of
        wrapping too early/unevenly.
        """
        words = text.split()
        lines: List[str] = []
        current: List[str] = []
        current_w = 0
        for w in words:
            ww = cell_len(w)
            add = ww + (1 if current else 0)
            if current and current_w + add > width:
                lines.append(" ".join(current))
                current, current_w = [w], ww
            else:
                current.append(w)
                current_w += add
        if current:
            lines.append(" ".join(current))
        return lines or [text]

    def _prepare_arabic(self, text: str, width: Optional[int] = None) -> str:
        """Correctly wrap + shape an Arabic string for display in an LTR terminal.

        Order matters: wrap the ORIGINAL logical text first (plain
        whitespace wrapping, direction-agnostic), THEN reshape (join
        letterforms) and bidi-reorder (RTL display order) each finished
        line on its own. Doing it in the other order -- reshaping/
        reordering the whole string and then letting a generic wrapper
        break it -- wraps based on position in the already-*visually*
        reordered string, which can put the logical start of a sentence on
        a later screen line than its end.
        """
        wrap_width = width or self._content_width()
        output_lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                output_lines.append(paragraph)
                continue
            for line in self._wrap_by_cells(paragraph, wrap_width):
                output_lines.append(prepare_arabic(line))
        return "\n".join(output_lines)

    def _create_rtl_text(self, text: str) -> Text:
        """A standalone Rich Text block, ready to sit in a Group as its own renderable.

        no_wrap=True is required: the text is already wrapped + shaped
        per line above, so letting Rich wrap it again would re-scramble
        the line order. Because of that, this Text must always be combined
        with other content via `Group(...)`, never merged into a bigger
        Text with `.append()` -- append() only copies characters/style
        spans, it does NOT carry over no_wrap, so an appended copy would
        silently lose this protection.
        """
        return Text(self._prepare_arabic(text), justify="right", no_wrap=True)

    def _wrap_plain(self, text: str, width: Optional[int] = None) -> str:
        """Wrap plain (English) text to the same column width as the Arabic block."""
        w = width or self._content_width()
        wrapped = textwrap.wrap(text, width=w, break_long_words=False, break_on_hyphens=False)
        return "\n".join(wrapped) if wrapped else text

    # ------------------------------------------------------------------
    # Shared card renderer
    # ------------------------------------------------------------------
    def _render_card(
        self,
        *,
        title: str,
        border_style: str,
        arabic: Optional[str] = None,
        badge: Optional[str] = None,
        badge_style: str = "bold cyan",
        transliteration: Optional[str] = None,
        translation: str,
        footer: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Panel:
        """Build one consistently-styled content card (ayah / hadith / dua).

        Every text block -- Arabic, badge, transliteration, translation,
        footer -- is wrapped to the SAME width, so the card reads as one
        clean column instead of blocks of mismatched width.
        """
        width = self._content_width()
        blocks = []

        if arabic:
            blocks.append(self._create_rtl_text(arabic))
            blocks.append(Text(""))

        body = Text()
        if badge:
            body.append(badge, style=badge_style)
            body.append("\n\n")
        if transliteration:
            body.append(self._wrap_plain(f"({transliteration})", width), style="cyan")
            body.append("\n\n")
        body.append(self._wrap_plain(f"\u201c{translation}\u201d", width), style="italic")
        if footer:
            body.append("\n\n")
            body.append(self._wrap_plain(footer, width), style="dim")
        blocks.append(body)

        content = Group(*blocks) if len(blocks) > 1 else blocks[0]

        return Panel(
            content,
            title=f"[bold]{title}[/bold]",
            title_align="left",
            subtitle=f"[dim]{source}[/dim]" if source else None,
            subtitle_align="right",
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False,
        )

    def _render_compact_card(
        self,
        *,
        title: str,
        border_style: str,
        translation: str,
        arabic: Optional[str] = None,
        transliteration: Optional[str] = None,
        badge: Optional[str] = None,
        badge_style: str = "bold cyan",
        footer: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Group:
        """Render one reading item as a compact, continuous reading block.

        Full collections are read ten items at a time. A plain text block
        keeps the Arabic, translation, and source together without nested
        boxes or repeated blank rows that made a short surah unnecessarily tall.
        """
        width = self._content_width()
        blocks = [Text(title, style="bold")]
        if arabic:
            blocks.append(self._create_rtl_text(arabic))

        body = Text()
        if badge:
            body.append(badge, style=badge_style)
            body.append("\n")
        if transliteration:
            body.append(self._wrap_plain(f"({transliteration})", width), style="cyan")
            body.append("\n")
        body.append(self._wrap_plain(f"\u201c{translation}\u201d", width), style="italic")
        if footer:
            body.append("\n")
            body.append(self._wrap_plain(footer, width), style="dim")
        if source:
            body.append("\n")
            body.append(f"— {source}", style="dim")
        blocks.append(body)
        return Group(*blocks)

    # ------------------------------------------------------------------
    # Fetch + shape a single item
    # ------------------------------------------------------------------
    def get_random_ayah(self, force_fresh: bool = False, category: Optional[str] = None) -> Dict:
        """Get a random ayah, optionally scoped to one surah via ``category``.

        Mirrors how --category scopes random picks for dua and hadith: a
        surah number picks randomly among that surah's own ayahs (fetched via
        the same cached surah lookup used by ``read-surah``).
        An invalid/unrecognized surah number falls through to the ordinary
        whole-Quran random pick rather than erroring.
        """
        ayah = None
        if category and category.strip().isdigit() and 1 <= int(category.strip()) <= 114:
            surah_ayahs = self.api.fetch_ayahs_by_surah(category.strip())
            if surah_ayahs:
                import random as _random
                ayah = _random.choice(surah_ayahs)
            else:
                logger.warning(f"Could not fetch Surah {category} for --category; falling back to a random ayah")

        if ayah is None:
            ayah = self.api.fetch_random_ayah()
        if not ayah:
            # Both the live API and every offline fallback failed (e.g. a
            # fresh install with no network and no seeded content, which
            # shouldn't normally happen since init_db() always seeds a few
            # entries -- but we don't want to crash the render either way).
            raise RuntimeError(
                "No ayah available: the Quran API is unreachable and no offline content is cached. "
                "Check your connection and try again."
            )

        return {
            "id": ayah["id"],
            "arabic": ayah.get("arabic"),
            "translation": ayah["translation"],
            "surah_english": ayah.get("surah_english"),
            "source": ayah.get("source") or f"Quran {ayah['id']}",
            "transliteration": ayah.get("transliteration") or None,
        }

    def get_random_hadith(self, force_fresh: bool = False, mood: Optional[str] = None,
                           category: Optional[str] = None) -> Dict:
        """Get a hadith from the API with an authenticated offline fallback.

        ``category``, when set to a valid collection name (bukhari, muslim,
        tirmidhi, nasai, abudawud, ibnmajah), scopes the random pick to that
        collection -- the full collection is read with ``read-hadith``.

        ``mood`` is resolved by the API layer via a keyword search over
        real hadith text (see MOOD_KEYWORDS in services/api.py); it was
        previously accepted here only to be printed as a label and had no
        effect on which hadith was actually returned.
        """
        hadith = self.api.fetch_random_hadith(mood=mood, collection=category)
        if not hadith:
            raise RuntimeError(
                "No hadith available: the hadith API is unreachable and no offline content is cached. "
                "Check your connection and try again."
            )

        return {
            "id": hadith["id"],
            # Arabic text (when available) is the actual hadith text, matched
            # by hadith number against the collection's Arabic edition --
            # not the narrator's name reshaped to look Arabic-ish, which is
            # what an earlier version accidentally did.
            "arabic": hadith.get("arabic") or None,
            "translation": hadith["text"],
            "source": hadith["reference"],
            "grade": hadith["grade"],
            "narrator": hadith["narrator"],
            # None = no mood was requested; True = keyword-matched; False =
            # a mood was requested but nothing matched, so this is a plain
            # random pick shown as a fallback (see display_content).
            "mood_matched": hadith.get("mood_matched") if mood else None,
        }

    def get_random_dua(self, category: Optional[str] = None) -> Dict:
        """Get an authenticated dua from the Hisn al-Muslim collection."""
        dua = self.api.fetch_random_dua(category=category)
        if not dua:
            raise RuntimeError(
                "No dua available: the dua API is unreachable, nothing is cached, and the "
                "offline collection could not be read either."
            )

        return {
            "arabic": dua["arabic"],
            "translation": dua["translation"],
            "source": dua["source"],
            "category": dua["category"],
            "transliteration": dua.get("transliteration") or None,
        }

    def list_duas(self, category: str) -> list:
        """Get every dua in a category (for `deen read-dua --category ...`)."""
        duas = self.api.fetch_duas_list(category)
        if not duas:
            raise RuntimeError(
                f"No duas found for category '{category}' (API unreachable and nothing cached). "
                "Run 'deen categories' to see valid category numbers/shortcuts."
            )
        return duas

    def list_hadiths(self, collection: str) -> list:
        """Get every hadith in a collection (for `deen read-hadith --collection ...`)."""
        hadiths = self.api.fetch_hadiths_list(collection)
        if not hadiths:
            raise RuntimeError(
                f"No hadiths found for collection '{collection}' (API unreachable and nothing cached). "
                "Valid collections: bukhari, muslim, tirmidhi, nasai, abudawud, ibnmajah."
            )
        return hadiths

    def list_ayahs(self, surah: str) -> list:
        """Get every ayah in a surah (for `deen read-surah --surah ...`)."""
        ayahs = self.api.fetch_ayahs_by_surah(surah)
        if not ayahs:
            raise RuntimeError(
                f"No ayahs found for surah '{surah}' (API unreachable, nothing cached, or not a "
                "valid surah number 1-114). Run 'deen surahs' to see the full list."
            )
        return ayahs

    # ------------------------------------------------------------------
    # Single-item display
    # ------------------------------------------------------------------
    def display_content(self, content_type: str = "dua", category: Optional[str] = None,
                        force_fresh: bool = False, mood: Optional[str] = None):
        """Render one piece of content as a card."""
        if content_type == "ayah":
            content = self.get_random_ayah(force_fresh, category)
            surah_suffix = f" \u2022 {content['surah_english']}" if content.get("surah_english") else ""
            title = f"\U0001F54B Quran {content['id']}{surah_suffix}{' [FRESH]' if force_fresh else ''}"

            card = self._render_card(
                title=title,
                border_style="blue",
                arabic=content.get("arabic"),
                transliteration=content.get("transliteration"),
                translation=content["translation"],
                source=content["source"],
            )
            console.print(card)

        elif content_type == "hadith":
            content = self.get_random_hadith(force_fresh, mood, category)
            if mood and content.get("mood_matched"):
                mood_tag = f" \u2022 Mood: {mood} (matched)"
            elif mood:
                mood_tag = f" \u2022 Mood: {mood} (no match \u2014 random pick shown)"
            else:
                mood_tag = ""
            title = f"\U0001F4DC Hadith{' [FRESH]' if force_fresh else ''}{mood_tag}"

            card = self._render_card(
                title=title,
                border_style="yellow",
                arabic=content.get("arabic"),
                badge=content["grade"],
                badge_style=self._grade_style(content["grade"]),
                translation=content["translation"],
                footer=f"Narrated by {content['narrator']}",
                source=content["source"],
            )
            console.print(card)

        elif content_type == "dua":
            content = self.get_random_dua(category=category)
            cat_display = content["category"].title() if content["category"] else "General"
            title = f"\U0001F932 Dua ({cat_display}){' [FRESH]' if force_fresh else ''}"

            card = self._render_card(
                title=title,
                border_style="green",
                arabic=content["arabic"],
                transliteration=content.get("transliteration"),
                translation=content["translation"],
                source=content["source"],
            )
            console.print(card)

        else:
            raise ValueError(f"Unknown content type '{content_type}' (expected ayah, hadith, or dua)")

        console.print(
            "\n[dim]\U0001F4A1 Sources: Quran.com/alquran.cloud API | "
            "Authenticated Hadith collections | Hisn al-Muslim Duas[/dim]"
        )

    @staticmethod
    def _grade_style(grade: Optional[str]) -> str:
        grade_lower = (grade or "").lower()
        if "sahih" in grade_lower:
            return "bold green"
        if "hasan" in grade_lower:
            return "bold yellow"
        return "bold cyan"

    # ------------------------------------------------------------------
    # Paged list display
    # ------------------------------------------------------------------
    def display_dua_list(self, category: str, page: int = 1, per_page: int = 10):
        """Read one page of duas from a category.

        Pages are printed directly so Windows terminals retain real Unicode
        characters instead of passing them through a legacy system pager.
        """
        duas = self.list_duas(category)

        def render(i: int, dua: Dict) -> Panel:
            return self._render_compact_card(
                title=f"\U0001F932 Dua {i}/{len(duas)}",
                border_style="green",
                arabic=dua["arabic"],
                transliteration=dua.get("transliteration"),
                translation=dua["translation"],
                source=dua["source"],
            )

        self._page_through(duas, f"dua(s) \u2014 category: {category}", render, page, per_page)

    @staticmethod
    def filter_hadiths(
        hadiths: list,
        search: Optional[str] = None,
        category: Optional[str] = None,
        number: Optional[str] = None,
    ) -> list:
        """Filter hadiths by source section, exact number, and text search."""
        query = search.strip().casefold() if search else ""
        category_query = category.strip().casefold() if category else ""
        number_query = str(number).strip() if number else ""
        filtered = []
        for hadith in hadiths:
            if number_query and str(hadith.get("id", "")) != number_query:
                continue
            if category_query:
                section_number = str(hadith.get("section_number") or "").casefold()
                section_name = str(hadith.get("section_name") or "").casefold()
                if category_query != section_number and category_query not in section_name:
                    continue
            if query:
                searchable = " ".join(
                    str(hadith.get(field) or "")
                    for field in ("text", "narrator", "reference", "section_name")
                ).casefold()
                if query not in searchable:
                    continue
            filtered.append(hadith)
        return filtered

    def display_hadith_list(
        self,
        collection: str,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None,
        category: Optional[str] = None,
        number: Optional[str] = None,
    ):
        """Read one page of hadiths from a collection using optional filters.

        Large collections are fetched once and then narrowed by number, search
        text, or source section before the requested page is printed.
        """
        console.print(f"[dim]\U0001F4DC Fetching {collection}... this may take a moment the first time.[/dim]")
        hadiths = self.list_hadiths(collection)
        hadiths = self.filter_hadiths(hadiths, search, category, number)
        if not hadiths:
            criteria = []
            if number:
                criteria.append(f"number {number}")
            if search:
                criteria.append(f"search '{search}'")
            if category:
                criteria.append(f"category '{category}'")
            detail = ", ".join(criteria) or "the supplied filters"
            raise RuntimeError(f"No hadiths found in {collection} for {detail}.")

        filter_label = ""
        if search:
            filter_label += f" • search: {search}"
        if category:
            filter_label += f" • category: {category}"
        if number:
            filter_label += f" • number: {number}"

        def render(i: int, h: Dict) -> Panel:
            section = h.get("section_name")
            footer = f"Narrated by {h['narrator']}"
            if section:
                footer += f" • {section}"
            return self._render_compact_card(
                title=f"\U0001F4DC Hadith {i}/{len(hadiths)}",
                border_style="yellow",
                arabic=h.get("arabic"),
                badge=h.get("grade", "Unclassified"),
                badge_style=self._grade_style(h.get("grade")),
                translation=h["text"],
                footer=footer,
                source=h["reference"],
            )

        self._page_through(hadiths, f"hadith(s) \u2014 {collection}{filter_label}", render, page, per_page)

    def display_ayah_list(self, surah: str, page: int = 1, per_page: int = 10):
        """Read one page of ayahs from a surah."""
        ayahs = self.list_ayahs(surah)
        surah_name = ayahs[0].get("surah_english") if ayahs else None
        label = f"ayah(s) \u2014 Surah {surah}" + (f" ({surah_name})" if surah_name else "")

        def render(i: int, a: Dict) -> Panel:
            return self._render_compact_card(
                title=f"\U0001F54B Ayah {i}/{len(ayahs)}",
                border_style="blue",
                arabic=a["arabic"],
                transliteration=a.get("transliteration"),
                translation=a["translation"],
                source=a["id"],
            )

        self._page_through(ayahs, label, render, page, per_page)

    def _page_through(
        self,
        items: list,
        label: str,
        render_fn: Callable[[int, Dict], object],
        page: int = 1,
        per_page: int = 10,
    ):
        """Render one manageable page through a Unicode-safe pager.

        The pager prefers installed ``less`` and then ``bat``. Text is sent
        through a UTF-8 pipe, avoiding the Windows ``pydoc.pager`` conversion
        that produced literal ``\\u...`` escape sequences. If no external
        pager exists, the built-in Windows fallback supports basic scrolling.
        """
        if page < 1:
            raise ValueError("--page must be 1 or greater")
        if per_page < 1:
            raise ValueError("--per-page must be 1 or greater")
        total_pages = (len(items) + per_page - 1) // per_page
        if page > total_pages:
            raise ValueError(f"--page {page} is outside the available range 1-{total_pages}")

        start = (page - 1) * per_page
        selected = items[start:start + per_page]
        end = start + len(selected)
        with console.capture() as capture:
            console.rule(
                f"[bold]{label} • page {page}/{total_pages} • items {start + 1}-{end} of {len(items)}[/bold]"
            )
            console.print("[dim]Use --page N to jump pages, --per-page N to change page size.[/dim]")
            console.print()
            for offset, item in enumerate(selected):
                console.print(render_fn(start + offset + 1, item))
                console.print()
        page_text(capture.get())
