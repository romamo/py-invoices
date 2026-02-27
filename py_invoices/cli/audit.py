import typer
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory
from py_invoices.core.audit_service import AuditService

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
    factory = get_factory(backend)

    # AuditService usually needs a repository if persistent, or it might just use memory
    # The factory logic for audit repo:
    audit_repo = factory.create_audit_repository()
    service = AuditService(audit_repo=audit_repo)

    logs = service.get_logs(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        action=action
    )

    # Slice for limit since get_logs might return all
    # Ideally repo handles limit, but service interface shown didn't have limit arg
    display_logs = logs[-limit:] if limit and len(logs) > limit else logs

    table = Table(title="Audit Logs")
    table.add_column("Timestamp", style="dim")
    table.add_column("Action", style="cyan")
    table.add_column("Invoice", style="green")
    table.add_column("Details")
    table.add_column("User", style="magenta")

    if not display_logs:
        console.print("[yellow]No audit logs found matching criteria.[/yellow]")
        return

    for log in display_logs:
        # Construct detailed message
        details = []
        if log.old_value:
            details.append(f"Old: {log.old_value}")
        if log.new_value:
            details.append(f"New: {log.new_value}")
        if log.notes:
            details.append(f"Note: {log.notes}")

        detail_str = "; ".join(details)

        table.add_row(
            str(log.timestamp.strftime("%Y-%m-%d %H:%M:%S")),
            log.action,
            log.invoice_number or str(log.invoice_id or "-"),
            detail_str,
            log.user or "-"
        )

    console.print(table)


@app.command("summary")
def get_summary(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get audit log summary."""
    factory = get_factory(backend)
    audit_repo = factory.create_audit_repository()
    service = AuditService(audit_repo=audit_repo)

    summary = service.get_summary()

    console.print("[bold]Audit Log Summary[/bold]")
    console.print(f"Total Entries: {summary.get('total_entries', 0)}")

    console.print("\n[bold]Actions Count:[/bold]")
    for action, count in summary.get("actions_count", {}).items():
        console.print(f"  {action}: {count}")

    invoices = summary.get("invoices_affected", [])
    console.print(f"\nTotal Invoices Affected: {len(invoices)}")
