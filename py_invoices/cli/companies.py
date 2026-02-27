import typer
from pydantic_invoices.schemas.company import CompanyCreate
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory

app = typer.Typer()
console = get_console()


@app.command("list")
def list_companies(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List active companies."""
    factory = get_factory(backend)
    repo = factory.create_company_repository()

    companies = repo.get_active()

    table = Table(title="Companies")
    table.add_column("Name", style="green")
    table.add_column("Tax ID")
    table.add_column("Email")
    table.add_column("Default")

    if not companies:
        console.print("[yellow]No active companies found.[/yellow]")
        return

    # Assuming 'is_default' or similar might exist, but repo interface doesn't show it explicitly
    # on get_active items usually. Let's check if we can identify default.
    default_company = repo.get_default()
    default_id = default_company.id if default_company else -1

    for company in companies:
        is_default = "*" if company.id == default_id else ""
        table.add_row(company.name, company.tax_id or "-", company.email or "-", is_default)

    console.print(table)


@app.command("default")
def get_default_company(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get the default company details."""
    factory = get_factory(backend)
    repo = factory.create_company_repository()

    company = repo.get_default()

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
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Create a new company."""
    factory = get_factory(backend)
    repo = factory.create_company_repository()

    company_data = CompanyCreate(
        name=name,
        tax_id=tax_id,
        address=address,
        email=email,
        phone=phone,
        legal_name=None,
        registration_number=None,
        city=None,
        postal_code=None,
        country=None,
        website=None,
        logo_path=None,
    )

    company = repo.create(company_data)

    console.print(f"[green]✓ Created Company {company.name}[/green]")
    console.print(f"  ID: {company.id}")
    console.print(f"  Tax ID: {company.tax_id or 'N/A'}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )
