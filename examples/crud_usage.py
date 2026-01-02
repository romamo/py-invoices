"""Example showing typical CRUD operations using the SQLite backend."""
import os
from datetime import datetime

from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory


def main() -> None:
    # 1. Setup SQLite
    db_file = "demo_crud.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    print(f"--- Setting up SQLite backend: {db_file} ---")
    factory = RepositoryFactory(
        backend="sqlite",
        database_url=f"sqlite:///{db_file}"
    )

    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # 2. CREATE
    print("\n[CREATE] Adding new client...")
    client = client_repo.create(ClientCreate(
        name="Star Labs",
        address="1 Central City Plaza",
        tax_id="SL-1002"
    ))
    print(f"Created client {client.name} with ID: {client.id}")

    print("[CREATE] Creating invoice...")
    invoice = invoice_repo.create(InvoiceCreate(
        number="INV-STAR-001",
        issue_date=datetime.now(),
        status=InvoiceStatus.UNPAID,
        client_id=client.id,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        lines=[
            InvoiceLineCreate(
                description="Particle Accelerator Tune-up", quantity=1, unit_price=5000.0
            ),
            InvoiceLineCreate(description="Speed Force Measurement", quantity=5, unit_price=200.0)
        ]
    ))
    print(f"Created invoice {invoice.number} for ${invoice.total_amount}")

    # 3. READ / SEARCH
    print("\n[READ] Searching for clients with 'Star'...")
    search_results = client_repo.search("Star")
    for c in search_results:
        print(f"Found: {c.name} ({c.tax_id})")

    # 4. UPDATE
    print("\n[UPDATE] Updating client address...")
    client.address = "Speedsters Lane 1, Central City"
    updated_client = client_repo.update(client)
    print(f"Updated address: {updated_client.address}")

    print("[UPDATE] Marking invoice as PAID...")
    invoice.status = InvoiceStatus.PAID
    updated_invoice = invoice_repo.update(invoice)
    print(f"New status for {updated_invoice.number}: {updated_invoice.status}")

    # 5. SUMMARY
    print("\n[SUMMARY] Getting repository summary...")
    summary = invoice_repo.get_summary()
    print(f"Total Invoices: {summary['total_count']}")
    print(f"Total Amount:   ${summary['total_amount']:.2f}")

    # 6. DELETE
    print("\n[DELETE] Deleting invoice and client (cleaned up after demo)...")
    invoice_repo.delete(invoice.id)
    success = client_repo.delete(client.id)
    print(f"Deletion successful: {success}")

    # Cleanup DB file
    factory.cleanup()
    if os.path.exists(db_file):
        os.remove(db_file)
    print("\nDemo completed.")

if __name__ == "__main__":
    main()
