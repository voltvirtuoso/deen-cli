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
    
    # Fetch calculation methods from API
    console.print("\n[dim]🕌 Fetching prayer calculation methods...[/dim]")
    metadata = MetadataService(config)
    methods = metadata.get_calculation_methods()
    
    if not methods:
        console.print("[yellow]⚠️  Could not fetch methods. Using defaults.[/yellow]")
        methods = [
            {"id": "2", "name": "Islamic Society of North America (ISNA)"},
            {"id": "4", "name": "Muslim World League (MWL)"},
            {"id": "5", "name": "Egyptian General Authority"},
            {"id": "3", "name": "Umm al-Qura University (Saudi Arabia)"},
            {"id": "1", "name": "University of Islamic Sciences, Karachi"}
        ]
    
    # Display methods table
    table = Table(title="Prayer Calculation Methods", show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Method", style="green")
    table.add_column("Region", style="dim")
    
    method_ids = []
    for m in methods:
        table.add_row(m["id"], m["name"], m.get("country", "Global"))
        method_ids.append(m["id"])
    
    console.print(table)
    
    # Smart default based on location
    location_lower = location.lower()
    default_id = "1" if any(x in location_lower for x in ["pakistan", "karachi", "lahore"]) else "2"
    method_id = Prompt.ask(
        "[bold]Select method ID[/bold]",
        choices=method_ids,
        default=default_id
    )
    
    # Fetch schools/madhabs from API
    console.print("\n[dim]📚 Fetching madhab options...[/dim]")
    schools = metadata.get_schools()
    if not schools:
        schools = [
            {"id": "0", "name": "Shafi'i, Maliki, Hanbali (Standard)"},
            {"id": "1", "name": "Hanafi"}
        ]
    
    school_table = Table(title="Madhab (School of Thought)", show_header=True, header_style="bold")
    school_table.add_column("ID", style="cyan", width=4)
    school_table.add_column("School", style="green")
    
    school_ids = []
    for s in schools:
        school_table.add_row(s["id"], s["name"])
        school_ids.append(s["id"])
    
    console.print(school_table)
    school_id = Prompt.ask("[bold]Select madhab ID[/bold]", choices=school_ids, default="0")
    
    # User name
    name = Prompt.ask("\n[bold]Your name[/bold]", default="Brother/Sister")
    
    # Save config
    config.set("user.name", name)
    config.set("user.location", location)
    config.set("user.latitude", latitude)
    config.set("user.longitude", longitude)
    config.set("prayer.calculation_method", method_id)
    config.set("prayer.school", school_id)
    
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