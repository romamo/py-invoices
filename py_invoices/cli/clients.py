import typer
from pydantic_invoices.schemas import Client, ClientCreate
from rich.table import Table

from py_invoices.cli.utils import cli_errors, get_console, get_factory, parse_country
from py_invoices.operations import clients as ops

app = typer.Typer()
console = get_console()


def clients_table(title: str, clients: list[Client]) -> Table:
    table = Table(title=title)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Tax ID")
    table.add_column("Email")
    for client in clients:
        table.add_row(
            str(client.id),
            client.name,
            str(client.tax_id) if client.tax_id else "-",
            client.email or "-",
        )
    return table


@app.command("list")
def list_clients(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    limit: int = typer.Option(10, help="Number of clients to show"),
) -> None:
    """List recent clients."""
    clients = ops.list_clients(get_factory(backend), limit)
    if not clients:
        console.print("[yellow]No clients found.[/yellow]")
        return
    console.print(clients_table("Clients", clients))


@app.command("details")
def get_client_details(
    client_identifier: str = typer.Argument(..., help="Client ID or Name"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get full details of a client."""
    with cli_errors():
        client = ops.find_client(get_factory(backend), client_identifier)

    console.print(f"[bold]Client: {client.name}[/bold]")
    console.print(f"ID: {client.id}")
    console.print(f"Address: {client.address}")
    console.print(f"City: {client.city or 'N/A'}")
    console.print(f"Postal Code: {client.postal_code or 'N/A'}")
    console.print(f"Country: {client.country or 'N/A'}")
    console.print(f"Tax ID: {client.tax_id or 'N/A'}")
    console.print(f"Email: {client.email or 'N/A'}")
    console.print(f"Phone: {client.phone or 'N/A'}")
    console.print(f"Preferred Template: {client.preferred_template or 'N/A'}")


@app.command("search")
def search_clients(
    query: str = typer.Argument(..., help="Search query"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Search clients by name, tax ID, or email."""
    clients = ops.search_clients(get_factory(backend), query)
    if not clients:
        console.print(f"[yellow]No clients found matching '{query}'.[/yellow]")
        return
    console.print(clients_table(f"Search Results: '{query}'", clients))


@app.command("create")
def create_client(
    name: str = typer.Option(..., help="Client name"),
    address: str = typer.Option(..., help="Client address"),
    city: str = typer.Option(None, help="Client city"),
    postal_code: str = typer.Option(None, help="Client postal code"),
    country: str = typer.Option(None, help="ISO 3166-1 alpha-2 country code, e.g. DE"),
    tax_id: str = typer.Option(None, help="Client Tax ID"),
    email: str = typer.Option(None, help="Client email"),
    phone: str = typer.Option(None, help="Client phone"),
    preferred_template: str = typer.Option(None, help="Preferred template filename"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option([], "--format", "-f", help="Output formats (json)"),
) -> None:
    """Create a new client."""
    data = ClientCreate(
        name=name,
        address=address,
        city=city,
        postal_code=postal_code,
        country=parse_country(country, "--country"),
        tax_id=tax_id,
        email=email,
        phone=phone,
        preferred_template=preferred_template,
    )
    client = ops.create_client(get_factory(backend), data)

    console.print(f"[green]✓ Created Client {client.name}[/green]")
    console.print(f"  ID: {client.id}")
    console.print(f"  Address: {client.address}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )

    for fmt in formats:
        if fmt.lower() == "json":
            console.print(client.model_dump_json(indent=2))
        else:
            console.print(f"[yellow]Warning: Format '{fmt}' not supported for clients.[/yellow]")
