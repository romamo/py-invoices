import typer
from rich.console import Console
from rich.table import Table

from py_invoices.config import get_settings
from py_invoices.constants import APP_DISPLAY_NAME
from py_invoices.operations.config import settings_overview

app = typer.Typer()
console = Console()


@app.command("show")
def show_config() -> None:
    """Show current configuration details."""
    overview = settings_overview(get_settings())

    table = Table(
        title=f"{APP_DISPLAY_NAME} Configuration",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Setting", style="dim")
    table.add_column("Value")
    table.add_row("Backend", overview.backend)
    if overview.masked_database_url:
        table.add_row("Database URL", overview.masked_database_url)
    table.add_row("Default File Format", overview.file_format)
    table.add_row("Output Directory", overview.output_dir)
    table.add_row("Template Directory", overview.template_dir or "[italic]Default[/italic]")
    console.print(table)


@app.callback()
def main() -> None:
    """Manage configuration."""
    pass
