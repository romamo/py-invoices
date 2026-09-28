import typer
from rich.table import Table

from py_invoices.cli.utils import cli_errors, get_console, get_factory
from py_invoices.operations import payments as ops

app = typer.Typer()
console = get_console()


@app.command("list")
def list_payments(
    invoice_number: str = typer.Argument(..., help="Invoice Number"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List payments for a specific invoice."""
    with cli_errors():
        result = ops.invoice_payments(get_factory(backend), invoice_number)

    if not result.payments:
        console.print(f"[yellow]No payments recorded for {result.invoice.number}.[/yellow]")
        return

    table = Table(title=f"Payments for {result.invoice.number}")
    table.add_column("ID", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Amount", justify="right")
    table.add_column("Method")
    table.add_column("Reference")
    for payment in result.payments:
        table.add_row(
            str(payment.id),
            str(payment.payment_date),
            f"${payment.amount:.2f}",
            payment.payment_method or "-",
            payment.reference or "-",
        )
    console.print(table)
    console.print(f"[bold]Total Paid: ${result.total_paid:.2f}[/bold]")
    console.print(f"Balance Due: ${result.balance_due:.2f}")
