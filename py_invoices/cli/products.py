import typer
from pydantic_invoices.schemas.product import ProductCreate
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory

app = typer.Typer()
console = get_console()
@app.command("list")
def list_products(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    category: str = typer.Option(None, help="Filter by category"),
) -> None:
    """List active products."""
    factory = get_factory(backend)
    repo = factory.create_product_repository()

    if category:
        products = repo.get_by_category(category)
    else:
        products = repo.get_active()

    table = Table(title="Products")
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Category")
    table.add_column("Price", justify="right")

    if not products:
        console.print("[yellow]No products found.[/yellow]")
        return

    for product in products:
        table.add_row(
            product.code,
            product.name,
            product.category or "-",
            f"${product.unit_price:.2f}"
        )

    console.print(table)


@app.command("get")
def get_product(
    code: str = typer.Argument(..., help="Product Code"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get product details by code."""
    factory = get_factory(backend)
    repo = factory.create_product_repository()

    product = repo.get_by_code(code)

    if not product:
        console.print(f"[red]Error: Product '{code}' not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Product: {product.name}[/bold]")
    console.print(f"Code: {product.code}")
    console.print(f"Category: {product.category}")
    console.print(f"Price: ${product.unit_price:.2f}")
    console.print(f"Description: {product.description}")


@app.command("search")
def search_products(
    query: str = typer.Argument(..., help="Search query"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Search products by name, code, or description."""
    factory = get_factory(backend)
    repo = factory.create_product_repository()

    products = repo.search(query)

    table = Table(title=f"Search Results: '{query}'")
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Category")
    table.add_column("Price", justify="right")

    if not products:
        console.print(f"[yellow]No products found matching '{query}'.[/yellow]")
        return

    for product in products:
        table.add_row(
            product.code,
            product.name,
            product.category or "-",
            f"${product.unit_price:.2f}"
        )

    console.print(table)


@app.command("create")
def create_product(
    name: str = typer.Option(..., help="Product name"),
    code: str = typer.Option(..., help="Product code"),
    unit_price: float = typer.Option(..., help="Unit price"),
    category: str = typer.Option(None, help="Product category"),
    description: str = typer.Option(None, help="Product description"),
    tax_rate: float = typer.Option(0.0, help="Tax rate (0.0 - 1.0)"),
    preferred_template: str = typer.Option(None, help="Preferred template filename"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Create a new product."""
    factory = get_factory(backend)
    repo = factory.create_product_repository()

    product_data = ProductCreate(
        name=name,
        code=code,
        unit_price=unit_price,
        category=category,
        description=description,
        tax_rate=tax_rate,
        preferred_template=preferred_template
    )

    product = repo.create(product_data)

    console.print(f"[green]✓ Created Product {product.name}[/green]")
    console.print(f"  Code: {product.code}")
    console.print(f"  Price: ${product.unit_price:.2f}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )

