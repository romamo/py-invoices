import typer
from pydantic_invoices.schemas import InvoiceType
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory
from py_invoices.core.credit_service import CreditService
from py_invoices.core.numbering_service import NumberingService

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
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()

    # Needs a numbering service? Ideally yes, but CreditService takes it
    # We can perform a quick implementation or instantiate one
    # NumberingService needs invoice_repo
    numbering_service = NumberingService(invoice_repo=invoice_repo)
    credit_service = CreditService(invoice_repo, numbering_service)

    original_invoice = invoice_repo.get_by_number(invoice_number)
    if not original_invoice:
        console.print(f"[red]Error: Invoice '{invoice_number}' not found.[/red]")
        raise typer.Exit(code=1)

    try:
        cn = credit_service.create_credit_note(
            original_invoice=original_invoice,
            reason=reason,
            # lines=None, # Defaults to full refund if lines/indices not passed
            # refund_lines_indices=None
        )
        console.print(f"[green]✓ Created Credit Note {cn.number}[/green]")
        console.print(f"  Reference: {original_invoice.number}")
        console.print(f"  Total Credited: ${cn.total_amount:.2f}")  # Assuming positive for display?

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("get")
def get_credit_note(
    number: str = typer.Argument(..., help="Credit Note Number"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get details of a Credit Note."""
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()

    invoice = invoice_repo.get_by_number(number)

    if not invoice:
        console.print(f"[red]Error: Credit Note '{number}' not found.[/red]")
        raise typer.Exit(code=1)

    if invoice.type != InvoiceType.CREDIT_NOTE:
        console.print(f"[yellow]Warning: '{number}' is an Invoice, not a Credit Note.[/yellow]")
        # We can still show it or exit. Let's show it but warn.

    console.print(f"[bold]Credit Note: {invoice.number}[/bold]")
    console.print(f"Date: {invoice.issue_date.date()}")
    console.print(f"Status: {invoice.status}")
    console.print(f"Client: {invoice.client_name_snapshot}")
    console.print(f"Reason: {invoice.reason}")
    # Todo: fetch number if needed
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
