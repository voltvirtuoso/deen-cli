"""The Typer apps and the ``@command`` decorator every command is registered with."""
from __future__ import annotations

from typing import Callable, Optional

import typer

from ._common import guard

app = typer.Typer(
    name="deen",
    help=(
        "[bold]deen-cli[/bold] \u2014 a git-style tracker for daily Islamic habits "
        "(prayers, Qur'an, dhikr), plus a spiritual-content lookup (ayah / hadith / dua).\n\n"
        "[dim]First run:[/dim] deen init\n"
        "[dim]Daily:[/dim] deen status  \u00b7  deen commit  \u00b7  deen log\n"
        "[dim]Read:[/dim] deen quran|hadith|dua  [cyan]list[/cyan] | [cyan]read[/cyan] | [cyan]random[/cyan]   "
        "[dim](e.g. deen quran read 1, deen hadith read bukhari, deen dua random morning)[/dim]\n\n"
        "[dim]Shell tab-completion (optional, not required to use deen-cli):[/dim]\n"
        "[dim]  --install-completion installs it for your current shell (bash/zsh/fish/etc.)[/dim]\n"
        "[dim]  --show-completion prints the completion script instead of installing it[/dim]"
    ),
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,  # bare `deen` shows a friendly dashboard instead (see __main__.main)
)

config_app = typer.Typer(
    name="config",
    help="View or change deen-cli settings (logging, caching, API endpoints).",
    rich_markup_mode="rich",
)

# Panel names used to group `deen --help`.
PANEL_HABITS = "Daily habits"
PANEL_CONTENT = "Qur'an, hadith & dua"
PANEL_SETUP = "Setup & settings"


def _group(name: str, help: str) -> typer.Typer:
    return typer.Typer(name=name, help=help, rich_markup_mode="rich", no_args_is_help=True)


# Every content type has the same three verbs:  list  |  read  |  random
quran_app = _group("quran", "The Qur'an: [cyan]list[/cyan] surahs, [cyan]read[/cyan] one, or get a [cyan]random[/cyan] ayah.")
hadith_app = _group("hadith", "Hadith: [cyan]list[/cyan] collections/sections, [cyan]read[/cyan] a collection, or get a [cyan]random[/cyan] hadith.")
dua_app = _group("dua", "Duas (Hisn al-Muslim): [cyan]list[/cyan] categories, [cyan]read[/cyan] one, or get a [cyan]random[/cyan] dua.")

app.add_typer(quran_app, name="quran", rich_help_panel=PANEL_CONTENT)
app.add_typer(hadith_app, name="hadith", rich_help_panel=PANEL_CONTENT)
app.add_typer(dua_app, name="dua", rich_help_panel=PANEL_CONTENT)
app.add_typer(config_app, name="config", rich_help_panel=PANEL_SETUP)


def command(
    name: Optional[str] = None,
    *,
    requires_init: bool = True,
    target: typer.Typer = app,
    panel: Optional[str] = None,
    hidden: bool = False,
) -> Callable[[Callable], Callable]:
    """Register a command with the standard guard.

    ``requires_init`` defaults to True: every command needs ``deen init``
    except the ones that explicitly opt out (``init`` itself, ``config *``).
    ``panel`` groups a top-level command under a heading in ``deen --help``;
    ``hidden`` keeps deprecated aliases out of the help.
    """

    def decorator(fn: Callable) -> Callable:
        guarded = guard(fn, requires_init=requires_init)
        target.command(name, rich_help_panel=panel, hidden=hidden)(guarded)
        return guarded

    return decorator
