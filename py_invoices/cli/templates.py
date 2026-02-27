import os
from pathlib import Path

import typer
from rich.table import Table

from py_invoices.cli.utils import get_console
from py_invoices.config import get_settings

app = typer.Typer()
console = get_console()

@app.command("list")
def list_templates() -> None:
    """List available templates and their resolve paths."""
    settings = get_settings()

    # 1. Package templates
    import py_invoices
    package_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
    package_templates_dir = Path(package_dir) / "templates"

    # 2. User templates
    user_templates_dir = Path(settings.template_dir) if settings.template_dir else None

    table = Table(title="Available Templates")
    table.add_column("Template Name", style="cyan")
    table.add_column("Source", style="green")
    table.add_column("Full Path", style="dim")

    # Combine templates, respecting priority
    templates = {}

    # Packaged templates (lower priority)
    if package_templates_dir.exists():
        for f in package_templates_dir.iterdir():
            if f.is_file() and f.suffix == ".j2":
                templates[f.name] = ("Packaged", str(f.absolute()))

    # User templates (higher priority)
    if user_templates_dir and user_templates_dir.exists():
        for f in user_templates_dir.iterdir():
            if f.is_file() and f.suffix == ".j2":
                source = "User Override" if f.name in templates else "User"
                templates[f.name] = (source, str(f.absolute()))

    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        return

    for name, (source, path) in sorted(templates.items()):
        table.add_row(name, source, path)

    console.print(table)

    if user_templates_dir:
        console.print(f"\n[dim]User template directory: {user_templates_dir.absolute()}[/dim]")
    console.print(f"[dim]Packaged template directory: {package_templates_dir.absolute()}[/dim]")
