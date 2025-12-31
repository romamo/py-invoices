"""SQLite backend usage example."""
from datetime import datetime, date
from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core import NumberingService


def main() -> None:
    """Demonstrate SQLite backend usage."""
    print("=== py-invoices SQLite Backend Example ===\n")

    # Create factory with SQLite backend
    print("1. Initializing SQLite backend...")
    factory = RepositoryFactory(
        backend="sqlite", database_url="sqlite:///test_invoices.db"
    )
    print(f"   ✓ Backend initialized. Health check: {factory.health_check()}\n")

    # Get repositories
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # Create a client
    print("2. Creating a client...")
    client = client_repo.create(
        ClientCreate(
            name="Tech Solutions Inc",
            address="456 Tech Park, Innovation City",
            tax_id="98-7654321",
            email="accounts@techsolutions.com",
            phone="+1-555-0200",
        )
    )
    print(f"   ✓ Created client: {client.name} (ID: {client.id})\n")

    # Create an invoice
    print("3. Creating an invoice...")
    numbering = NumberingService(invoice_repo=invoice_repo)
    invoice_number = numbering.generate_number()

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=invoice_number,
            issue_date=datetime.now(),
            status=InvoiceStatus.UNPAID,
            due_date=date(2025, 1, 31),
            payment_terms="Net 30",
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            company_id=1,
            lines=[
                InvoiceLineCreate(
                    description="Cloud Infrastructure - Monthly",
                    quantity=1,
                    unit_price=2500.0,
                ),
                InvoiceLineCreate(
                    description="Support Services - 20 hours",
                    quantity=20,
                    unit_price=125.0,
                ),
            ],
        )
    )
    print(f"   ✓ Created invoice: {invoice.number}")
    print(f"     Total amount: ${invoice.total_amount:.2f}\n")

    # Retrieve invoice
    print("4. Retrieving invoice by number...")
    retrieved = invoice_repo.get_by_number(invoice_number)
    if retrieved:
        print(f"   ✓ Found invoice: {retrieved.number}")
        print(f"     Status: {retrieved.status}")
        print(f"     Lines: {len(retrieved.lines)}\n")

    # Search clients
    print("5. Searching clients...")
    results = client_repo.search("Tech")
    print(f"   ✓ Found {len(results)} client(s) matching 'Tech'")
    for c in results:
        print(f"     - {c.name}\n")

    # Get summary
    print("6. Getting invoice summary...")
    summary = invoice_repo.get_summary()
    print(f"   ✓ Total invoices: {summary['total_count']}")
    print(f"     Unpaid: {summary['unpaid_count']}")
    print(f"     Total amount: ${summary['total_amount']:.2f}\n")

    # Cleanup
    factory.cleanup()
    print("✓ Example completed successfully!")
    print("✓ Database saved to: test_invoices.db")


if __name__ == "__main__":
    main()
