"""Shared CLI plumbing: config singleton, the init/error guard, shared option types."""
from __future__ import annotations

import functools
import logging
from typing import Annotated, Callable, Optional

import typer

from ..config import DeenConfig
from ..errors import UserError
from ..ui import console, err_console

logger = logging.getLogger("deen.cli")

# ---------------------------------------------------------------------------
# Config: one instance per process
# ---------------------------------------------------------------------------
_config: Optional[DeenConfig] = None


def get_config() -> DeenConfig:
    """The process-wide config. Commands and services share this one instance."""
    global _config
    if _config is None:
        _config = DeenConfig()
    return _config


def reset_config() -> None:
    """Forget the cached config (for tests)."""
    global _config
    _config = None


# ---------------------------------------------------------------------------
# The guard every command runs inside
# ---------------------------------------------------------------------------
def guard(fn: Callable, *, requires_init: bool = True) -> Callable:
    """Wrap a command so every command behaves the same way.

    - Needs ``deen init`` first (unless ``requires_init=False``).
    - ``UserError``  -> yellow warning, exit 1.
    - Any other exception -> red ``✗ Error: ...`` (traceback goes to the log
      file only), exit 1.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if requires_init and not get_config().is_initialized:
            console.print("[red]✗ Run 'deen init' first[/red]")
            raise typer.Exit(1)
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort):
            raise
        except UserError as e:
            console.print(f"[yellow]⚠️  {e}[/yellow]")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(f"'{fn.__name__}' failed", exc_info=True)
            console.print(f"[red]✗ Error: {e}[/red]")
            raise typer.Exit(1)

    return wrapper


# ---------------------------------------------------------------------------
# Shared option types: defined once, reused by every command that needs them.
# ---------------------------------------------------------------------------
Page = Annotated[int, typer.Option("--page", "-p", min=1, help="Page number to display.")]
PerPage = Annotated[int, typer.Option("--per-page", min=1, max=50, help="Items per page (1-50).")]
Fresh = Annotated[bool, typer.Option("--fresh", "-f", help="Skip the cache and fetch new content.")]

# The positional argument is always "what you're looking at":
#   deen quran  read  <SURAH>        deen quran  random [SURAH]
#   deen hadith read  <COLLECTION>   deen hadith random [COLLECTION]
#   deen dua    read  <CATEGORY>     deen dua    random [CATEGORY]
SurahArg = Annotated[str, typer.Argument(metavar="SURAH", help="Surah number, 1-114 (see 'deen quran list').")]
CollectionArg = Annotated[
    str, typer.Argument(metavar="COLLECTION", help="bukhari, muslim, tirmidhi, nasai, abudawud or ibnmajah (see 'deen hadith list').")
]
CategoryArg = Annotated[str, typer.Argument(metavar="CATEGORY", help="Category number or shortcut (see 'deen dua list').")]


def deprecated(old: str, new: str) -> None:
    """One-line stderr notice for an old command name that still works."""
    err_console.print(f"[dim]'deen {old}' is now 'deen {new}' (the old name still works for now).[/dim]")
