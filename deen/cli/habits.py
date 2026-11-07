"""Habit commands: status (prayer times), commit, log."""
from __future__ import annotations

from datetime import datetime

import typer
from rich import box
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from ..database import commit_habit, get_commit_habit_name, get_recent_commits, get_today_prayer_status
from ..errors import UserError
from ..services.api import ApiService
from ..ui import console
from ._common import get_config
from .app import PANEL_HABITS, command

PRAYERS_SHOWN = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")  # Sunrise isn't a prayer
_HABIT_NAMES = {"quran": "Quran", "dhikr": "Dhikr", "fasting": "Fasting"}
_PRAYER_NAMES = set(PRAYERS_SHOWN)


def _habit_icon(name: str) -> str:
    if name in _PRAYER_NAMES:
        return "🕌"
    return {"Quran": "📖", "Dhikr": "🤲"}.get(name, "✨")


# --------------------------------------------------------------------------
@command(panel=PANEL_HABITS)
def status():
    """Show prayer times with completion markers and next prayer countdown"""
    config = get_config()
    lat, lon = config.get("user.latitude"), config.get("user.longitude")
    if not lat or not lon:
        raise UserError("Location not set. Run 'deen init' to configure.")

    today = datetime.now().strftime("%Y-%m-%d")
    fetched = ApiService(config).fetch_prayer_times(float(lat), float(lon), today)
    prayers = fetched.data
    if not prayers:
        console.print(
            "[red]✗ Could not get prayer times: the Aladhan API is unreachable "
            "and nothing is cached yet.[/red]\n"
            "[dim]Connect to the internet and try again.[/dim]"
        )
        raise typer.Exit(1)
    if fetched.is_stale:
        console.print("[yellow]⚠️  API unreachable — showing the last cached prayer times (may be outdated).[/yellow]")

    prayer_status = get_today_prayer_status()
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    shown = [(name, t) for name, t in prayers.items() if name in PRAYERS_SHOWN]
    next_prayer = next(((name, t) for name, t in shown if t > current_time), None)

    table = Table(show_header=False, box=None)
    table.add_column(style="cyan", width=12)
    table.add_column(style="green", justify="right", width=8)
    for name, time_str in shown:
        icon = "[bold green]✓[/bold green]" if prayer_status.get(name, False) else "[dim]○[/dim]"
        is_next = next_prayer is not None and name == next_prayer[0]
        table.add_row(
            f"[bold]{name} {icon}[/bold]" if is_next else f"{name} {icon}",
            f"[bold green]{time_str}[/bold green]" if is_next else time_str,
        )

    if next_prayer:
        delta = datetime.strptime(next_prayer[1], "%H:%M") - datetime.strptime(current_time, "%H:%M")
        secs = delta.seconds
        countdown = f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"
        console.print(f"\n[bold]Next:[/bold] {next_prayer[0]} in [green]{countdown}[/green]")

    console.print(Panel(
        table,
        title=f"🕌 Prayer Times • {config.get('user.location')}",
        border_style="green",
        expand=False,
    ))
    console.print("\n[dim]Commands:[/dim]")
    console.print("  • [cyan]deen commit -t salah -m 'on time'[/cyan] → Log current prayer")
    console.print("  • [cyan]deen commit -t salah -m 'Dhuhr'[/cyan] → Log specific prayer")
    console.print("  • [cyan]deen log[/cyan] → View recent activity")


# --------------------------------------------------------------------------
@command(panel=PANEL_HABITS)
def commit(
    habit_type: str = typer.Option("quran", "--type", "-t", help="Habit type: salah, quran, dhikr, fasting, custom"),
    message: str = typer.Option(..., "--message", "-m", help="Commit message (e.g., 'on time', 'Juz 1')"),
    makeup: bool = typer.Option(False, "--makeup", help="Mark as makeup prayer/habit"),
):
    """Log a spiritual habit completion (Git-style)"""
    key = habit_type.lower()
    # "salah" is resolved to the actual prayer inside commit_habit().
    habit_name = "salah" if key == "salah" else _HABIT_NAMES.get(key, habit_type.capitalize())

    config = get_config()
    commit_id = commit_habit(
        habit_name,
        message,
        makeup,
        current_prayer=ApiService(config).current_prayer,
        confirm_overwrite=lambda prayer: Confirm.ask(
            f"[yellow]⚠️  {prayer} already logged. Update existing record?[/yellow]"
        ),
    )
    actual_name = get_commit_habit_name(commit_id) or habit_name

    makeup_badge = "[yellow](makeup)[/yellow]" if makeup else ""
    console.print(
        f"[green]✓[/green] {_habit_icon(actual_name)} {actual_name} committed! "
        f"ID: [bold]{commit_id}[/bold] {makeup_badge}"
    )
    console.print(f"   [dim]Note:[/dim] {message}")


# --------------------------------------------------------------------------
def _parse_timestamp(raw) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        cleaned = str(raw).split(".")[0].split("+")[0]
        return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")


@command(panel=PANEL_HABITS)
def log(days: int = typer.Option(7, "--days", "-d", help="Number of days to show")):
    """View habit history"""
    commits = get_recent_commits(days=days)
    if not commits:
        console.print("[yellow]No habits logged yet. Run 'deen commit' to start![/yellow]")
        return

    table = Table(title=f"Recent Habits (Last {days} days)", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Time", style="dim")
    table.add_column("Habit", style="green")
    table.add_column("Message", overflow="fold")

    for c in commits:
        habit = escape(str(c[2])) + (" [yellow](M)[/yellow]" if c[4] else "")  # (M) = makeup
        table.add_row(
            str(c[0]),
            _parse_timestamp(c[1]).strftime("%Y-%m-%d %H:%M"),
            habit,
            escape(str(c[3])),
        )
    console.print(table)
