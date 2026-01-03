"""Example using settings-based configuration."""

from datetime import datetime

from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
)

from py_invoices import InvoiceSettings, RepositoryFactory


def example_from_environment() -> None:
    """Example: Load settings from environment variables."""
    print("=== Example 1: From Environment Variables ===\n")

    # Automatically loads from environment variables and .env file
    factory = RepositoryFactory.from_settings()

    print("✓ Factory initialized from environment")
    print(f"  Health check: {factory.health_check()}\n")

    # Use factory as normal
    client_repo = factory.create_client_repository()
    factory.create_invoice_repository()

    # Create a client
    client = client_repo.create(
        ClientCreate(
            name="Globex",
            address="456 Global St",
            tax_id="US-987654",
            email=None,
            phone=None
        )
    )
    print(f"✓ Created client: {client.name}\n")


def example_explicit_settings() -> None:
    """Example: Use explicit settings object."""
    print("=== Example 2: Explicit Settings ===\n")

    # Create settings programmatically
    settings = InvoiceSettings(
        backend="memory",
        template_dir="./templates",
        output_dir="./output",
    )

    factory = RepositoryFactory.from_settings(settings)
    print("✓ Factory initialized with explicit settings")
    print(f"  Backend: {settings.backend}")
    print(f"  Template dir: {settings.template_dir}\n")

    # Use factory
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    # Create invoice
    client = client_repo.create(
        ClientCreate(
            name="ACME Corp",
            address="123 Industry Way",
            tax_id="US-123456",
            email=None,
            phone=None,
        )
    )

    invoice = invoice_repo.create(
        InvoiceCreate(
            number="INV-2023-001",
            issue_date=datetime.now(),
            client_id=client.id,
            company_id=1,
            original_invoice_id=None,
            reason=None,
            due_date=None,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[
                InvoiceLineCreate(
                    description="Consulting Services",
                    quantity=10,
                    unit_price=150.0
                )
            ]
        )
    )

    print(f"✓ Created invoice: {invoice.number}")
    print(f"  Total: ${invoice.total_amount:.2f}\n")


def example_sqlite_settings() -> None:
    """Example: SQLite backend via settings."""
    print("=== Example 3: SQLite via Settings ===\n")

    try:
        settings = InvoiceSettings(
            backend="sqlite",
            database_url="sqlite:///settings_example.db",
            database_echo=False,
        )

        factory = RepositoryFactory.from_settings(settings)
        print("✓ SQLite factory initialized")
        print(f"  Database: {settings.database_url}")
        print(f"  Health check: {factory.health_check()}\n")

        # Cleanup
        factory.cleanup()

    except ValueError as e:
        print(f"⚠ SQLite backend not available: {e}")
        print("  Install with: pip install py-invoices[sqlite]\n")


def main() -> None:
    """Run all examples."""
    print("=== py-invoices Settings Configuration Examples ===\n")

    example_from_environment()
    example_explicit_settings()
    example_sqlite_settings()

    print("✓ All examples completed!")


if __name__ == "__main__":
    main()
