import typer

from py_invoices.cli.audit import app as audit_app
from py_invoices.cli.clients import app as clients_app
from py_invoices.cli.companies import app as companies_app
from py_invoices.cli.config import app as config_app
from py_invoices.cli.credit_notes import app as credit_notes_app
from py_invoices.cli.invoices import app as invoices_app
from py_invoices.cli.payment_notes import app as payment_notes_app
from py_invoices.cli.payments import app as payments_app
from py_invoices.cli.products import app as products_app
from py_invoices.cli.setup import interactive_setup
from py_invoices.cli.utils import get_console, get_factory
from py_invoices.cli.validate import app as validate_app
from py_invoices.config import get_settings

app = typer.Typer(
    name="py-invoices",
    help="CLI for py-invoices management.",
    add_completion=False,
)

app.add_typer(invoices_app, name="invoices", help="Manage invoices")
app.add_typer(clients_app, name="clients", help="Manage clients")
app.add_typer(products_app, name="products", help="Manage products")
app.add_typer(companies_app, name="companies", help="Manage companies")
app.add_typer(credit_notes_app, name="credit-notes", help="Manage credit notes")
app.add_typer(payments_app, name="payments", help="Manage payments")
app.add_typer(payment_notes_app, name="payment-notes", help="Manage payment notes")
app.add_typer(audit_app, name="audit", help="Manage audit logs")
app.add_typer(config_app, name="config", help="View configuration")
app.command(name="setup", help="Configure application (interactive)")(interactive_setup)
app.add_typer(validate_app, name="validate", help="Validate invoice files")


@app.command("init")
def init_db(backend: str = typer.Option(None, help="Storage backend to use")) -> None:
    """Initialize the database (No-op for memory backend)."""
    console = get_console()
    # Resolve backend
    resolved_backend = backend if backend else get_settings().backend

    if resolved_backend == "memory":
        console.print("[yellow]Memory backend selected. No initialization required.[/yellow]")
        console.print("[dim]Data will not persist between CLI runs.[/dim]")
        return

    get_factory(backend)
    # The factory init often creates tables if using SQLModel
    # This command is a placeholder for explicit migrations or setup if needed
    console.print(f"[green]Initialized {resolved_backend} backend successfully.[/green]")


def main() -> None:
    app()

if __name__ == "__main__":
    main()
