import typer
from rich.console import Console

from py_invoices.core.validator import UBLValidator

app = typer.Typer()
console = Console()

@app.command("invoice")
def validate_invoice(
    file_path: str = typer.Argument(..., help="Path to UBL XML invoice file to validate")
) -> None:
    """
    Validate a UBL 2.1 invoice XML file.

    Checks for mandatory fields and structure compliance.
    """
    result = UBLValidator.validate_file(file_path)

    for msg in result.messages:
        if msg.level == "error":
            console.print(f"[red]✗ {msg.text}[/red]")
        elif msg.level == "warning":
            console.print(f"[yellow]⚠ {msg.text}[/yellow]")
        elif msg.level == "success":
            console.print(f"[green]✓ {msg.text}[/green]")
        elif msg.level == "info":
            console.print(f"[blue]ℹ {msg.text}[/blue]")
        else:
            console.print(msg.text)

    if not result.success:
        raise typer.Exit(code=1)
