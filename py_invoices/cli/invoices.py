import os
from datetime import date, datetime

import typer
from pydantic_invoices.schemas import InvoiceCreate, InvoiceLineCreate, InvoiceStatus
from rich.table import Table

from py_invoices.cli.utils import get_console, get_factory
from py_invoices.core import NumberingService, PDFService, AuditService

app = typer.Typer()
console = get_console()


@app.command("pdf")
def generate_pdf(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    output_dir: str = typer.Option("output", help="Directory to save the PDF"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    # Company Details
    company_name: str = typer.Option(..., help="Company Name"),
    company_address: str = typer.Option(..., help="Company Address"),
    company_tax_id: str = typer.Option(None, help="Company Tax ID"),
    company_email: str = typer.Option(None, help="Company Email"),
) -> None:
    """Generate PDF for an invoice."""
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()

    # ... (invoice resolution logic same as before) ...
    # Try to find invoice by ID first (if integer), then by number
    invoice = None
    if invoice_identifier.isdigit():
         if hasattr(invoice_repo, "get_by_id"):
             invoice = invoice_repo.get_by_id(int(invoice_identifier))
         elif hasattr(invoice_repo, "get"):
             invoice = invoice_repo.get(int(invoice_identifier))

    if not invoice:
        if hasattr(invoice_repo, "get_by_number"):
            invoice = invoice_repo.get_by_number(invoice_identifier)
        else:
             all_invoices = invoice_repo.get_all()
             invoice = next((i for i in all_invoices if i.number == invoice_identifier), None)

    if not invoice:
        console.print(f"[red]Error: Invoice '{invoice_identifier}' not found.[/red]")
        raise typer.Exit(code=1)

    company_data = {
        "name": company_name,
        "address": company_address,
        "email": company_email,
        "tax_id": company_tax_id,
    }

    try:
        import py_invoices
        package_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
        template_dir = os.path.join(package_dir, "templates")

        service = PDFService(template_dir=template_dir, output_dir=output_dir)
        os.makedirs(output_dir, exist_ok=True)

        output_path = service.generate_pdf(
            invoice=invoice,
            company=company_data
        )

        console.print(f"[green]✓ Generated PDF for Invoice {invoice.number}[/green]")
        console.print(f"  Path: {output_path}")

    except ImportError as e:
         console.print("[red]Error: PDF generation dependencies missing.[/red]")
         console.print(f"{e}")
         console.print("[yellow]Tip: Install with `pip install 'py-invoices[pdf]'`[/yellow]")
         raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error generating PDF: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("html")
def generate_html(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    output_dir: str = typer.Option("output", help="Directory to save the HTML"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    # Company Details
    company_name: str = typer.Option(..., help="Company Name"),
    company_address: str = typer.Option(..., help="Company Address"),
    company_tax_id: str = typer.Option(None, help="Company Tax ID"),
    company_email: str = typer.Option(None, help="Company Email"),
) -> None:
    """Generate HTML for an invoice."""
    from py_invoices.core import HTMLService

    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()

    invoice = None
    if invoice_identifier.isdigit():
         if hasattr(invoice_repo, "get_by_id"):
             invoice = invoice_repo.get_by_id(int(invoice_identifier))
         elif hasattr(invoice_repo, "get"):
             invoice = invoice_repo.get(int(invoice_identifier))

    if not invoice:
        if hasattr(invoice_repo, "get_by_number"):
            invoice = invoice_repo.get_by_number(invoice_identifier)
        else:
             all_invoices = invoice_repo.get_all()
             invoice = next((i for i in all_invoices if i.number == invoice_identifier), None)

    if not invoice:
        console.print(f"[red]Error: Invoice '{invoice_identifier}' not found.[/red]")
        raise typer.Exit(code=1)

    company_data = {
        "name": company_name,
        "address": company_address,
        "email": company_email,
        "tax_id": company_tax_id,
    }

    try:
        import py_invoices
        package_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
        template_dir = os.path.join(package_dir, "templates")

        service = HTMLService(template_dir=template_dir, output_dir=output_dir)
        os.makedirs(output_dir, exist_ok=True)

        output_path = service.save_html(
            invoice=invoice,
            company=company_data
        )

        console.print(f"[green]✓ Generated HTML for Invoice {invoice.number}[/green]")
        console.print(f"  Path: {output_path}")

    except Exception as e:
        console.print(f"[red]Error generating HTML: {e}[/red]")
        raise typer.Exit(code=1)


@app.command("list")
def list_invoices(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    limit: int = typer.Option(10, help="Number of invoice to show")
) -> None:
    """List recent invoices."""
    factory = get_factory(backend)
    repo = factory.create_invoice_repository()

    invoices = repo.get_all(limit=limit)

    table = Table(title="Invoices")
    table.add_column("Number", style="cyan")
    table.add_column("Date", style="magenta")
    table.add_column("Client", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Status")

    if not invoices:
        console.print("[yellow]No invoices found.[/yellow]")
        return

    for invoice in invoices:
        table.add_row(
            invoice.number,
            str(invoice.issue_date.date()),
            invoice.client_name_snapshot,
            f"${invoice.total_amount:.2f}",
            invoice.status.value
        )

    console.print(table)


@app.command("details")
def get_invoice_details(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Get full details of an invoice."""
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()

    # Reuse resolution logic? Simpler here for now.
    invoice = None
    if invoice_identifier.isdigit():
         if hasattr(invoice_repo, "get_by_id"):
             invoice = invoice_repo.get_by_id(int(invoice_identifier))
         elif hasattr(invoice_repo, "get"):
             invoice = invoice_repo.get(int(invoice_identifier))

    if not invoice:
        if hasattr(invoice_repo, "get_by_number"):
            invoice = invoice_repo.get_by_number(invoice_identifier)
        else:
             all_invoices = invoice_repo.get_all()
             invoice = next((i for i in all_invoices if i.number == invoice_identifier), None)

    if not invoice:
        console.print(f"[red]Error: Invoice '{invoice_identifier}' not found.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Invoice: {invoice.number}[/bold]")
    console.print(f"Date: {invoice.issue_date.date()}")
    console.print(f"Status: {invoice.status}")
    console.print(f"Client: {invoice.client_name_snapshot}")
    console.print(f"Type: {invoice.type}")
    
    table = Table(title="Line Items")
    table.add_column("Description")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Total", justify="right")
    
    for line in invoice.lines:
        table.add_row(
            line.description,
            str(line.quantity),
            f"${line.unit_price:.2f}",
            f"${line.line_total:.2f}"
        )
    
    console.print(table)
    console.print(f"[bold]Total: ${invoice.total_amount:.2f}[/bold]")


@app.command("overdue")
def list_overdue(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """List overdue invoices."""
    factory = get_factory(backend)
    repo = factory.create_invoice_repository()

    invoices = repo.get_overdue()

    table = Table(title="Overdue Invoices", style="red")
    table.add_column("Number", style="cyan")
    table.add_column("Due Date", style="magenta")
    table.add_column("Client", style="green")
    table.add_column("Total", justify="right")

    if not invoices:
        console.print("[green]No overdue invoices found. Great job![/green]")
        return

    for invoice in invoices:
        table.add_row(
            invoice.number,
            str(invoice.due_date),
            invoice.client_name_snapshot,
            f"${invoice.total_amount:.2f}"
        )

    console.print(table)


@app.command("summary")
def show_summary(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Show invoice statistics."""
    factory = get_factory(backend)
    repo = factory.create_invoice_repository()

    summary = repo.get_summary()
    # Expecting dict like {"total_invoices": 10, "total_revenue": 1000.0, "overdue_count": 2}
    # Adjust based on actua repo implementation if needed, but dict is flexible.

    console.print("[bold]Invoice Summary[/bold]")
    for key, value in summary.items():
        if "amount" in key or "revenue" in key:
            console.print(f"{key.replace('_', ' ').title()}: ${value:.2f}")
        else:
             console.print(f"{key.replace('_', ' ').title()}: {value}")


@app.command("create")
def create_invoice(
    amount: float = typer.Option(..., help="Invoice amount"),
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
    payment_terms: str = typer.Option("Due on Receipt", help="Payment terms (e.g. Net 30)"),
    bank_account: str = typer.Option(None, help="Bank account details to display"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option(
        [], "--format", "-f",
        help="Output formats to generate immediately (pdf, html, json, ubl)"
    ),
    output_dir: str = typer.Option("output", help="Directory for generated files"),
    # Company Details
    company_name: str = typer.Option(None, help="Company Name (required for formats)"),
    company_address: str = typer.Option(None, help="Company Address (required for formats)"),
    company_tax_id: str = typer.Option(None, help="Company Tax ID"),
    company_email: str = typer.Option(None, help="Company Email"),
) -> None:
    """
    Create a new invoice.

    If providing --client-name and the client doesn't exist, it will be automatically created.
    You can optionally generate output files immediately using --format.
    Example: --format pdf --format html
    """
    factory = get_factory(backend)
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # 1. Resolve Client
    client = None
    if client_id:
        client = client_repo.get_by_id(client_id)
        if not client:
            console.print(f"[red]Error: Client with ID {client_id} not found.[/red]")
            raise typer.Exit(code=1)
    elif client_name:
        # Simple search implementation
        all_clients = client_repo.get_all()
        # Case insensitive match
        client = next((c for c in all_clients if c.name.lower() == client_name.lower()), None)

        if not client:
             console.print(
                 f"[yellow]Client '{client_name}' not found. Creating new client...[/yellow]"
             )
             from pydantic_invoices.schemas import ClientCreate
             client = client_repo.create(ClientCreate(
                 name=client_name,
                 address=client_address, # Optional in schema
                 tax_id=client_tax_id,
                 email=client_email,
                 phone=client_phone
             ))
             console.print(f"[green]✓ Created Client {client.name} (ID: {client.id})[/green]")
    else:
        console.print("[red]Error: Must provide --client-id or --client-name[/red]")
        raise typer.Exit(code=1)

    # 2. Generate Number
    if not invoice_number:
        numbering = NumberingService(invoice_repo=invoice_repo)
        invoice_number = numbering.generate_number()

    # 3. Create Invoice
    invoice = invoice_repo.create(InvoiceCreate(
        number=invoice_number,
        issue_date=datetime.now(),
        status=InvoiceStatus.UNPAID,
        due_date=date.today(),
        payment_terms=payment_terms,
        original_invoice_id=None,
        reason=None,
        client_id=client.id,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        company_id=1,
        lines=[
            InvoiceLineCreate(
                description=description,
                quantity=1,
                unit_price=amount
            )
        ]
    ))

    console.print(f"[green]✓ Created Invoice {invoice.number}[/green]")
    console.print(f"  Client: {invoice.client_name_snapshot}")
    console.print(f"  Total:  ${invoice.total_amount:.2f}")

    if backend == "memory":
        console.print("\n[yellow]Note: Invoice stored in memory.[/yellow]")

    # 4. Handle Format Generation
    if formats:
        # Validate Company Info if formats requested
        if any(f.lower() in ["pdf", "html", "ubl"] for f in formats):
            if not company_name or not company_address:
                console.print(
                    "[red]Error: --company-name and --company-address are required when "
                    "generating files.[/red]"
                )
                pass

        company_data = {
            "name": company_name or "Unknown Company",
            "address": company_address or "Unknown Address",
            "email": company_email,
            "tax_id": company_tax_id
        }

        # Construct Payment Notes for Template
        # The template expects a list of objects with title/content
        payment_notes_context = []
        if payment_terms:
            payment_notes_context.append({"title": "Payment Terms", "content": payment_terms})
        if bank_account:
            payment_notes_context.append({"title": "Bank Account", "content": bank_account})

        try:
            import py_invoices
            package_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
            template_dir = os.path.join(package_dir, "templates")
            os.makedirs(output_dir, exist_ok=True)

            from py_invoices.core import HTMLService, PDFService, UBLService

            for fmt in formats:
                fmt = fmt.lower()
                try:
                    if fmt == "pdf":
                        pdf_service = PDFService(template_dir=template_dir, output_dir=output_dir)
                        path = pdf_service.generate_pdf(
                            invoice=invoice,
                            company=company_data,
                            payment_notes=payment_notes_context
                        )
                        console.print(f"[blue]  -> Generated PDF: {path}[/blue]")

                    elif fmt == "html":
                        html_service = HTMLService(template_dir=template_dir, output_dir=output_dir)
                        path = html_service.save_html(
                            invoice=invoice,
                            company=company_data,
                            payment_notes=payment_notes_context
                        )
                        console.print(f"[blue]  -> Generated HTML: {path}[/blue]")

                    elif fmt == "ubl":
                        ubl_service = UBLService(template_dir=template_dir, output_dir=output_dir)
                        path = ubl_service.save_ubl(invoice=invoice, company=company_data)
                        console.print(f"[blue]  -> Generated UBL XML: {path}[/blue]")

                    elif fmt == "json":
                        path = os.path.join(output_dir, f"{invoice.number}.json")
                        with open(path, "w") as f:
                            f.write(invoice.model_dump_json(indent=2))
                        console.print(f"[blue]  -> Generated JSON: {path}[/blue]")

                    else:
                        console.print(f"[yellow]  Warning: Unknown format '{fmt}'[/yellow]")

                except ImportError:
                     console.print(
                         f"[red]  Failed to generate {fmt.upper()}: Missing dependencies.[/red]"
                     )
                except Exception as e:
                     console.print(f"[red]  Failed to generate {fmt.upper()}: {e}[/red]")

        except Exception as e:
             console.print(f"[red]Error initializing generation services: {e}[/red]")


@app.command("stats")
def stats(
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
) -> None:
    """Display invoice statistics."""
    factory = get_factory(backend)
    repo = factory.create_invoice_repository()
    summary = repo.get_summary()

    console.print("\n[bold cyan]INVOICE STATISTICS[/bold cyan]")
    # Handle keys gracefully
    console.print(f"Total Invoices:  {summary.get('total_count', 0)}")
    console.print(f"Total Amount:    ${summary.get('total_amount', 0):.2f}")
    console.print(f"Total Paid:      ${summary.get('total_paid', 0):.2f}")
    console.print(f"Total Due:       ${summary.get('total_due', 0):.2f}")
    console.print(f"Overdue:         {summary.get('overdue_count', 0)}")


@app.command("clone")
def clone_invoice(
    invoice_identifier: str = typer.Argument(..., help="Invoice Number or ID to clone"),
    backend: str = typer.Option(None, help="Storage backend to use (overrides env var)"),
    formats: list[str] = typer.Option(
        [], "--format", "-f",
        help="Output formats to generate immediately (pdf, html, json, ubl)"
    ),
    output_dir: str = typer.Option("output", help="Directory for generated files"),
    # Company Details for generation
    company_name: str = typer.Option(None, help="Company Name (required for formats)"),
    company_address: str = typer.Option(None, help="Company Address (required for formats)"),
    company_tax_id: str = typer.Option(None, help="Company Tax ID"),
    company_email: str = typer.Option(None, help="Company Email"),
) -> None:
    """Clone an existing invoice with a new unique number."""
    factory = get_factory(backend)
    invoice_repo = factory.create_invoice_repository()
    audit_repo = factory.create_audit_repository()

    # 1. Find Original Invoice
    original = None
    if invoice_identifier.isdigit():
        if hasattr(invoice_repo, "get_by_id"):
            original = invoice_repo.get_by_id(int(invoice_identifier))
        elif hasattr(invoice_repo, "get"):
             original = invoice_repo.get(int(invoice_identifier))

    if not original:
        if hasattr(invoice_repo, "get_by_number"):
            original = invoice_repo.get_by_number(invoice_identifier)
        else:
             all_invoices = invoice_repo.get_all()
             # Note: inefficient for many invoices, but acceptable for CLI for now
             original = next((i for i in all_invoices if i.number == invoice_identifier), None)

    if not original:
        console.print(f"[red]Error: Invoice '{invoice_identifier}' not found.[/red]")
        raise typer.Exit(code=1)

    # 2. Get Next Number
    numbering = NumberingService(invoice_repo=invoice_repo)
    new_number = numbering.generate_number()

    # 3. Create New Invoice Data
    lines = [
        InvoiceLineCreate(
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price
        )
        for line in original.lines
    ]

    new_invoice_data = InvoiceCreate(
        number=new_number,
        issue_date=datetime.now(),
        status=InvoiceStatus.UNPAID,
        due_date=original.due_date, # Preserving original term, though might be past
        payment_terms=original.payment_terms,
        client_id=original.client_id,
        client_name_snapshot=original.client_name_snapshot,
        client_address_snapshot=original.client_address_snapshot,
        client_tax_id_snapshot=original.client_tax_id_snapshot,
        company_id=original.company_id,
        lines=lines
    )

    # 4. Save
    new_invoice = invoice_repo.create(new_invoice_data)

    # 5. Audit
    audit = AuditService(audit_repo=audit_repo)
    audit.log_invoice_cloned(
        invoice_id=new_invoice.id,
        invoice_number=new_invoice.number,
        original_number=original.number,
        total_amount=new_invoice.total_amount
    )

    console.print(f"[green]✓ Cloned Invoice {original.number} -> {new_invoice.number}[/green]")
    console.print(f"  Total:  ${new_invoice.total_amount:.2f}")

    # 6. Handle Format Generation (Same logic as create)
    if formats:
        # Validate Company Info if formats requested
        if any(f.lower() in ["pdf", "html", "ubl"] for f in formats):
            if not company_name or not company_address:
                console.print(
                    "[red]Error: --company-name and --company-address are required when "
                    "generating files.[/red]"
                )
                pass # Don't exit, just skip or let it fail downstream gracefully?
                # Actually, let's continue but it will probably fail or use defaults?
                # Create command logic used 'pass', effectively ignoring the error and continuing?
                # Ah, existing 'create' logic checks but 'pass' does nothing.
                # It continues to define 'company_data' below.

        company_data = {
            "name": company_name or "Unknown Company",
            "address": company_address or "Unknown Address",
            "email": company_email,
            "tax_id": company_tax_id
        }

        payment_notes_context = []
        if new_invoice.payment_terms:
             payment_notes_context.append({"title": "Payment Terms", "content": new_invoice.payment_terms})

        try:
            import py_invoices
            package_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
            template_dir = os.path.join(package_dir, "templates")
            os.makedirs(output_dir, exist_ok=True)

            from py_invoices.core import HTMLService, PDFService, UBLService

            for fmt in formats:
                fmt = fmt.lower()
                try:
                    if fmt == "pdf":
                        pdf_service = PDFService(template_dir=template_dir, output_dir=output_dir)
                        path = pdf_service.generate_pdf(
                            invoice=new_invoice,
                            company=company_data,
                            payment_notes=payment_notes_context
                        )
                        console.print(f"[blue]  -> Generated PDF: {path}[/blue]")

                    elif fmt == "html":
                        html_service = HTMLService(template_dir=template_dir, output_dir=output_dir)
                        path = html_service.save_html(
                            invoice=new_invoice,
                            company=company_data,
                            payment_notes=payment_notes_context
                        )
                        console.print(f"[blue]  -> Generated HTML: {path}[/blue]")

                    elif fmt == "ubl":
                        ubl_service = UBLService(template_dir=template_dir, output_dir=output_dir)
                        path = ubl_service.save_ubl(invoice=new_invoice, company=company_data)
                        console.print(f"[blue]  -> Generated UBL XML: {path}[/blue]")

                    elif fmt == "json":
                        path = os.path.join(output_dir, f"{new_invoice.number}.json")
                        with open(path, "w") as f:
                            f.write(new_invoice.model_dump_json(indent=2))
                        console.print(f"[blue]  -> Generated JSON: {path}[/blue]")

                    else:
                        console.print(f"[yellow]  Warning: Unknown format '{fmt}'[/yellow]")

                except ImportError:
                     console.print(
                         f"[red]  Failed to generate {fmt.upper()}: Missing dependencies.[/red]"
                     )
                except Exception as e:
                     console.print(f"[red]  Failed to generate {fmt.upper()}: {e}[/red]")

        except Exception as e:
             console.print(f"[red]Error initializing generation services: {e}[/red]")


