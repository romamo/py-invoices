from typing import NoReturn

import typer
from rich.table import Table

from py_invoices.cli.utils import error_lines, get_console, get_factory
from py_invoices.operations import companies as ops
from py_invoices.operations.errors import OperationError

app = typer.Typer()
console = get_console()


@app.command("list")
def list_companies(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List active companies."""
    listing = ops.list_companies(get_factory(backend))
    if not listing.companies:
        console.print("[yellow]No active companies found.[/yellow]")
        return

    table = Table(title="Companies")
    table.add_column("Name", style="green")
    table.add_column("Tax ID")
    table.add_column("Email")
    table.add_column("Default")
    for company in listing.companies:
        table.add_row(
            company.name,
            str(company.tax_id) if company.tax_id else "-",
            company.email or "-",
            "*" if company.id == listing.default_id else "",
        )
    console.print(table)


@app.command("default")
def get_default_company(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get the default company details."""
    company = ops.default_company(get_factory(backend))
    if not company:
        console.print("[yellow]No default company configured.[/yellow]")
        return

    console.print(f"[bold]Default Company: {company.name}[/bold]")
    console.print(f"Address: {company.address}")
    console.print(f"Tax ID: {company.tax_id}")
    console.print(f"Email: {company.email}")
    console.print(f"Phone: {company.phone}")


@app.command("create")
def create_company(
    name: str = typer.Option(..., help="Company name"),
    tax_id: str = typer.Option(None, help="Company Tax ID"),
    address: str = typer.Option(None, help="Company address"),
    email: str = typer.Option(None, help="Company email"),
    phone: str = typer.Option(None, help="Company phone"),
    number_prefix: str = typer.Option(
        None,
        help="Prefix giving the company its own number series (AC -> AC-INV-2026-0001)",
    ),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Create a new company."""
    try:
        company = ops.create_company(
            get_factory(backend), name, tax_id, address, email, phone, number_prefix
        )
    except OperationError as e:
        _fail(e)

    console.print(f"[green]✓ Created Company {company.name}[/green]")
    console.print(f"  ID: {company.id}")
    console.print(f"  Tax ID: {company.tax_id or 'N/A'}")
    if company.number_prefix:
        console.print(f"  Number prefix: {company.number_prefix}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )


@app.command("set-number-prefix")
def set_number_prefix(
    company_id: int = typer.Argument(..., help="Company ID"),
    number_prefix: str = typer.Argument(..., help="Letters and digits, e.g. AC"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Give a company its own number series (AC -> AC-INV-2026-0001, AC-CN-2026-0001).

    Numbers already issued keep theirs; the company's next invoice starts the new series.
    """
    try:
        company = ops.set_number_prefix(get_factory(backend), company_id, number_prefix)
    except OperationError as e:
        _fail(e)
    console.print(
        f"[green]✓ {company.name} numbers its documents {company.number_prefix}-…[/green]"
    )


def _fail(error: OperationError) -> NoReturn:
    for line in error_lines(error):
        console.print(line)
    raise typer.Exit(1)
