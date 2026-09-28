import typer
from rich.console import Console
from rich.markup import escape

from py_invoices.core.validator import MessageLevel, UBLValidator

app = typer.Typer()
console = Console()


@app.command("invoice")
def validate_invoice(
    file_path: str = typer.Argument(..., help="Path to UBL XML invoice file to validate"),
) -> None:
    """
    Validate a UBL 2.1 invoice or credit note XML file.

    Checks for mandatory fields and structure compliance.
    """
    result = UBLValidator.validate_file(file_path)

    styles = {
        MessageLevel.ERROR: "[red]✗",
        MessageLevel.WARNING: "[yellow]⚠",
        MessageLevel.SUCCESS: "[green]✓",
        MessageLevel.INFO: "[blue]ℹ",  # noqa: RUF001 (information symbol, not a letter)
    }
    for msg in result.messages:
        console.print(f"{styles[msg.level]} {escape(msg.text)}[/]")

    if not result.success:
        raise typer.Exit(code=1)
