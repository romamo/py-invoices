import typer
from pydantic_invoices.schemas import InvoiceType
from rich.table import Table

from py_invoices.cli.utils import cli_errors, get_console, get_factory
from py_invoices.operations import credit_notes as ops

app = typer.Typer()
console = get_console()


@app.command("create")
def create_credit_note(
    invoice_number: str = typer.Argument(..., help="Original Invoice Number"),
    reason: str = typer.Option(..., help="Reason for credit note"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    full_refund: bool = typer.Option(True, help="Full refund of the invoice"),
    # TODO: Add partial refund support via interactive prompt or complex flags if needed later
) -> None:
    """Create a Credit Note for an invoice."""
    with cli_errors():
        created = ops.create_credit_note(get_factory(backend), invoice_number, reason)

    console.print(f"[green]✓ Created Credit Note {created.credit_note.number}[/green]")
    console.print(f"  Reference: {created.original.number}")
    console.print(f"  Total Credited: ${created.credit_note.total_amount:.2f}")


@app.command("get")
def get_credit_note(
    number: str = typer.Argument(..., help="Credit Note Number"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get details of a Credit Note."""
    with cli_errors():
        invoice = ops.find_credit_note(get_factory(backend), number)

    if invoice.type != InvoiceType.CREDIT_NOTE:
        console.print(f"[yellow]Warning: '{number}' is an Invoice, not a Credit Note.[/yellow]")

    console.print(f"[bold]Credit Note: {invoice.number}[/bold]")
    console.print(f"Date: {invoice.issue_date}")
    console.print(f"Status: {invoice.status}")
    console.print(f"Client: {invoice.client_name_snapshot}")
    console.print(f"Reason: {invoice.reason}")
    console.print(f"Original Invoice: {invoice.original_invoice_id} (ID)")

    table = Table(title="Lines")
    table.add_column("Description")
    table.add_column("Qty", justify="right")
    table.add_column("Unit Price", justify="right")
    table.add_column("Total", justify="right")
    for line in invoice.lines:
        table.add_row(
            line.description,
            str(line.quantity),
            f"${line.unit_price:.2f}",
            f"${line.total:.2f}",
        )
    console.print(table)
    console.print(f"[bold]Total: ${invoice.total_amount:.2f}[/bold]")
