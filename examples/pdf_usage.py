"""Example showing how to generate PDF invoices."""

from datetime import date, datetime, timedelta

from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core import PDFService


def main() -> None:
    # 1. Setup Backend
    factory = RepositoryFactory(backend="memory")
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # 2. Setup PDF Service
    # Ensure you have jinja2 and weasyprint installed: pip install py-invoices[pdf]
    pdf_service = PDFService(output_dir="output", default_template="invoice.html.j2")

    # 3. Create Sample Data
    company_repo = factory.create_company_repository()
    from pydantic_invoices.schemas.company import CompanyCreate

    company_schema = company_repo.create(
        CompanyCreate(
            name="Acme Services Ltd",
            address="123 Business Way, New York, NY 10001",
            tax_id="NY-123456789",
            email="info@acmeservices.com",
            legal_name="Acme Legal",
            registration_number="REG-001",
            city="New York",
            postal_code="10001",
            country="USA",
            phone="555-0000",
            website="https://acme.com",
            logo_path=None,
        )
    )

    client = client_repo.create(
        ClientCreate(
            name="Tech Solutions Inc.",
            address="123 Tech Blvd, Silicon Valley, CA",
            tax_id="US-987654321",
            email=None,
            phone=None,
        )
    )

    invoice = invoice_repo.create(
        InvoiceCreate(
            number="INV-2025-0010",
            issue_date=datetime.now(),
            due_date=date.today() + timedelta(days=14),
            status=InvoiceStatus.UNPAID,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            company_id=company_schema.id,
            payment_terms="Net 30",
            original_invoice_id=None,
            reason=None,
            lines=[
                InvoiceLineCreate(description="Consulting Services", quantity=10, unit_price=150.0),
                InvoiceLineCreate(description="Software License", quantity=1, unit_price=500.0),
            ],
        )
    )

    # 4. Generate PDF
    print(f"Generating PDF for invoice {invoice.number}...")
    try:
        pdf_path = pdf_service.generate_pdf(
            invoice=invoice,
            company=company_schema.model_dump(),
            payment_notes=[
                {
                    "title": "Bank Details",
                    "content": "Bank: Global Bank, IBAN: US1234567890, SWIFT: GBSWUS",
                },
                {
                    "title": "Policy",
                    "content": "Please include the invoice number in your transfer description.",
                },
            ],
        )
        print(f"✅ PDF generated successfully: {pdf_path}")
    except ImportError as e:
        print(f"❌ Error: {e}")
        print("Falling back to HTML generation...")
        html_path = pdf_service.save_html(invoice=invoice, company=company_schema.model_dump())
        print(f"✅ HTML saved instead: {html_path}")

    # 5. Generate Industry Standard Formats (Optional)
    print("\nGenerating Industry Standard Formats...")
    try:
        # Factur-X (PDF/A-3 + XML)
        facturx_path = pdf_service.generate_facturx(
            invoice=invoice, company=company_schema.model_dump()
        )
        print(f"✅ Factur-X (ZUGFeRD) generated: {facturx_path}")
    except (ImportError, RuntimeError) as e:
        print(f"⚠️  Factur-X skipped: {e}")

    # UBL (XML Only)
    from py_invoices.core import UBLService

    ubl_service = UBLService(output_dir="output")
    ubl_path = ubl_service.save_ubl(invoice=invoice, company=company_schema.model_dump())
    print(f"✅ UBL XML generated: {ubl_path}")

    # 6. Generate Bytes (In-Memory)
    print("\nGenerating Bytes (In-Memory)...")
    try:
        pdf_bytes = pdf_service.generate_facturx_bytes(invoice, company=company_schema.model_dump())
        print(f"✅ Factur-X bytes generated: {len(pdf_bytes)} bytes")

        xml_bytes = ubl_service.generate_ubl_bytes(invoice, company=company_schema.model_dump())
        print(f"✅ UBL bytes generated: {len(xml_bytes)} bytes")
    except ImportError:
        print("⚠️  Skipping bytes generation due to missing dependencies")


if __name__ == "__main__":
    main()
