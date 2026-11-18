import typer
from rich.console import Console
from rich.markup import escape

from py_invoices.cli.utils import get_factory
from py_invoices.core.validator import MessageLevel, UBLValidator
from py_invoices.operations.integrity import Finding, check_stored_invoices

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


@app.command("data")
def validate_data(
    seal: bool = typer.Option(
        False, help="Record a hash for invoices issued before hashing existed (audited)"
    ),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """
    Check that no issued invoice changed since it was issued.

    Recomputes each issued invoice's content hash; exits 1 if any differs.
    """
    report = check_stored_invoices(get_factory(backend), seal=seal)
    styles = {
        Finding.TAMPERED: "[red]✗",
        Finding.UNSEALED: "[yellow]⚠",
        Finding.SEALED: "[blue]ℹ",  # noqa: RUF001 (information symbol, not a letter)
    }
    for finding in report.findings:
        console.print(
            f"{styles[finding.finding]} {escape(finding.number)}: "
            f"{finding.finding.value}, {escape(finding.detail)}[/]"
        )
    unsealed = sum(f.finding is Finding.UNSEALED for f in report.findings)
    if unsealed:
        console.print(f"[yellow]{unsealed} issued invoice(s) have no hash; --seal records one[/]")
    console.print(f"Checked {report.checked} issued invoice(s), skipped {report.drafts} draft(s)")
    if not report.ok:
        raise typer.Exit(code=1)
    console.print("[green]✓ No issued invoice changed[/]")
