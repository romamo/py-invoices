import typer
from pydantic_invoices.schemas.product import Product, ProductCreate
from rich.table import Table

from py_invoices.cli.utils import cli_errors, get_console, get_factory
from py_invoices.core.totals import format_money
from py_invoices.operations import products as ops

app = typer.Typer()
console = get_console()


def products_table(title: str, products: list[Product]) -> Table:
    table = Table(title=title)
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Category")
    table.add_column("Price", justify="right")
    for product in products:
        table.add_row(
            product.code,
            product.name,
            product.category or "-",
            format_money(product.unit_price),
        )
    return table


@app.command("list")
def list_products(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    category: str = typer.Option(None, help="Filter by category"),
) -> None:
    """List active products."""
    products = ops.list_products(get_factory(backend), category)
    if not products:
        console.print("[yellow]No products found.[/yellow]")
        return
    console.print(products_table("Products", products))


@app.command("get")
def get_product(
    code: str = typer.Argument(..., help="Product Code"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get product details by code."""
    with cli_errors():
        product = ops.find_product(get_factory(backend), code)

    console.print(f"[bold]Product: {product.name}[/bold]")
    console.print(f"Code: {product.code}")
    console.print(f"Category: {product.category}")
    console.print(f"Price: {format_money(product.unit_price)}")
    console.print(f"Description: {product.description}")


@app.command("search")
def search_products(
    query: str = typer.Argument(..., help="Search query"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Search products by name, code, or description."""
    products = ops.search_products(get_factory(backend), query)
    if not products:
        console.print(f"[yellow]No products found matching '{query}'.[/yellow]")
        return
    console.print(products_table(f"Search Results: '{query}'", products))


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
    data = ProductCreate(
        name=name,
        code=code,
        unit_price=unit_price,
        category=category,
        description=description,
        tax_rate=tax_rate,
        preferred_template=preferred_template,
    )
    product = ops.create_product(get_factory(backend), data)

    console.print(f"[green]✓ Created Product {product.name}[/green]")
    console.print(f"  Code: {product.code}")
    console.print(f"  Price: {format_money(product.unit_price)}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )
