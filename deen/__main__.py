#!/usr/bin/env python3
"""deen-cli: Git-style Islamic productivity companion - ZERO hardcoded religious content"""
import typer
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
    help="✨ Git-style Islamic productivity companion",
    add_completion=True,
    rich_markup_mode="rich"
)
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
    methods = metadata.get_calculation_methods(location)
    
    if not methods:
        console.print("[yellow]⚠️  Could not fetch methods. Using regional defaults.[/yellow]")
        # Create minimal defaults based on location
        default_method_id = metadata.get_smart_default_method(location)
        methods = [
            {"id": "1", "name": "University of Islamic Sciences, Karachi", "region": "🇵🇰 Pakistan", "is_default_for": ["pakistan"]},
            {"id": "2", "name": "Islamic Society of North America (ISNA)", "region": "🇺🇸 North America", "is_default_for": ["usa", "canada"]},
            {"id": "3", "name": "Muslim World League", "region": "🌍 Global", "is_default_for": ["global"]},
            {"id": "4", "name": "Umm Al-Qura University, Makkah", "region": "🇸🇦 Saudi Arabia", "is_default_for": ["saudi arabia"]},
            {"id": "5", "name": "Egyptian General Authority", "region": "🇪🇬 Egypt", "is_default_for": ["egypt"]}
        ]
        # Sort with location-relevant method first
        methods.sort(key=lambda x: 0 if any(r in location.lower() for r in x["is_default_for"]) else 1)
    
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
    content_type: str = typer.Option("hadith", "--type", "-t", help="Content type: ayah, hadith"),
    mood: str = typer.Option(None, "--mood", "-m", help="Emotional state (API-driven content)"),
    fresh: bool = typer.Option(False, "--fresh", "-f", help="Get fresh content")
):
    """Get spiritual inspiration (100% API-driven, zero hardcoded content)"""
    config = DeenConfig()
    if not config.is_initialized:
        console.print("[red]✗ Run 'deen init' first[/red]")
        raise typer.Exit(1)
    
    try:
        engine = ContentEngine()
        engine.display_content(content_type=content_type, force_fresh=fresh, mood=mood)
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]", err=True)
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
        console.print("  init     → Setup configuration")
        console.print("  inspire  → Get spiritual content")
        console.print("\n[dim]'deen COMMAND --help' for details[/dim]")

if __name__ == "__main__":
    app()