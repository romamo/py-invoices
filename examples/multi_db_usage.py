"""Example demonstrating how to easily switch between different storage backends."""

import os
from datetime import date, datetime

from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core import NumberingService


def run_example(backend: str, **config: str) -> None:
    """Run a full example with a specific backend."""
    print(f"\n--- Running Example with Backend: {backend.upper()} ---")

    try:
        # 1. Initialize factory
        with RepositoryFactory(backend=backend, **config) as factory:
            print(f"✓ {backend.capitalize()} backend initialized.")

            # 2. Get repositories
            client_repo = factory.create_client_repository()
            invoice_repo = factory.create_invoice_repository()

            # 3. Create a client
            client = client_repo.create(
                ClientCreate(
                    name=f"Client for {backend}",
                    address=f"Street in {backend} City",
                    tax_id=f"TAX-{backend.upper()}-001",
                )
            )
            print(f"✓ Created client: {client.name}")

            # 4. Create an invoice
            numbering = NumberingService(invoice_repo=invoice_repo)
            invoice_num = numbering.generate_number()

            invoice = invoice_repo.create(
                InvoiceCreate(
                    number=invoice_num,
                    issue_date=datetime.now(),
                    status=InvoiceStatus.UNPAID,
                    due_date=date(2025, 12, 31),
                    client_id=client.id,
                    client_name_snapshot=client.name,
                    client_address_snapshot=client.address,
                    client_tax_id_snapshot=client.tax_id,
                    company_id=1,
                    lines=[
                        InvoiceLineCreate(
                            description=f"Services using {backend} backend",
                            quantity=1,
                            unit_price=500.0,
                        )
                    ],
                )
            )
            print(f"✓ Created invoice: {invoice.number}")
            print(f"  Balance Due: ${invoice.balance_due:.2f}")

            # 5. Verify persistence (for non-memory backends)
            if backend != "memory":
                retrieved = invoice_repo.get_by_number(invoice.number)
                if retrieved:
                    print(f"✓ Verified persistence: {retrieved.number} found.")

    except Exception as e:
        print(f"✗ Failed to run {backend} backend: {e}")
        print("  (Note: Optional backends require their respective driver dependencies)")


def main() -> None:
    """Run examples for all supported backends."""
    print("=== py-invoices Multi-Backend Usage Example ===")

    # 1. In-Memory (Great for tests - no dependencies)
    run_example("memory")

    # 2. SQLite (Single file - included in standard library)
    run_example("sqlite", database_url="sqlite:///multi_db_example.db")

    # 3. PostgreSQL (Requires psycopg2-binary)
    # run_example("postgres", database_url="postgresql://user:pass@localhost:5432/invoices")

    # 4. MySQL (Requires pymysql)
    # run_example("mysql", database_url="mysql+pymysql://root:root@localhost:3306/invoices")

    print("\n✓ All reachable examples completed!")
    if os.path.exists("multi_db_example.db"):
        print("✓ Cleanup: multi_db_example.db created for sqlite example.")


if __name__ == "__main__":
    db_file = "multi_db_example.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    main()
