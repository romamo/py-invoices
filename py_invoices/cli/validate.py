import typer
from py_invoices.core.validator import UBLValidator

app = typer.Typer()

@app.command("invoice")
def validate_invoice(
    file_path: str = typer.Argument(..., help="Path to UBL XML invoice file to validate")
) -> None:
    """
    Validate a UBL 2.1 invoice XML file.
    
    Checks for mandatory fields and structure compliance.
    """
    success = UBLValidator.validate_file(file_path)
    if not success:
        raise typer.Exit(code=1)
