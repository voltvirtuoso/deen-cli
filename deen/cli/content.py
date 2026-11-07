"""Content commands: inspire (random), read-* (full), categories / surahs (indexes)."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ..arabic import prepare_arabic
from ..content import ContentEngine
from ..errors import UserError
from ..services.api import ApiService, MOOD_KEYWORDS
from ..ui import console
from ._common import Collection, Page, PerPage, get_config
from .app import command

VALID_MOODS = list(MOOD_KEYWORDS)


# --------------------------------------------------------------------------
# One random item
# --------------------------------------------------------------------------
@command()
def inspire(
    content_type: str = typer.Option("hadith", "--type", "-t", help="Content type: ayah, hadith, dua"),
    mood: Optional[str] = typer.Option(
        None, "--mood", "-m",
        help=(
            "Hadith-only. Emotional state: " + ", ".join(VALID_MOODS) + ". "
            "No hadith source tags narrations by mood, so this keyword-matches real, "
            "authenticated hadith text on themes tied to the mood (see 'deen inspire "
            "--type hadith --mood ... '); if nothing matches, a plain random hadith is "
            "shown and clearly labeled as such rather than a false match."
        ),
    ),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help=(
            "Scopes the random pick only: "
            "for --type dua, a category number/shortcut (run 'deen categories'); "
            "for --type hadith, a collection name (bukhari, muslim, tirmidhi, nasai, abudawud, ibnmajah); "
            "for --type ayah, a surah number 1-114 (run 'deen surahs') -- e.g. --category 36 picks a "
            "random ayah from Surah Ya-Sin instead of anywhere in the Quran."
        ),
    ),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Get fresh content"),
):
    """Get one random piece of spiritual content.

    Use ``read-surah``, ``read-hadith``, or ``read-dua`` when you want to
    read a complete surah, hadith collection, or dua category.
    """
    content_type = content_type.strip().lower()

    if mood:
        if content_type != "hadith":
            console.print(
                f"[yellow]⚠️  --mood only applies to --type hadith; ignoring it for --type {content_type}.[/yellow]"
            )
            mood = None
        elif mood.strip().lower() not in VALID_MOODS:
            raise UserError(f"Unknown --mood '{mood}'. Valid moods: {', '.join(VALID_MOODS)}")

    ContentEngine(get_config()).display_content(
        content_type=content_type, category=category, force_fresh=fresh, mood=mood
    )


# --------------------------------------------------------------------------
# Read a whole thing, a page at a time
# --------------------------------------------------------------------------
@command("read-surah")
def read_surah(
    surah_arg: Optional[str] = typer.Argument(None, metavar="SURAH", help="Surah number from 1 to 114."),
    surah: Optional[str] = typer.Option(None, "--surah", "-s", help="Surah number from 1 to 114 (run 'deen surahs')."),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Read a surah ten ayahs at a time with --page and --per-page."""
    surah_number = surah or surah_arg
    if not surah_number:
        raise UserError("Provide a surah number, e.g. 'deen read-surah 101' or '--surah 101'.")
    ContentEngine(get_config()).display_ayah_list(surah_number, page=page, per_page=per_page)


@command("read-hadith")
def read_hadith(
    collection: Collection,
    search: Optional[str] = typer.Option(None, "--search", help="Search English text, narrator, or section title."),
    category: Optional[str] = typer.Option(
        None, "--category",
        help="Source section number or part of its title; run 'deen hadith-categories'.",
    ),
    number: Optional[str] = typer.Option(None, "--number", "-n", help="Read one exact hadith number."),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Read hadiths ten at a time; filter by text, number, or source category."""
    ContentEngine(get_config()).display_hadith_list(
        collection.strip().lower(),
        page=page,
        per_page=per_page,
        search=search,
        category=category,
        number=number,
    )


@command("read-dua")
def read_dua(
    category: str = typer.Option(
        ..., "--category", "-c", help="Dua category number or shortcut (run 'deen categories')."
    ),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Read a dua category ten items at a time with --page and --per-page."""
    ContentEngine(get_config()).display_dua_list(category, page=page, per_page=per_page)


# --------------------------------------------------------------------------
# Indexes: what can I read?
# --------------------------------------------------------------------------
@command("hadith-categories")
def hadith_categories(collection: Collection):
    """List a collection's source sections for use with --category."""
    categories_list = ApiService(get_config()).fetch_hadith_categories(collection)
    if not categories_list:
        raise UserError(
            f"No categories found for '{collection}'. Valid collections: "
            "bukhari, muslim, tirmidhi, nasai, abudawud, ibnmajah."
        )
    table = Table(title=f"{collection.strip().title()} hadith categories")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Section", style="white")
    table.add_column("Hadith range", style="dim")
    for item in categories_list:
        first, last = item.get("first"), item.get("last")
        number_range = f"{first}–{last}" if first is not None and last is not None else "?"
        table.add_row(item["number"], item["name"], number_range)
    console.print(table)
    console.print(
        f"\n[dim]Example: deen read-hadith -c {collection.strip().lower()} --category 1 --page 1[/dim]"
    )


@command()
def categories():
    """List dua categories for `deen inspire --category ...` or `deen read-dua`.

    Fetched live from the Hisn al-Muslim collection (132 categories) so
    this always reflects what's actually available, instead of a
    hardcoded short list.
    """
    console.print("[dim]📚 Fetching dua categories...[/dim]")
    fetched = ApiService(get_config()).fetch_dua_categories()
    data = fetched.data

    if fetched.is_offline:
        console.print("[yellow]⚠️  Dua API unreachable and nothing cached; showing a minimal offline shortcut list.[/yellow]\n")

    shortcuts = data.get("shortcuts", [])
    if shortcuts:
        console.print("[bold]Named shortcuts[/bold] (use with --category):")
        console.print("  " + ", ".join(shortcuts))
        console.print()

    categories_list = data.get("categories", [])
    if categories_list:
        table = Table(title=f"All {len(categories_list)} categories (or use a numeric --category)")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Category", style="white")
        table.add_column("Duas", style="dim", justify="right")
        for c in categories_list:
            table.add_row(str(c.get("number", "?")), c.get("en", "Unknown"), str(c.get("count", "?")))
        console.print(table)
    elif not fetched.is_offline:
        console.print("[dim]No category list returned by the API.[/dim]")

    console.print("\n[dim]💡 Leave --category blank with `deen inspire -t dua` for a fully random dua.[/dim]")


@command()
def surahs():
    """List all 114 surahs (chapters) for use with `deen read-surah --surah <number>`.

    Fetched live from the Quran API so names/ayah counts are always
    accurate. If it is unreachable, surah *numbers* 1-114 still work with
    `deen read-surah --surah <number>`; names are unavailable until connected.
    """
    console.print("[dim]📖 Fetching surah list...[/dim]")
    surah_list = ApiService(get_config()).fetch_surah_list().data

    if not surah_list:
        console.print(
            "[yellow]⚠️  Quran API unreachable and nothing cached, so surah names aren't available "
            "right now.[/yellow]\n"
            "[dim]Surah numbers 1-114 still work directly, e.g.: "
            "deen read-surah --surah 36[/dim]"
        )
        raise typer.Exit(1)

    table = Table(title=f"All {len(surah_list)} surahs")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("English", style="white")
    table.add_column("Meaning", style="dim")
    table.add_column("Ayahs", style="dim", justify="right")
    for s in surah_list:
        table.add_row(
            str(s.get("number", "?")),
            prepare_arabic(s.get("name")),
            s.get("englishName", "?"),
            s.get("englishNameTranslation", ""),
            str(s.get("numberOfAyahs", "?")),
        )
    console.print(table)
    console.print("\n[dim]💡 deen read-surah --surah <#> to page through a whole surah.[/dim]")
