"""Old command names, kept working but hidden from --help.

Each one prints a one-line notice and forwards to the same function the new
command uses, so behaviour can't drift. Remove this module in a future major
version.
"""
from __future__ import annotations

from typing import Optional

import typer

from ._common import Page, PerPage, deprecated
from .app import command
from .dua import show_dua_categories, show_duas
from .hadith import show_hadiths, show_sections
from .quran import show_surah, show_surah_list
from ..errors import UserError


@command("surahs", hidden=True)
def surahs():
    """Deprecated: use `deen quran list`."""
    deprecated("surahs", "quran list")
    show_surah_list()


@command("read-surah", hidden=True)
def read_surah(
    surah_arg: Optional[str] = typer.Argument(None, metavar="SURAH"),
    surah: Optional[str] = typer.Option(None, "--surah", "-s"),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Deprecated: use `deen quran read`."""
    deprecated("read-surah", "quran read")
    number = surah or surah_arg
    if not number:
        raise UserError("Provide a surah number, e.g. 'deen quran read 101'.")
    show_surah(number, page, per_page)


@command("categories", hidden=True)
def categories():
    """Deprecated: use `deen dua list`."""
    deprecated("categories", "dua list")
    show_dua_categories()


@command("read-dua", hidden=True)
def read_dua(
    category: str = typer.Option(..., "--category", "-c"),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Deprecated: use `deen dua read`."""
    deprecated("read-dua", "dua read")
    show_duas(category, page, per_page)


@command("hadith-categories", hidden=True)
def hadith_categories(collection: str = typer.Option(..., "--collection", "-c")):
    """Deprecated: use `deen hadith list <collection>`."""
    deprecated("hadith-categories", "hadith list")
    show_sections(collection)


@command("read-hadith", hidden=True)
def read_hadith(
    collection: str = typer.Option(..., "--collection", "-c"),
    search: Optional[str] = typer.Option(None, "--search"),
    category: Optional[str] = typer.Option(None, "--category"),
    number: Optional[str] = typer.Option(None, "--number", "-n"),
    page: Page = 1,
    per_page: PerPage = 10,
):
    """Deprecated: use `deen hadith read`."""
    deprecated("read-hadith", "hadith read")
    show_hadiths(collection, page, per_page, search, category, number)
