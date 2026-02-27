"""Example showing how to generate PDF invoices in-memory as bytes."""

import io
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
    pdf_service = PDFService(default_template="invoice.html.j2")

    # 3. Create Sample Data
    client = client_repo.create(
        ClientCreate(
            name="Acme Corp",
            address="777 Buffer St, Stream City",
            tax_id="123-456",
            email=None,
            phone=None,
        )
    )

    invoice = invoice_repo.create(
        InvoiceCreate(
            number="INV-MEM-001",
            issue_date=datetime.now(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.UNPAID,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            original_invoice_id=None,
            reason=None,
            lines=[
                InvoiceLineCreate(description="Memory Optimization", quantity=10, unit_price=150.0),
                InvoiceLineCreate(description="Stream Processing", quantity=5, unit_price=200.0),
            ],
        )
    )

    company = {
        "name": "Acme Services Ltd",
        "address": "123 Business Way, New York, NY 10001",
        "tax_id": "NY-123456789",
    }

    # 4. Generate PDF in-memory
    print(f"Generating PDF in-memory for invoice {invoice.number}...")
    try:
        # Get raw bytes
        pdf_bytes = pdf_service.generate_pdf_bytes(
            invoice=invoice,
            company=company,
            payment_notes=[{"title": "Note", "content": "This PDF was generated in-memory."}],
        )

        print(f"✅ PDF generated successfully in-memory! Size: {len(pdf_bytes)} bytes")

        # You can now:
        # - Return this in a web response: Response(content=pdf_bytes, media_type="application/pdf")
        # - Attach it to an email
        # - Wrap it in a file-like object
        pdf_stream = io.BytesIO(pdf_bytes)
        print(f"✅ Wrapped in BytesIO stream: {type(pdf_stream)}")

    except ImportError as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
