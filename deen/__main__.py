#!/usr/bin/env python3
"""deen-cli: Git-style Islamic productivity companion"""
import logging
import typer
from datetime import datetime
from .services.api import ApiService
from .database import commit_habit, get_recent_commits, get_today_prayer_status, get_db

from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.table import Table
import sys

from .config import DeenConfig
from .database import init_db, check_existing_data
from .services.location import LocationService
from .services.metadata import MetadataService
from .content import ContentEngine

app = typer.Typer(
    name="deen",
    help=(
        "[bold]deen-cli[/bold] \u2014 a git-style tracker for daily Islamic habits "
        "(prayers, Qur'an, dhikr), plus a spiritual-content lookup (ayah / hadith / dua).\n\n"
        "[dim]First run:[/dim] deen init\n"
        "[dim]Then:[/dim] deen status  \u00b7  deen commit  \u00b7  deen inspire\n\n"
        "[dim]Shell tab-completion (optional, not required to use deen-cli):[/dim]\n"
        "[dim]  --install-completion installs it for your current shell (bash/zsh/fish/etc.)[/dim]\n"
        "[dim]  --show-completion prints the completion script instead of installing it[/dim]"
    ),
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=False,  # bare `deen` shows a friendly dashboard instead (see main() below)
)
config_app = typer.Typer(
    name="config",
    help="View or change deen-cli settings (logging, caching, API endpoints).",
    rich_markup_mode="rich",
)
app.add_typer(config_app, name="config")
console = Console()

@app.command()
def init():
    """Initialize deen-cli with interactive configuration (API-driven, zero hardcoded values)"""
    config = DeenConfig()
    
    # Check existing data
    existing = check_existing_data()
    if existing["is_initialized"]:
        console.print("[yellow]⚠️  deen-cli is already initialized.[/yellow]")
        if not Confirm.ask("Overwrite existing configuration?", default=False):
            console.print("[green]✓[/green] Initialization skipped.")
            raise typer.Exit(0)
    
    console.print(Panel("[bold green]deen-cli Setup Wizard[/bold green]", expand=False))
    
    # Location detection
    console.print("\n[dim]📍 Detecting your location...[/dim]")
    location_service = LocationService(config)
    detected = location_service.get_current_location()
    
    location, latitude, longitude = None, None, None
    if detected:
        city, lat, lon = detected
        console.print(f"[green]✓[/green] Detected: [bold]{city}[/bold] ({lat:.4f}, {lon:.4f})")
        if Confirm.ask("Use this location?", default=True):
            location, latitude, longitude = city, lat, lon
    
    if not location:
        console.print("\n[dim]📍 Manual location entry[/dim]")
        query = Prompt.ask("[bold]City name[/bold]", default="London")
        result = location_service.search_location(query)
        if result:
            city, lat, lon = result
            console.print(f"[green]✓[/green] Found: [bold]{city}[/bold]")
            location, latitude, longitude = city, lat, lon
        else:
            console.print("[yellow]⚠️  Using London as fallback[/yellow]")
            location, latitude, longitude = "London", 51.5074, -0.1278
    
    # Fetch calculation methods with location hint
    console.print("\n[dim]🕌 Fetching prayer calculation methods...[/dim]")
    metadata = MetadataService(config)
    methods, used_offline_fallback = metadata.get_calculation_methods(location)

    if not methods:
        console.print("[red]✗ Could not load calculation methods (API unreachable and no offline data). Try again with a network connection.[/red]")
        raise typer.Exit(1)
    if used_offline_fallback:
        console.print("[yellow]⚠️  Aladhan API unreachable; using the bundled offline method list.[/yellow]")
    
    # Display methods table
    table = Table(title="Prayer Calculation Methods", show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", width=4, justify="right")
    table.add_column("Method", style="green", no_wrap=False)
    table.add_column("Region", style="dim", width=20)
    
    method_ids = []
    for m in methods:
        # Highlight default method with emoji
        is_default = any(r in location.lower() for r in m.get("is_default_for", []))
        id_display = f"{m['id']} {'⭐' if is_default else ''}"
        table.add_row(id_display, m["name"], m["region"])
        method_ids.append(m["id"])
    
    console.print(table)
    
    # Get smart default based on location
    smart_default = metadata.get_smart_default_method(location)
    console.print(f"\n[dim]💡 Smart default for {location}: Method {smart_default}[/dim]")
    
    method_id = Prompt.ask(
        "[bold]Select method ID[/bold]",
        choices=method_ids,
        default=smart_default
    )
    
    # Special handling for Method 99 (custom)
    if method_id == "99":
        console.print("\n[bold yellow]⚠️  Method 99: Custom Parameters[/bold yellow]")
        console.print("[dim]This advanced method lets you define custom angles for Fajr/Isha calculations.")
        console.print("Only use if you understand prayer time calculation parameters.")
        console.print("Most users should select a standard method (1-5) based on their region.[/dim]")
        if not Confirm.ask("Continue with custom method?", default=False):
            # Re-prompt for method selection excluding 99
            filtered_ids = [m for m in method_ids if m != "99"]
            method_id = Prompt.ask("[bold]Select standard method ID[/bold]", choices=filtered_ids, default=smart_default)
    
    # Fetch schools/madhabs
    console.print("\n[dim]📚 Fetching madhab options...[/dim]")
    schools = metadata.get_schools()
    school_ids = [s["id"] for s in schools]
    
    school_table = Table(title="Madhab (School of Thought)", show_header=True, header_style="bold")
    school_table.add_column("ID", style="cyan", width=4, justify="right")
    school_table.add_column("School", style="green")
    
    for s in schools:
        school_table.add_row(s["id"], s["name"])
    
    console.print(school_table)
    
    # Smart madhab default
    smart_school = metadata.get_smart_default_school(location)
    console.print(f"\n[dim]💡 Smart default for {location}: Madhab {smart_school}[/dim]")
    
    school_id = Prompt.ask(
        "[bold]Select madhab ID[/bold]",
        choices=school_ids,
        default=smart_school
    )
    
    # User name
    name = Prompt.ask("\n[bold]Your name[/bold]", default="Brother/Sister")
    
    # Save config - ensure proper types (no None values)
    config.set("user.name", name)
    config.set("user.location", location)
    if latitude is not None:
        config.set("user.latitude", float(latitude))
    if longitude is not None:
        config.set("user.longitude", float(longitude))
    config.set("prayer.calculation_method", str(method_id))
    config.set("prayer.school", str(school_id))
    
    # Init DB
    console.print("\n[dim]💾 Initializing database...[/dim]")
    init_db()
    
    # Success
    selected_method = next((m["name"] for m in methods if m["id"] == method_id), "Unknown")
    selected_school = next((s["name"] for s in schools if s["id"] == school_id), "Unknown")
    
    console.print()
    console.print(Panel(
        f"[green]✓[/green] Setup complete!\n\n"
        f"[bold]Name:[/bold] {name}\n"
        f"[bold]Location:[/bold] {location}\n"
        f"[bold]Prayer Method:[/bold] {selected_method}\n"
        f"[bold]Madhab:[/bold] {selected_school}\n\n"
        f"[dim]Config: {config.config_path}[/dim]",
        title="🎉 deen-cli Initialized",
        border_style="green"
    ))
    
    console.print("\n[bold]Next:[/bold] [cyan]deen inspire --type hadith --mood stressed[/cyan]")

@app.command()
def inspire(
    content_type: str = typer.Option("hadith", "--type", "-t", help="Content type: ayah, hadith, dua"),
    mood: str = typer.Option(None, "--mood", "-m", help="Emotional state: stressed, anxious, grateful, sad, angry, lonely, tired, doubtful"),
    category: str = typer.Option(
        None, "--category", "-c",
        help=(
            "Scopes --list (and, for dua, also scopes the random pick): "
            "for --type dua, a category number/shortcut (run 'deen categories'); "
            "for --type hadith, a collection name (bukhari, muslim, tirmidhi, nasai, abudawud, ibnmajah); "
            "for --type ayah, a surah number 1-114 (run 'deen surahs')."
        ),
    ),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Get fresh content"),
    list_all: bool = typer.Option(
        False, "--list", "-l",
        help="Show ALL items for --category in a scrollable pager (arrow keys/space to scroll, '/' to search, 'q' to quit) instead of one random pick. Requires --category.",
    ),
):
    """Get spiritual inspiration (API-driven with authenticated fallbacks)"""
    config = DeenConfig()
    if not config.is_initialized:
        console.print("[red]✗ Run 'deen init' first[/red]")
        raise typer.Exit(1)

    if list_all:
        if not category:
            hint = {
                "dua": "a category, e.g. -c morning (see 'deen categories')",
                "hadith": "a collection, e.g. -c bukhari (bukhari, muslim, tirmidhi, nasai, abudawud, ibnmajah)",
                "ayah": "a surah number, e.g. -c 36 (see 'deen surahs')",
            }.get(content_type, "a --category")
            console.print(f"[red]✗ --list requires --category: {hint}[/red]")
            raise typer.Exit(1)

        try:
            engine = ContentEngine()
            if content_type == "dua":
                engine.display_dua_list(category)
            elif content_type == "hadith":
                engine.display_hadith_list(category.strip().lower())
            elif content_type == "ayah":
                engine.display_ayah_list(category)
            else:
                console.print(f"[red]✗ Unknown --type '{content_type}'. Use ayah, hadith, or dua.[/red]")
                raise typer.Exit(1)
        except typer.Exit:
            raise
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
            raise typer.Exit(1)
        return

    try:
        engine = ContentEngine()
        engine.display_content(
            content_type=content_type,
            category=category,
            force_fresh=fresh,
            mood=mood
        )
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def categories():
    """List dua categories for `deen inspire --type dua --category ...`.

    Fetched live from the Hisn al-Muslim collection (132 categories) so
    this always reflects what's actually available, instead of a
    hardcoded short list.
    """
    config = DeenConfig()
    api = ApiService(config)

    console.print("[dim]📚 Fetching dua categories...[/dim]")
    data, is_offline_fallback = api.fetch_dua_categories()

    if is_offline_fallback:
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
    elif not is_offline_fallback:
        console.print("[dim]No category list returned by the API.[/dim]")

    console.print("\n[dim]💡 Leave --category blank for a fully random dua from the whole collection.[/dim]")


@app.command()
def surahs():
    """List all 114 surahs (chapters) for `deen inspire --type ayah --list --category <number>`.

    Fetched live from the Quran API so names/ayah counts are always
    accurate. If it's unreachable, surah *numbers* 1-114 still work with
    --list -- you just won't see the names here without a connection.
    """
    config = DeenConfig()
    api = ApiService(config)

    console.print("[dim]📖 Fetching surah list...[/dim]")
    surah_list, is_offline_fallback = api.fetch_surah_list()

    if is_offline_fallback or not surah_list:
        console.print(
            "[yellow]⚠️  Quran API unreachable and nothing cached, so surah names aren't available "
            "right now.[/yellow]\n"
            "[dim]Surah numbers 1-114 still work directly, e.g.: "
            "deen inspire --type ayah --list --category 36[/dim]"
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
            s.get("name", ""),
            s.get("englishName", "?"),
            s.get("englishNameTranslation", ""),
            str(s.get("numberOfAyahs", "?")),
        )
    console.print(table)
    console.print("\n[dim]💡 deen inspire --type ayah --list --category <#> to page through a whole surah.[/dim]")


@app.command()
def status():
    """Show prayer times with completion markers and next prayer countdown"""
    config = DeenConfig()
    if not config.is_initialized:
        console.print("[red]✗ Run 'deen init' first[/red]")
        raise typer.Exit(1)
    
    try:
        # Get location from config
        lat = config.get("user.latitude")
        lon = config.get("user.longitude")
        if not lat or not lon:
            console.print("[yellow]⚠️  Location not set. Run 'deen init' to configure.[/yellow]")
            raise typer.Exit(1)
        
        # Fetch prayer times (cache -> live -> stale cache; never fabricated)
        api = ApiService(config)
        today = datetime.now().strftime("%Y-%m-%d")
        prayers, is_stale = api.fetch_prayer_times(float(lat), float(lon), today)

        if not prayers:
            console.print(
                "[red]✗ Could not get prayer times: the Aladhan API is unreachable "
                "and nothing is cached yet.[/red]\n"
                "[dim]Connect to the internet and try again.[/dim]"
            )
            raise typer.Exit(1)
        if is_stale:
            console.print("[yellow]⚠️  API unreachable — showing the last cached prayer times (may be outdated).[/yellow]")
        
        # Get today's prayer completion status
        prayer_status = get_today_prayer_status()
        
        # Calculate next prayer
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        next_prayer = None
        for prayer, time_str in prayers.items():
            if prayer not in ["Sunrise"]:  # Skip non-obligatory prayers
                if time_str > current_time:
                    next_prayer = (prayer, time_str)
                    break
        
        # Build prayer table with completion markers
        from rich.table import Table
        table = Table(show_header=False, box=None)
        table.add_column(style="cyan", width=12)
        table.add_column(style="green", justify="right", width=8)
        
        for prayer, time_str in prayers.items():
            # Skip non-obligatory prayers in main display
            if prayer == "Sunrise":
                continue
            
            # Check completion status
            is_completed = prayer_status.get(prayer, False)
            status_icon = "[bold green]✓[/bold green]" if is_completed else "[dim]○[/dim]"
            
            # Determine styling
            is_next = next_prayer and prayer == next_prayer[0]
            prayer_display = f"[bold]{prayer} {status_icon}[/bold]" if is_next else f"{prayer} {status_icon}"
            time_display = f"[bold green]{time_str}[/bold green]" if is_next else time_str
            
            table.add_row(prayer_display, time_display)
        
        # Show countdown if next prayer exists
        if next_prayer:
            next_time = datetime.strptime(next_prayer[1], "%H:%M")
            now_time = datetime.strptime(current_time, "%H:%M")
            if next_time < now_time:
                next_time = next_time.replace(day=next_time.day + 1)
            delta = next_time - now_time
            countdown = f"{delta.seconds // 3600:02d}:{(delta.seconds % 3600) // 60:02d}:{delta.seconds % 60:02d}"
            console.print(f"\n[bold]Next:[/bold] {next_prayer[0]} in [green]{countdown}[/green]")
        
        # Display panel
        console.print(Panel(
            table,
            title=f"🕌 Prayer Times • {config.get('user.location')}",
            border_style="green",
            expand=False
        ))
        
        console.print("\n[dim]Commands:[/dim]")
        console.print("  • [cyan]deen commit -t salah -m 'on time'[/cyan] → Log current prayer")
        console.print("  • [cyan]deen commit -t salah -m 'Dhuhr'[/cyan] → Log specific prayer")
        console.print("  • [cyan]deen log[/cyan] → View recent activity")
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def commit(
    habit_type: str = typer.Option("quran", "--type", "-t", help="Habit type: salah, quran, dhikr, fasting, custom"),
    message: str = typer.Option(..., "--message", "-m", help="Commit message (e.g., 'on time', 'Juz 1')"),
    makeup: bool = typer.Option(False, "--makeup", help="Mark as makeup prayer/habit")
):
    """Log a spiritual habit completion (Git-style)"""
    config = DeenConfig()
    if not config.is_initialized:
        console.print("[red]✗ Run 'deen init' first[/red]")
        raise typer.Exit(1)
    try:
        # For salah type, we detect actual prayer from message
        if habit_type.lower() == "salah":
            habit_name = "salah"  # Will be resolved in commit_habit()
        else:
            # Map other types to habit names
            habit_map = {
                "quran": "Quran",
                "dhikr": "Dhikr",
                "fasting": "Fasting"
            }
            habit_name = habit_map.get(habit_type.lower(), habit_type.capitalize())
        
        commit_id = commit_habit(habit_name, message, makeup, config=config)
        
        # Get actual habit name from DB to show correct icon
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT h.name FROM commits c
                JOIN habits h ON c.habit_id = h.id
                WHERE c.id = ?
            """, (commit_id,))
            actual_name = cursor.fetchone()[0]
        
        # Set icon based on actual habit
        if actual_name in ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]:
            icon = "🕌"
        elif actual_name == "Quran":
            icon = "📖"
        elif actual_name == "Dhikr":
            icon = "🤲"
        else:
            icon = "✨"
        
        makeup_badge = "[yellow](makeup)[/yellow]" if makeup else ""
        console.print(f"[green]✓[/green] {icon} {actual_name} committed! ID: [bold]{commit_id}[/bold] {makeup_badge}")
        console.print(f"   [dim]Note:[/dim] {message}")
    except ValueError as ve:
        console.print(f"[yellow]⚠️  {ve}[/yellow]")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]✗ Commit failed: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def log(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to show")
):
    """View habit history"""
    config = DeenConfig()
    if not config.is_initialized:
        console.print("[red]✗ Run 'deen init' first[/red]")
        raise typer.Exit(1)
    
    try:
        commits = get_recent_commits(days=days)
        
        if not commits:
            console.print("[yellow]No habits logged yet. Run 'deen commit' to start![/yellow]")
            return
        
        from rich.table import Table
        from rich.markup import escape
        from rich import box
        
        # 1. Removed "Type" column from title and initialization
        table = Table(title=f"Recent Habits (Last {days} days)", box=box.ROUNDED)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Time", style="dim")
        table.add_column("Habit", style="green")
        table.add_column("Message", overflow="fold")
        # --- Column Deleted Here ---
        
        for c in commits:
            try:
                timestamp = datetime.fromisoformat(c[1])
            except (ValueError, TypeError):
                timestamp_str = str(c[1]).split('.')[0].split('+')[0]
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            
            time_str = timestamp.strftime("%Y-%m-%d %H:%M")
            
            # If it's a makeup, we can append (M) to the habit name instead 
            # so you don't lose the info even without the Type column
            habit_name = f"{c[2]} [yellow](M)[/yellow]" if c[4] else str(c[2])
            
            # 2. Removed the last argument (c[5] or makeup_badge) from add_row
            table.add_row(
                str(c[0]),
                time_str,
                escape(habit_name), # Combined Name + Makeup badge
                escape(str(c[3]))   # Note/message
            )
        
        console.print(table)
        
    except typer.Exit:
        raise
    except Exception as e:
        logging.getLogger("deen.cli").exception("Error fetching log")
        console.print(f"[red]✗ Error fetching log: {e}[/red]")
        raise typer.Exit(1)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """deen-cli: Git-style Islamic productivity companion"""
    if ctx.invoked_subcommand is None:
        config = DeenConfig()
        if not config.is_initialized:
            console.print("[yellow]⚠️  Run 'deen init' to get started[/yellow]")
            raise typer.Exit(1)
        
        console.print("[bold green]deen-cli[/bold green] — Version Control for Your Deeds")
        console.print("\n[bold]Commands:[/bold]")
        console.print("  init        → Setup configuration")
        console.print("  status      → Prayer times & habit summary")
        console.print("  commit      → Log habit completion")
        console.print("  log         → View habit history")
        console.print("  inspire     → Get spiritual content (ayah / hadith / dua)")
        console.print("  categories  → List available dua categories")
        console.print("  surahs      → List all 114 surahs")
        console.print("  config      → View/change settings (logging, cache, endpoints)")
        console.print("\n[dim]'deen COMMAND --help' for details[/dim]")


# --------------------------------------------------------------------------
# `deen config` — inspect/change settings without hand-editing config.toml.
# --------------------------------------------------------------------------

_KNOWN_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _parse_config_value(raw: str):
    """Coerce a CLI string into bool/int/float where unambiguous, else leave as str."""
    low = raw.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


@config_app.command("show")
def config_show():
    """Show all current settings and where deen-cli stores its files."""
    config = DeenConfig()
    from .cache import get_cache_dir

    table = Table(title="deen-cli configuration", show_lines=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    def walk(prefix: str, d: dict):
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                walk(path, v)
            else:
                table.add_row(path, str(v))

    walk("", config._config)
    console.print(table)

    console.print("\n[bold]File locations[/bold]")
    console.print(f"  Config:  {config.config_path}")
    console.print(f"  Data DB: {config.config_dir / 'data.db'}")
    console.print(f"  Cache:   {get_cache_dir()}")
    console.print(f"  Logs:    {config.logs_dir / 'deen.log'}")
    console.print(
        f"\n[dim]💡 Change logging verbosity with: "
        f"deen config set logging.level DEBUG[/dim]"
    )


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Dot-notation config key, e.g. logging.level or cache.enable"),
    value: str = typer.Argument(..., help="New value. true/false and numbers are auto-detected."),
):
    """Set a config value (e.g. logging level, cache on/off, API endpoints)."""
    config = DeenConfig()

    if key == "logging.level" and value.upper() not in _KNOWN_LOG_LEVELS:
        console.print(f"[red]✗ logging.level must be one of: {', '.join(sorted(_KNOWN_LOG_LEVELS))}[/red]")
        raise typer.Exit(1)

    parsed = _parse_config_value(value) if key != "logging.level" else value.upper()
    config.set(key, parsed)
    console.print(f"[green]✓[/green] {key} = {parsed}")
    if key.startswith("logging."):
        console.print("[dim]Takes effect on the next deen command (logging is set up once per run).[/dim]")


@config_app.command("path")
def config_path():
    """Print where deen-cli's config, database, cache, and logs live."""
    config = DeenConfig()
    from .cache import get_cache_dir

    console.print(f"Config:  {config.config_path}")
    console.print(f"Data DB: {config.config_dir / 'data.db'}")
    console.print(f"Cache:   {get_cache_dir()}")
    console.print(f"Logs:    {config.logs_dir / 'deen.log'}")


if __name__ == "__main__":
    app()