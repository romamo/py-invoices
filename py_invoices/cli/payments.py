import typer
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory

app = typer.Typer()
console = get_console()


@app.command("list")
def list_payments(
    invoice_number: str = typer.Argument(..., help="Invoice Number"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List payments for a specific invoice."""
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()
    payment_repo = factory.create_payment_repository()

    # Resolve invoice ID from number
    invoice = invoice_repo.get_by_number(invoice_number)
    if not invoice:
        console.print(f"[red]Error: Invoice '{invoice_number}' not found.[/red]")
        raise typer.Exit(code=1)

    payments = payment_repo.get_by_invoice(invoice.id)

    table = Table(title=f"Payments for {invoice.number}")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Amount", justify="right")
    table.add_column("Method")
    table.add_column("Reference")

    if not payments:
        console.print(f"[yellow]No payments recorded for {invoice.number}.[/yellow]")
        return

    for payment in payments:
        table.add_row(
            str(payment.id),
            str(payment.payment_date),
            f"${payment.amount:.2f}",
            payment.payment_method or "-",
            payment.reference or "-"
        )
    
    total_paid = sum(p.amount for p in payments)
    console.print(table)
    console.print(f"[bold]Total Paid: ${total_paid:.2f}[/bold]")
    console.print(f"Balance Due: ${max(0, invoice.total_amount - total_paid):.2f}")
