"""``deen quran``: list | read | random."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ..arabic import prepare_arabic
from ..content import ContentEngine
from ..services.api import ApiService
from ..ui import console
from ._common import Fresh, Page, PerPage, SurahArg, get_config
from .app import command, quran_app


# Plain functions: the commands below and the deprecated aliases in legacy.py share them.
def show_surah_list() -> None:
    console.print("[dim]📖 Fetching surah list...[/dim]")
    surah_list = ApiService(get_config()).fetch_surah_list().data

    if not surah_list:
        console.print(
            "[yellow]⚠️  Quran API unreachable and nothing cached, so surah names aren't available "
            "right now.[/yellow]\n"
            "[dim]Surah numbers 1-114 still work directly, e.g.: deen quran read 36[/dim]"
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
    console.print("\n[dim]💡 deen quran read <#> to page through a whole surah.[/dim]")


def show_surah(surah: str, page: int, per_page: int) -> None:
    ContentEngine(get_config()).display_ayah_list(surah, page=page, per_page=per_page)


@command("list", target=quran_app)
def quran_list():
    """List all 114 surahs with their number, meaning and ayah count.

    Fetched live so names/counts are always accurate. If the API is
    unreachable, surah numbers 1-114 still work with `deen quran read`.
    """
    show_surah_list()


@command("read", target=quran_app)
def quran_read(surah: SurahArg, page: Page = 1, per_page: PerPage = 10):
    """Read a surah ten ayahs at a time (use --page / --per-page to move)."""
    show_surah(surah, page, per_page)


@command("random", target=quran_app)
def quran_random(
    surah: Optional[str] = typer.Argument(None, metavar="[SURAH]", help="Pick only from this surah (1-114)."),
    fresh: Fresh = False,
):
    """Show one random ayah, optionally from a single surah (e.g. `deen quran random 36`)."""
    ContentEngine(get_config()).display_content(content_type="ayah", category=surah, force_fresh=fresh)
