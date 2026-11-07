"""``deen hadith``: list | read | random."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ..content import ContentEngine
from ..errors import UserError
from ..services.api import HADITH_COLLECTIONS, MOOD_KEYWORDS, ApiService
from ..ui import console
from ._common import CollectionArg, Fresh, Page, PerPage, get_config
from .app import command, hadith_app

VALID_MOODS = list(MOOD_KEYWORDS)
COLLECTION_NAMES = {
    "bukhari": "Sahih al-Bukhari",
    "muslim": "Sahih Muslim",
    "tirmidhi": "Jami' at-Tirmidhi",
    "nasai": "Sunan an-Nasa'i",
    "abudawud": "Sunan Abi Dawud",
    "ibnmajah": "Sunan Ibn Majah",
}


def validate_mood(mood: Optional[str]) -> Optional[str]:
    if mood and mood.strip().lower() not in VALID_MOODS:
        raise UserError(f"Unknown --mood '{mood}'. Valid moods: {', '.join(VALID_MOODS)}")
    return mood


def show_collections() -> None:
    table = Table(title="Hadith collections")
    table.add_column("Use", style="cyan")
    table.add_column("Collection", style="white")
    for key in HADITH_COLLECTIONS:
        table.add_row(key, COLLECTION_NAMES.get(key, key.title()))
    console.print(table)
    console.print("\n[dim]💡 deen hadith list <collection> shows its sections; deen hadith read <collection> reads it.[/dim]")


def show_sections(collection: str) -> None:
    collection = collection.strip().lower()
    sections = ApiService(get_config()).fetch_hadith_categories(collection)
    if not sections:
        raise UserError(
            f"No sections found for '{collection}'. Valid collections: {', '.join(HADITH_COLLECTIONS)}."
        )
    table = Table(title=f"{COLLECTION_NAMES.get(collection, collection.title())}: sections")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Section", style="white")
    table.add_column("Hadith range", style="dim")
    for item in sections:
        first, last = item.get("first"), item.get("last")
        number_range = f"{first}–{last}" if first is not None and last is not None else "?"
        table.add_row(item["number"], item["name"], number_range)
    console.print(table)
    console.print(f"\n[dim]Example: deen hadith read {collection} --section 1[/dim]")


def show_hadiths(collection: str, page: int, per_page: int, search, section, number) -> None:
    ContentEngine(get_config()).display_hadith_list(
        collection.strip().lower(),
        page=page,
        per_page=per_page,
        search=search,
        category=section,
        number=number,
    )


@command("list", target=hadith_app)
def hadith_list(
    collection: Optional[str] = typer.Argument(
        None, metavar="[COLLECTION]", help="Show this collection's sections. Omit to list the collections."
    ),
):
    """List the hadith collections, or one collection's sections."""
    show_sections(collection) if collection else show_collections()


@command("read", target=hadith_app)
def hadith_read(
    collection: CollectionArg,
    section: Optional[str] = typer.Option(
        None, "--section", help="Only this section: its number or part of its title (see 'deen hadith list <collection>')."
    ),
    number: Optional[str] = typer.Option(None, "--number", "-n", help="Read one exact hadith number."),
    search: Optional[str] = typer.Option(None, "--search", help="Search English text, narrator, or section title."),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Read a collection ten hadiths at a time; filter by section, number or text."""
    show_hadiths(collection, page, per_page, search, section, number)


@command("random", target=hadith_app)
def hadith_random(
    collection: Optional[str] = typer.Argument(None, metavar="[COLLECTION]", help="Pick only from this collection."),
    mood: Optional[str] = typer.Option(
        None, "--mood", "-m",
        help=(
            "Emotional state: " + ", ".join(VALID_MOODS) + ". No source tags hadith by mood, so this "
            "keyword-matches real authenticated text; if nothing matches you get a plain random hadith, "
            "clearly labeled."
        ),
    ),
    fresh: Fresh = False,
):
    """Show one random authenticated hadith."""
    ContentEngine(get_config()).display_content(
        content_type="hadith", category=collection, force_fresh=fresh, mood=validate_mood(mood)
    )
