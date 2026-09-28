import typer
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory
from py_invoices.operations import audit as ops

app = typer.Typer()
console = get_console()


@app.command("list")
def list_logs(
    # Filters
    invoice_id: int = typer.Option(None, help="Filter by Invoice ID"),
    invoice_number: str = typer.Option(None, help="Filter by Invoice Number"),
    action: str = typer.Option(None, help="Filter by Action type"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    limit: int = typer.Option(20, help="Number of logs to show"),
) -> None:
    """List audit logs."""
    logs = ops.list_audit_logs(get_factory(backend), invoice_id, invoice_number, action, limit)
    if not logs:
        console.print("[yellow]No audit logs found matching criteria.[/yellow]")
        return

    table = Table(title="Audit Logs")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Invoice", style="green")
    table.add_column("Details")
    table.add_column("User", style="magenta")
    for log in logs:
        table.add_row(
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.action,
            log.invoice_number or str(log.invoice_id or "-"),
            ops.entry_details(log),
            log.user or "-",
        )
    console.print(table)


@app.command("summary")
def get_summary(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get audit log summary."""
    summary = ops.audit_summary(get_factory(backend))

    console.print("[bold]Audit Log Summary[/bold]")
    console.print(f"Total Entries: {summary.get('total_entries', 0)}")

    console.print("\n[bold]Actions Count:[/bold]")
    for action, count in summary.get("actions_count", {}).items():
        console.print(f"  {action}: {count}")

    invoices = summary.get("invoices_affected", [])
    console.print(f"\nTotal Invoices Affected: {len(invoices)}")
