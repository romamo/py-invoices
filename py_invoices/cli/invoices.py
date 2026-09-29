from datetime import date, datetime

import typer
from pydantic_invoices.schemas import Invoice
from rich.table import Table

from py_invoices.cli.utils import cli_errors, get_console, get_factory
from py_invoices.core.totals import format_money
from py_invoices.operations import invoices as ops
from py_invoices.operations.invoices import (
    CompanyOverrides,
    DocumentKind,
    ExportOutcome,
    NewInvoice,
)

app = typer.Typer()
console = get_console()

EXPORT_LABELS = {"pdf": "PDF", "html": "HTML", "ubl": "UBL XML", "json": "JSON"}


def print_export_outcomes(outcomes: list[ExportOutcome]) -> None:
    for outcome in outcomes:
        label = EXPORT_LABELS[outcome.format]
        console.print(f"[blue]  -> Generated {label}: {outcome.path}[/blue]")


def parse_date(value: str | None, option: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        console.print(f"[red]Error: Invalid {option} format. Use YYYY-MM-DD.[/red]")
        raise typer.Exit(code=1) from None


def render_document(
    kind: DocumentKind,
    invoice_identifier: str,
    output_dir: str,
    backend: str | None,
    company: CompanyOverrides,
    template: str | None,
) -> None:
    with cli_errors():
        document = ops.render_invoice_document(
            get_factory(backend), invoice_identifier, kind, output_dir, company, template
        )
    console.print(
        f"[green]✓ Generated {kind.value.upper()} for Invoice {document.invoice.number}[/green]"
    )
    console.print(f"  Path: {document.path}")


@app.command("pdf")
def generate_pdf(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    output_dir: str = typer.Option("output", help="Directory to save the PDF"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    # Company Details
    company_name: str | None = typer.Option(None, help="Company Name"),
    company_address: str | None = typer.Option(None, help="Company Address"),
    company_tax_id: str | None = typer.Option(None, help="Company Tax ID"),
    company_email: str | None = typer.Option(None, help="Company Email"),
    company_logo_path: str | None = typer.Option(None, help="Company Logo Path"),
    template: str = typer.Option(None, help="Template name to use (e.g. invoice.html.j2)"),
) -> None:
    """Generate PDF for an invoice."""
    company = CompanyOverrides(
        company_name, company_address, company_tax_id, company_email, company_logo_path
    )
    render_document(DocumentKind.PDF, invoice_identifier, output_dir, backend, company, template)


@app.command("html")
def generate_html(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    output_dir: str = typer.Option("output", help="Directory to save the HTML"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    # Company Details
    company_name: str | None = typer.Option(None, help="Company Name"),
    company_address: str | None = typer.Option(None, help="Company Address"),
    company_tax_id: str | None = typer.Option(None, help="Company Tax ID"),
    company_email: str | None = typer.Option(None, help="Company Email"),
    company_logo_path: str | None = typer.Option(None, help="Company Logo Path"),
    template: str = typer.Option(None, help="Template name to use (e.g. invoice.html.j2)"),
) -> None:
    """Generate HTML for an invoice."""
    company = CompanyOverrides(
        company_name, company_address, company_tax_id, company_email, company_logo_path
    )
    render_document(DocumentKind.HTML, invoice_identifier, output_dir, backend, company, template)


@app.command("list")
def list_invoices(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    limit: int = typer.Option(10, help="Number of invoices to show"),
) -> None:
    """List recent invoices."""
    invoices = ops.list_invoices(get_factory(backend), limit)
    if not invoices:
        console.print("[yellow]No invoices found.[/yellow]")
        return

    table = Table(title="Invoices")
    table.add_column("Number", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Client", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Status")
    for invoice in invoices:
        table.add_row(
            invoice.number,
            str(invoice.issue_date),
            invoice.client_name_snapshot,
            format_money(invoice.total_amount),
            invoice.status.value,
        )
    console.print(table)


@app.command("details")
def get_invoice_details(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get full details of an invoice."""
    with cli_errors():
        invoice = ops.find_invoice(get_factory(backend), invoice_identifier)

    console.print(f"[bold]Invoice: {invoice.number}[/bold]")
    console.print(f"Date: {invoice.issue_date}")
    console.print(f"Status: {invoice.status.value}")
    console.print(f"Client: {invoice.client_name_snapshot}")
    console.print(f"Type: {invoice.type.value}")

    table = Table(title="Line Items")
    table.add_column("Description")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Total", justify="right")
    for line in invoice.lines:
        table.add_row(
            line.description,
            str(line.quantity),
            format_money(line.unit_price),
            format_money(line.total),
        )
    console.print(table)
    console.print(f"[bold]Total: {format_money(invoice.total_amount)}[/bold]")


@app.command("overdue")
def list_overdue(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List overdue invoices."""
    invoices = ops.list_overdue_invoices(get_factory(backend))
    if not invoices:
        console.print("[green]No overdue invoices found. Great job![/green]")
        return

    table = Table(title="Overdue Invoices", style="red")
    table.add_column("Number", style="cyan")
    table.add_column("Due Date", style="magenta")
    table.add_column("Client", style="green")
    table.add_column("Total", justify="right")
    for invoice in invoices:
        table.add_row(
            invoice.number,
            str(invoice.due_date),
            invoice.client_name_snapshot,
            format_money(invoice.total_amount),
        )
    console.print(table)


@app.command("summary")
def show_summary(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Show invoice statistics."""
    with cli_errors():
        summary = ops.invoice_summary(get_factory(backend))
    console.print("[bold]Invoice Summary[/bold]")
    console.print(f"Total Count:    {summary.total_count}")
    console.print(f"Paid Count:     {summary.paid_count}")
    console.print(f"Unpaid Count:   {summary.unpaid_count}")
    console.print(f"Overdue Count:  {summary.overdue_count}")
    console.print(f"Total Amount:   {format_money(summary.total_amount)}")
    console.print(f"Total Paid:     {format_money(summary.total_paid)}")
    console.print(f"Total Due:      {format_money(summary.total_due)}")


@app.command("create")
def create_invoice(
    amount: str = typer.Option(..., help="Invoice amount (exact decimal, e.g. 1234.50)"),
    currency: str = typer.Option("USD", help="ISO currency code of the amount"),
    client_name: str = typer.Option(None, help="Client name to search for"),
    client_id: int = typer.Option(None, help="Client ID to link directly"),
    client_address: str = typer.Option(None, help="Client address (if creating new)"),
    client_tax_id: str = typer.Option(None, help="Client Tax ID (if creating new)"),
    client_email: str = typer.Option(None, help="Client Email (if creating new)"),
    client_phone: str = typer.Option(None, help="Client Phone (if creating new)"),
    description: str = typer.Option(..., help="Line item description"),
    invoice_number: str = typer.Option(
        None, help="Custom invoice number (overrides auto-generation)"
    ),
    payment_terms: str = typer.Option(
        "Due on Receipt", help="Payment terms; 'Net <days>' also sets the due date"
    ),
    due_date_str: str | None = typer.Option(
        None, "--due-date", help="Due date (YYYY-MM-DD); overrides the one from payment terms"
    ),
    bank_account: str = typer.Option(None, help="Bank account details to display"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option(
        [], "--format", "-f", help="Output formats to generate immediately (pdf, html, json, ubl)"
    ),
    output_dir: str = typer.Option("output", help="Directory for generated files"),
    # Company Details
    company_name: str | None = typer.Option(None, help="Company Name (required for formats)"),
    company_address: str | None = typer.Option(None, help="Company Address (required for formats)"),
    company_tax_id: str | None = typer.Option(None, help="Company Tax ID"),
    company_email: str | None = typer.Option(None, help="Company Email"),
    company_logo_path: str | None = typer.Option(None, help="Company Logo Path"),
    template: str = typer.Option(None, help="Template name to use"),
) -> None:
    """
    Create a new invoice.

    If providing --client-name and the client doesn't exist, it will be automatically created.
    You can optionally generate output files immediately using --format.
    Example: --format pdf --format html
    """
    factory = get_factory(backend)
    company = CompanyOverrides(
        company_name, company_address, company_tax_id, company_email, company_logo_path
    )
    with cli_errors():
        formats = ops.check_new_invoice_export(factory, formats, company)
        money = ops.parse_amount(amount, currency)
    request = NewInvoice(
        amount=money,
        description=description,
        client_id=client_id,
        client_name=client_name,
        client_address=client_address,
        client_tax_id=client_tax_id,
        client_email=client_email,
        client_phone=client_phone,
        invoice_number=invoice_number,
        payment_terms=payment_terms,
        due_date=parse_date(due_date_str, "--due-date"),
        company=company,
        template=template,
    )
    with cli_errors():
        created = ops.create_invoice(factory, request)

    if created.created_client is not None:
        client = created.created_client
        console.print(f"[yellow]Client '{client_name}' not found. Creating new client...[/yellow]")
        console.print(f"[green]✓ Created Client {client.name} (ID: {client.id})[/green]")
    print_invoice_created(created.invoice)
    if factory.plugin.name == "memory":
        console.print("\n[yellow]Note: Invoice stored in memory.[/yellow]")

    if formats:
        notes = ops.export_payment_notes(payment_terms, bank_account)
        with cli_errors():
            outcomes = ops.export_invoice(
                factory, created.invoice, formats, output_dir, company, notes
            )
        print_export_outcomes(outcomes)


def print_invoice_created(invoice: Invoice) -> None:
    console.print(f"[green]✓ Created Invoice {invoice.number}[/green]")
    console.print(f"  Client: {invoice.client_name_snapshot}")
    console.print(f"  Total:  {format_money(invoice.total_amount)}")


@app.command("stats")
def stats(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Display invoice statistics."""
    with cli_errors():
        summary = ops.invoice_summary(get_factory(backend))
    console.print("\n[bold cyan]INVOICE STATISTICS[/bold cyan]")
    console.print(f"Total Invoices:  {summary.total_count}")
    console.print(f"Total Amount:    {format_money(summary.total_amount)}")
    console.print(f"Total Paid:      {format_money(summary.total_paid)}")
    console.print(f"Total Due:       {format_money(summary.total_due)}")
    console.print(f"Overdue:         {summary.overdue_count}")


@app.command("clone")
def clone_invoice(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID to clone"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option(
        [], "--format", "-f", help="Output formats to generate immediately (pdf, html, json, ubl)"
    ),
    output_dir: str = typer.Option("output", help="Directory for generated files"),
    date_str: str | None = typer.Option(
        None, "--date", help="Set a specific issue date (YYYY-MM-DD)"
    ),
    # Company Details for generation
    company_name: str | None = typer.Option(None, help="Company Name (required for formats)"),
    company_address: str | None = typer.Option(None, help="Company Address (required for formats)"),
    company_tax_id: str | None = typer.Option(None, help="Company Tax ID"),
    company_email: str | None = typer.Option(None, help="Company Email"),
    company_logo_path: str | None = typer.Option(None, help="Company Logo Path"),
) -> None:
    """Clone an existing invoice with a new unique number."""
    factory = get_factory(backend)
    company = CompanyOverrides(
        company_name, company_address, company_tax_id, company_email, company_logo_path
    )
    issue_date = parse_date(date_str, "--date") or date.today()
    with cli_errors():
        original = ops.find_invoice(factory, invoice_identifier)
        formats = ops.check_invoice_export(factory, original, formats, company)
        cloned = ops.clone_invoice(factory, invoice_identifier, issue_date)

    console.print(
        f"[green]✓ Cloned Invoice {cloned.original.number} -> {cloned.invoice.number}[/green]"
    )
    console.print(f"  Total:  {format_money(cloned.invoice.total_amount)}")

    if formats:
        notes = ops.export_payment_notes(cloned.invoice.payment_terms, None)
        with cli_errors():
            outcomes = ops.export_invoice(
                factory, cloned.invoice, formats, output_dir, company, notes
            )
        print_export_outcomes(outcomes)
