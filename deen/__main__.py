#!/usr/bin/env python3
"""deen-cli: Git-style Islamic productivity companion.

This module only assembles the app; commands live in ``deen.cli.*``.
"""
import typer

from . import __version__
from .cli import setup, habits, quran, hadith, dua, inspire, settings, legacy  # noqa: F401  (importing registers the commands)
from .cli._common import get_config
from .cli.app import app, command
from .ui import console

_DASHBOARD = """\
[bold green]deen-cli[/bold green] — Version Control for Your Deeds

[bold]Daily habits[/bold]
  status            → Prayer times & next prayer
  commit            → Log a habit
  log               → View habit history

[bold]Qur'an, hadith & dua[/bold]  (same three verbs for each)
  deen quran  list | read <surah> | random
  deen hadith list | read <collection> | random
  deen dua    list | read <category> | random
  inspire           → Quick random item

[bold]Setup[/bold]
  init, config

[dim]'deen COMMAND --help' for details[/dim]"""


def _version_callback(value: bool):
    # Eager so `deen --version` prints and exits before a subcommand is resolved.
    if value:
        console.print(f"deen-cli {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False, "--version", "-V",
        help="Show the deen-cli version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
):
    """deen-cli: Git-style Islamic productivity companion"""
    if ctx.invoked_subcommand is None:
        if not get_config().is_initialized:
            console.print("[yellow]⚠️  Run 'deen init' to get started[/yellow]")
            raise typer.Exit(1)
        console.print(_DASHBOARD)


if __name__ == "__main__":
    app()
