import os

import typer
from rich.console import Console
from rich.table import Table

from py_invoices.config import get_settings
from py_invoices.constants import APP_DISPLAY_NAME

app = typer.Typer()
console = Console()


@app.command("show")
def show_config() -> None:
    """Show current configuration details."""
    settings = get_settings()

    table = Table(
        title=f"{APP_DISPLAY_NAME} Configuration",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Setting", style="dim")
    table.add_column("Value")

    # Backend settings
    table.add_row("Backend", settings.backend)
    if settings.database_url:
        # Simple masking just in case, though usually env var
        db_url = settings.database_url
        if "://" in db_url:
            scheme, rest = db_url.split("://", 1)
            table.add_row("Database URL", f"{scheme}://***")
        else:
            table.add_row("Database URL", "***")

    # Files backend settings
    table.add_row("Default File Format", settings.file_format)

    # Paths
    table.add_row("Output Directory", os.path.abspath(settings.output_dir))
    if settings.template_dir:
        table.add_row("Template Directory", os.path.abspath(settings.template_dir))
    else:
        table.add_row("Template Directory", "[italic]Default[/italic]")

    console.print(table)


@app.callback()
def main() -> None:
    """Manage configuration."""
    pass
