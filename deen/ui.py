"""The shared Rich consoles. Import these; don't create another ``Console()``."""
from rich.console import Console

console = Console()
err_console = Console(stderr=True)
