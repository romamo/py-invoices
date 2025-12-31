"""Example showing how to generate PDF invoices."""
from datetime import datetime, date, timedelta
from py_invoices import RepositoryFactory
from py_invoices.core import PDFService
from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

def main() -> None:
    # 1. Setup Backend
    factory = RepositoryFactory(backend="memory")
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # 2. Setup PDF Service
    # Ensure you have jinja2 and weasyprint installed: pip install py-invoices[pdf]
    pdf_service = PDFService(
        template_dir="templates",
        output_dir="output",
        default_template="invoice.html.j2"
    )

    # 3. Create Sample Data
    company_repo = factory.create_company_repository()
    from pydantic_invoices.schemas.company import CompanyCreate
    company_schema = company_repo.create(CompanyCreate(
        name="Acme Services Ltd",
        address="123 Business Way, New York, NY 10001",
        tax_id="NY-123456789",
        email="info@acmeservices.com"
    ))

    client = client_repo.create(ClientCreate(
        name="Tech Solutions Inc.",
        address="456 Innovation Drive, Suite 100, San Francisco, CA",
        tax_id="US-987654321"
    ))

    invoice = invoice_repo.create(InvoiceCreate(
        number="INV-2025-0010",
        issue_date=datetime.now(),
        due_date=date.today() + timedelta(days=14),
        status=InvoiceStatus.UNPAID,
        client_id=client.id,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        company_id=company_schema.id,
        lines=[
            InvoiceLineCreate(
                description="Cloud Infrastructure Setup",
                quantity=1,
                unit_price=2500.0
            ),
            InvoiceLineCreate(
                description="Software Development (Frontend)",
                quantity=40.0,
                unit_price=120.0
            ),
            InvoiceLineCreate(
                description="Backend Integration Services",
                quantity=20.0,
                unit_price=150.0
            )
        ]
    ))

    # 4. Generate PDF
    print(f"Generating PDF for invoice {invoice.number}...")
    try:
        pdf_path = pdf_service.generate_pdf(
            invoice=invoice,
            company=company_schema.model_dump(),
            payment_notes=[
                {"title": "Bank Details", "content": "Bank: Global Bank, IBAN: US1234567890, SWIFT: GBSWUS"},
                {"title": "Policy", "content": "Please include the invoice number in your transfer description."}
            ]
        )
        print(f"✅ PDF generated successfully: {pdf_path}")
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Falling back to HTML generation...")
        html_path = pdf_service.save_html(
            invoice=invoice,
            company=company
        )
        print(f"✅ HTML saved instead: {html_path}")

if __name__ == "__main__":
    main()
