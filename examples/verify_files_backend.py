"""Example usage of the files backend."""

import shutil
from pathlib import Path

from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceLineCreate
from pydantic_invoices.schemas.company import CompanyCreate

from py_invoices.plugins.factory import RepositoryFactory

# Clean up previous run
DATA_DIR = Path("./files_data")
if DATA_DIR.exists():
    shutil.rmtree(DATA_DIR)


def verify_files_backend(fmt: str):
    print(f"\nVerifying {fmt} format...")

    # Initialize factory with files backend
    factory = RepositoryFactory(backend="files", root_dir=str(DATA_DIR / fmt), file_format=fmt)

    # Create repositories
    client_repo = factory.create_client_repository()
    company_repo = factory.create_company_repository()
    invoice_repo = factory.create_invoice_repository()

    # Create data
    company = company_repo.create(CompanyCreate(name="Acme Corp", tax_id="123456789"))

    client = client_repo.create(ClientCreate(name="John Doe", email="john@example.com"))

    invoice = invoice_repo.create(
        InvoiceCreate(
            client_id=client.id,
            company_id=company.id,
            number=f"INV-{fmt.upper()}-001",
            lines=[InvoiceLineCreate(description="Consulting", quantity=10, unit_price=100.0)],
        )
    )

    print(f"Created Invoice {invoice.number} (ID: {invoice.id})")

    # Verify file existence
    expected_file = DATA_DIR / fmt / "invoices" / f"{invoice.id}.{fmt}"
    if expected_file.exists():
        print(f"File created: {expected_file}")
    else:
        print(f"ERROR: File not created: {expected_file}")

    # Verify content loading
    loaded_invoice = invoice_repo.get_by_id(invoice.id)
    if loaded_invoice and loaded_invoice.number == invoice.number:
        print(f"Loaded invoice successfully: {loaded_invoice.number}")
    else:
        print("ERROR: Failed to load invoice")

    # cleanup is handled by rm at start or manual


def main():
    # Verify all formats
    verify_files_backend("json")
    verify_files_backend("xml")
    verify_files_backend("md")


if __name__ == "__main__":
    main()
