import typer
from rich.table import Table

from py_invoices.cli.utils import get_console
from py_invoices.config import get_settings
from py_invoices.operations.config import template_catalog

app = typer.Typer()
console = get_console()


@app.command("list")
def list_templates() -> None:
    """List available templates and their resolve paths."""
    catalog = template_catalog(get_settings())
    if not catalog.templates:
        console.print("[yellow]No templates found.[/yellow]")
        return

    table = Table(title="Available Templates")
    table.add_column("Template Name", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Full Path", style="dim")
    for entry in catalog.templates:
        table.add_row(entry.name, entry.source, entry.path)
    console.print(table)

    if catalog.user_dir:
        console.print(f"\n[dim]User template directory: {catalog.user_dir.absolute()}[/dim]")
    console.print(f"[dim]Packaged template directory: {catalog.package_dir.absolute()}[/dim]")
