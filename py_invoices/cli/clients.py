import typer
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory
from pydantic_invoices.schemas import ClientCreate

app = typer.Typer()
console = get_console()


@app.command("list")
def list_clients(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    limit: int = typer.Option(10, help="Number of clients to show")
) -> None:
    """List recent clients."""
    factory = get_factory(backend)
    repo = factory.create_client_repository()
    
    clients = repo.get_all(limit=limit)
    
    table = Table(title="Clients")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Tax ID")
    table.add_column("Email")

    if not clients:
        console.print("[yellow]No clients found.[/yellow]")
        return

    for client in clients:
        table.add_row(
            str(client.id),
            client.name,
            client.tax_id or "-",
            client.email or "-"
        )

    console.print(table)


@app.command("create")
def create_client(
    name: str = typer.Option(..., help="Client name"),
    address: str = typer.Option(..., help="Client address"),
    tax_id: str = typer.Option(None, help="Client Tax ID"),
    email: str = typer.Option(None, help="Client email"),
    phone: str = typer.Option(None, help="Client phone"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option(
        [], "--format", "-f", 
        help="Output formats (json)"
    )
) -> None:
    """Create a new client."""
    factory = get_factory(backend)
    repo = factory.create_client_repository()
    
    client_data = ClientCreate(
        name=name,
        address=address,
        tax_id=tax_id,
        email=email,
        phone=phone
    )
    
    client = repo.create(client_data)
    
    console.print(f"[green]✓ Created Client {client.name}[/green]")
    console.print(f"  ID: {client.id}")
    console.print(f"  Address: {client.address}")
    
    if backend == "memory":
        console.print("\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]")

    if formats:
        for fmt in formats:
            if fmt.lower() == "json":
                # Print JSON to console for piping? Or save? 
                # Since output_dir isn't an option here, let's print to console or save to current dir if desired?
                # User command `... --format json` usually implies getting the json back.
                # Let's print it to stdout nicely.
                console.print(client.model_dump_json(indent=2))
            else:
                 console.print(f"[yellow]Warning: Format '{fmt}' not supported for clients.[/yellow]")
