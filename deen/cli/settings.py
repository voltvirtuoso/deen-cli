"""``deen config``: inspect or change settings without hand-editing config.toml."""
from __future__ import annotations

import typer
from rich.table import Table

from ..cache import get_cache_dir
from ..errors import UserError
from ..ui import console
from ._common import get_config
from .app import command, config_app

KNOWN_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


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


def _print_locations(config) -> None:
    console.print(f"Config:  {config.config_path}")
    console.print(f"Data DB: {config.config_dir / 'data.db'}")
    console.print(f"Cache:   {get_cache_dir()}")
    console.print(f"Logs:    {config.logs_dir / 'deen.log'}")


# Config commands work before `deen init` (they're how you inspect a fresh install).
@command("show", requires_init=False, target=config_app)
def config_show():
    """Show all current settings and where deen-cli stores its files."""
    config = get_config()
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
    _print_locations(config)
    console.print(
        "\n[dim]💡 Change logging verbosity with: deen config set logging.level DEBUG[/dim]"
    )


@command("set", requires_init=False, target=config_app)
def config_set(
    key: str = typer.Argument(..., help="Dot-notation config key, e.g. logging.level or cache.enable"),
    value: str = typer.Argument(..., help="New value. true/false and numbers are auto-detected."),
):
    """Set a config value (e.g. logging level, cache on/off, API endpoints)."""
    if key == "logging.level":
        if value.upper() not in KNOWN_LOG_LEVELS:
            raise UserError(f"logging.level must be one of: {', '.join(sorted(KNOWN_LOG_LEVELS))}")
        parsed = value.upper()
    else:
        parsed = _parse_config_value(value)

    get_config().set(key, parsed)
    console.print(f"[green]✓[/green] {key} = {parsed}")
    if key.startswith("logging."):
        console.print("[dim]Takes effect on the next deen command (logging is set up once per run).[/dim]")


@command("path", requires_init=False, target=config_app)
def config_path():
    """Print where deen-cli's config, database, cache, and logs live."""
    _print_locations(get_config())
