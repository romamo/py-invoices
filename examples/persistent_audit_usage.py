"""Example demonstrating persistent audit logs with SQLite backend."""

import os
from datetime import datetime

from pydantic_invoices.schemas import InvoiceStatus, PaymentCreate

from py_invoices.core import AuditService
from py_invoices.plugins import RepositoryFactory


def main() -> None:
    db_file = "audit_demo.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    print(f"--- Persistent Audit Example (using {db_file}) ---")

    # 1. Initialize factory and repositories
    # We use SQLite for persistence
    factory = RepositoryFactory(backend="sqlite", database_url=f"sqlite:///{db_file}")

    invoice_repo = factory.create_invoice_repository()
    audit_repo = factory.create_audit_repository()

    # 2. Initialize services
    # Now we pass the audit_repo to AuditService for persistence
    audit_service = AuditService(audit_repo=audit_repo)
    audit_service = AuditService(audit_repo=audit_repo)

    # 3. Create some data and perform actions
    print("\n1. Creating a client and an invoice...")
    client_repo = factory.create_client_repository()
    from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceLineCreate

    # Create Client
    client = client_repo.create(
        ClientCreate(
            name="Audit Corp",
            address="123 Audit Lane",
            tax_id="AUD-001",
            email="audit@example.com",
            phone="555-0000",
        )
    )
    # Create invoice
    invoice_in = InvoiceCreate(
        number="PERSIST-001",
        issue_date=datetime.now(),
        status=InvoiceStatus.DRAFT,
        client_id=client.id,
        company_id=1,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        lines=[InvoiceLineCreate(description="Service A", quantity=10, unit_price=150.0)],
        original_invoice_id=None,
        reason=None,
        due_date=None,
    )
    repo_invoice = invoice_repo.create(invoice_in)
    # We need to fetch it to get the version with ID
    # if create doesn't return full object with ID (it should)
    # But to satisfy type checker if create returns Invoice and we need to be sure
    invoice = repo_invoice
    # Log creation
    audit_service.log_invoice_created(invoice, user_id="admin")

    print(f"   Created Invoice: {invoice.number}")

    # 4. Add a payment
    print("\n2. Adding a payment...")
    payment_repo = factory.create_payment_repository()
    payment = payment_repo.create(
        PaymentCreate(
            invoice_id=invoice.id,
            amount=500.0,
            payment_date=datetime.now(),
            reference="REF-001",
            payment_method="Bank Transfer",
        )
    )

    # Log payment
    # Retrieve invoice to see balance update
    invoice_or_none = invoice_repo.get_by_id(invoice.id)
    if invoice_or_none:
        invoice = invoice_or_none
        print(f"Updated Balance: ${invoice.balance_due}")
    audit_service.log_payment_added(invoice, payment, user_id="admin")

    # 5. Change status
    print("\n3. Changing status to PAID...")
    old_status = str(invoice.status)
    invoice.status = InvoiceStatus.PAID
    invoice_repo.update(invoice)

    # Log status change
    audit_service.log_status_changed(
        invoice, new_status="PAID", old_status=old_status, user_id="admin"
    )

    # 6. Check logs (in current session)
    print("\n4. Checking audit logs in current session:")
    logs = audit_service.get_logs(invoice_id=invoice.id)
    for log in logs:
        print(
            f"   [{log.timestamp.strftime('%H:%M:%S')}] {log.action}: {log.new_value or log.notes}"
        )

    # 7. Verification of persistence
    print("\n5. Verifying PERSISTENCE (reclosing and reopening database)...")
    factory.cleanup()

    # New factory, new service instance
    new_factory = RepositoryFactory(backend="sqlite", database_url=f"sqlite:///{db_file}")
    new_audit_repo = new_factory.create_audit_repository()
    new_audit_service = AuditService(audit_repo=new_audit_repo)

    # Fetch logs - should be loaded from DB
    persisted_logs = new_audit_service.get_logs(invoice_id=invoice.id)
    print(f"   Successfully retrieved {len(persisted_logs)} logs from database!")

    for log in persisted_logs:
        print(f"   [DEEP RECALL] {log.action}: {log.new_value or log.notes}")

    new_factory.cleanup()
    print(f"\nExample completed. Database {db_file} kept for inspection (manual delete if needed).")


if __name__ == "__main__":
    main()
