"""``deen inspire``: the one-word shortcut for a random item of any type."""
from __future__ import annotations

from typing import Optional

import typer

from ..content import ContentEngine
from ..ui import console
from ._common import Fresh, get_config
from .app import PANEL_CONTENT, command
from .dua import resolve_category
from .hadith import VALID_MOODS, validate_mood


@command(panel=PANEL_CONTENT)
def inspire(
    content_type: str = typer.Option("hadith", "--type", "-t", help="ayah, hadith or dua"),
    mood: Optional[str] = typer.Option(None, "--mood", "-m", help="Hadith only: " + ", ".join(VALID_MOODS) + "."),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Narrow the pick: a surah number (ayah), collection (hadith) or dua category.",
    ),
    fresh: Fresh = False,
):
    """Quick random item. Shortcut for [cyan]deen quran|hadith|dua random[/cyan]."""
    content_type = content_type.strip().lower()
    if mood:
        if content_type != "hadith":
            console.print(
                f"[yellow]⚠️  --mood only applies to --type hadith; ignoring it for --type {content_type}.[/yellow]"
            )
            mood = None
        else:
            validate_mood(mood)

    if content_type == "dua" and category:
        category = resolve_category(category)

    ContentEngine(get_config()).display_content(
        content_type=content_type, category=category, force_fresh=fresh, mood=mood
    )
