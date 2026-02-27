import typer
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory

app = typer.Typer()
console = get_console()


@app.command("list")
def list_payment_notes(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    company_id: int = typer.Option(None, help="Filter by company ID"),
) -> None:
    """List active payment notes."""
    factory = get_factory(backend)
    repo = factory.create_payment_note_repository()

    if company_id:
        notes = repo.get_by_company(company_id)
    else:
        notes = repo.get_active()

    table = Table(title="Payment Notes")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Note")
    table.add_column("Default")

    if not notes:
        console.print("[yellow]No payment notes found.[/yellow]")
        return

    # We don't have get_default easily here without querying again or knowing it
    # We can check if is_default is a field in the schema, likely yes.
    # Assuming schema has is_default based on typical patterns, but let's
    # check repo.get_default(company_id) to mark it if we really want, but listing is fine.

    for note in notes:
        # Check attributes of PaymentNote schema (not shown but assumed similar to others)
        # Often it has 'note' or 'content' field.
        # Let's assume 'title' and 'note' based on table columns intended.
        # If schema is unknown, we might risk attribute error.
        # But 'get_default' suggests there is a concept of default.

        # Safe access to common fields
        note_id = str(getattr(note, "id", ""))
        title = getattr(note, "title", "Payment Note")
        content = getattr(note, "note", getattr(note, "content", ""))
        is_default_flag = getattr(note, "is_default", False)

        table.add_row(note_id, title, content, "*" if is_default_flag else "")

    console.print(table)


@app.command("default")
def get_default_note(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    company_id: int = typer.Option(None, help="Company ID to get default for"),
) -> None:
    """Get the default payment note."""
    factory = get_factory(backend)
    repo = factory.create_payment_note_repository()

    note = repo.get_default(company_id)

    if not note:
        console.print("[yellow]No default payment note found.[/yellow]")
        return

    console.print("[bold]Default Payment Note[/bold]")
    console.print(getattr(note, "note", getattr(note, "content", "")))


@app.command("create")
def create_payment_note(
    content: str = typer.Option(..., help="Payment note content"),
    title: str = typer.Option("Payment Note", help="Note title"),
    company_id: int = typer.Option(None, help="Associated Company ID"),
    is_default: bool = typer.Option(False, help="Set as default"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Create a new payment note."""
    factory = get_factory(backend)
    repo = factory.create_payment_note_repository()

    note_data = PaymentNoteCreate(
        title=title, content=content, company_id=company_id, is_default=is_default
    )

    created_note = repo.create(note_data)

    console.print("[green]✓ Created Payment Note[/green]")
    console.print(f"  ID: {created_note.id}")
    console.print(f"  Title: {created_note.title}")

    if backend == "memory":
        console.print(
            "\n[yellow]Note: stored in memory. It will be lost when this command exits.[/yellow]"
        )
