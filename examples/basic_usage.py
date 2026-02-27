"""Basic usage example for py-invoices with memory backend."""

from datetime import date, datetime

from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core import NumberingService


def main() -> None:
    """Demonstrate basic usage of py-invoices."""
    print("=== py-invoices Basic Usage Example ===\n")

    # Create factory with memory backend (no database required!)
    print("1. Initializing memory backend...")
    factory = RepositoryFactory(backend="memory")
    print(f"   ✓ Backend initialized. Health check: {factory.health_check()}\n")

    # Get repositories
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # Company setup (In a real app, you would have a company repository)
    print("1b. Setting up company information...")
    # For this example, we'll just use a company_id = 1
    company_id = 1
    print(f"   ✓ Company setup complete (ID: {company_id})\n")

    # Create a client
    print("2. Creating a client...")
    client = client_repo.create(
        ClientCreate(
            name="Acme Corporation",
            address="123 Business St, Suite 100",
            tax_id="12-3456789",
            email="billing@acme.com",
            phone="+1-555-0100",
            preferred_template=None,
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
            company_id=1,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[
                InvoiceLineCreate(
                    description="Professional Services - January 2025",
                    quantity=40,
                    unit_price=150.0,
                ),
                InvoiceLineCreate(
                    description="Software License - Annual",
                    quantity=10,  # Changed from 1.0 to 10
                    unit_price=1200.0,
                ),
            ],
            original_invoice_id=None,
            reason=None,
            template_name=None,
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

    # Get summary statistics
    print("5. Getting invoice summary...")
    summary = invoice_repo.get_summary()
    print(f"   ✓ Total invoices: {summary['total_count']}")
    print(f"     Unpaid: {summary['unpaid_count']}")
    print(f"     Total amount: ${summary['total_amount']:.2f}")
    print(f"     Total due: ${summary['total_due']:.2f}\n")

    # List all clients
    print("6. Listing all clients...")
    all_clients = client_repo.get_all()
    for c in all_clients:
        print(f"   - {c.name} (Tax ID: {c.tax_id})")

    print("\n✓ Example completed successfully!")


if __name__ == "__main__":
    main()
