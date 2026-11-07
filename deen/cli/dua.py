"""``deen dua``: list | read | random."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ..content import ContentEngine
from ..errors import UserError
from ..services.api import ApiService
from ..services.dua import search_dua_categories
from ..ui import console
from ._common import CategoryArg, Fresh, Page, PerPage, get_config
from .app import command, dua_app


def resolve_category(query: str) -> str:
    """Turn what the user typed into something the API understands.

    Numbers and the API's named shortcuts (morning, forgiveness, ...) pass straight
    through. Anything else is looked up in the 132 chapter titles, so
    `deen dua read istikhara` works even though the API has no such shortcut.
    One match -> use it; several -> list them and ask; none -> say so.
    """
    q = query.strip()
    if q.isdigit():
        return q
    fetched = ApiService(get_config()).fetch_dua_categories()
    shortcuts = [x.lower() for x in fetched.data.get("shortcuts", [])]
    categories = fetched.data.get("categories", [])
    if q.lower() in shortcuts or not categories:
        return q  # known shortcut, or offline (nothing to search): let the normal path handle it

    matches = search_dua_categories(categories, q)
    if len(matches) == 1:
        m = matches[0]
        console.print(f"[dim]→ chapter {m['number']}: {m['en']}[/dim]")
        return str(m["number"])
    if not matches:
        raise UserError(f"No dua category matches '{query}'. Try 'deen dua list --search <word>'.")
    lines = "\n".join(f"  {m['number']:>3}  {m['en']}" for m in matches[:15])
    more = f"\n  …and {len(matches) - 15} more" if len(matches) > 15 else ""
    raise UserError(f"'{query}' matches {len(matches)} categories; pick one by number:\n{lines}{more}")


def show_dua_categories(search: Optional[str] = None) -> None:
    console.print("[dim]📚 Fetching dua categories...[/dim]")
    fetched = ApiService(get_config()).fetch_dua_categories()
    data = fetched.data

    if fetched.is_offline:
        console.print("[yellow]⚠️  Dua API unreachable and nothing cached; showing a minimal offline shortcut list.[/yellow]\n")

    shortcuts = data.get("shortcuts", [])
    categories = data.get("categories", [])

    if search:
        categories = search_dua_categories(categories, search)
        if not categories:
            console.print(f"[yellow]No category matches '{search}'.[/yellow] [dim]Try a shorter word, or run 'deen dua list'.[/dim]")
            return
    elif shortcuts:
        console.print("[bold]Named shortcuts[/bold] (e.g. deen dua read morning):")
        console.print("  " + ", ".join(shortcuts))
        console.print()

    if categories:
        title = f"{len(categories)} categories matching '{search}'" if search else f"All {len(categories)} categories (use a number, a shortcut, or part of a title)"
        table = Table(title=title)
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Category", style="white")
        table.add_column("Duas", style="dim", justify="right")
        for c in categories:
            table.add_row(str(c.get("number", "?")), c.get("en", "Unknown"), str(c.get("count", "?")))
        console.print(table)
    elif not fetched.is_offline:
        console.print("[dim]No category list returned by the API.[/dim]")

    console.print("\n[dim]💡 deen dua read <category> to read one; deen dua random for a random dua.[/dim]")


def show_duas(category: str, page: int, per_page: int) -> None:
    ContentEngine(get_config()).display_dua_list(resolve_category(category), page=page, per_page=per_page)


@command("list", target=dua_app)
def dua_list(
    search: Optional[str] = typer.Option(
        None, "--search", "-s", help="Only categories whose title matches, e.g. forgiveness, istikhara, travel, sleep."
    ),
):
    """List dua categories (Hisn al-Muslim) and their named shortcuts.

    Fetched live, so this always reflects what's actually available.
    Use --search to find one by name.
    """
    show_dua_categories(search)


@command("read", target=dua_app)
def dua_read(category: CategoryArg, page: Page = 1, per_page: PerPage = 10):
    """Read a dua category ten items at a time.

    CATEGORY can be a number (`26`), a shortcut (`morning`, `forgiveness`) or part of a
    title (`istikhara`, `sleep`). Use --page / --per-page to move.
    """
    show_duas(category, page, per_page)


@command("random", target=dua_app)
def dua_random(
    category: Optional[str] = typer.Argument(None, metavar="[CATEGORY]", help="Pick only from this category."),
    fresh: Fresh = False,
):
    """Show one random dua, optionally from one category (e.g. `deen dua random morning`)."""
    scope = resolve_category(category) if category else None
    ContentEngine(get_config()).display_content(content_type="dua", category=scope, force_fresh=fresh)
