"""Example showing how to use the AuditService to track changes."""
from datetime import datetime

from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core import AuditService


def main() -> None:
    # 1. Initialize Services
    audit_service = AuditService()
    factory = RepositoryFactory(backend="memory")
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()

    print("--- 1. Creating Client & Invoice ---")
    client = client_repo.create(ClientCreate(name="Audit Client", email=None, phone=None,
        address="789 Future St, Innova City",
        tax_id="GC-555-01"
    ))

    invoice = invoice_repo.create(InvoiceCreate(
        number="INV-LOG-001",
        issue_date=datetime.now(),
        status=InvoiceStatus.UNPAID,
        client_id=client.id,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        lines=[InvoiceLineCreate(description="Audit Item", quantity=1, unit_price=100.0)],
        original_invoice_id=None,
        reason=None,
        due_date=None,
    ))

    # 2. Log Creation
    audit_service.log_invoice_created(invoice, user_id="system_admin")

    # 3. Process Payment & Log it
    print("\n--- 2. Processing Payment ---")
    payment_amount = 200.0
    # In a real app, you'd add the payment via payment_repo first
    audit_service.log_payment_added(
        invoice, payment_amount, user_id="cashier_01", payment_method="Credit Card"
    )

    # 4. Change Status & Log it
    print("\n--- 3. Changing Status ---")
    # In a real app, you'd update via invoice_repo.update(invoice)
    audit_service.log_status_changed(
        invoice,
        new_status=str(InvoiceStatus.PARTIALLY_PAID),
        user_id="payment_processor"
    )

    # 5. Review Audit Logs
    print("\n--- 4. Reviewing Audit History for", invoice.number, "---\n")
    logs = audit_service.get_logs(invoice_id=invoice.id)

    for entry in logs:
        print(f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.action}")
        print(f"    User:  {entry.user}")
        if entry.old_value:
            print(f"    From:  {entry.old_value}")
        if entry.new_value:
            print(f"    To:    {entry.new_value}")
        if entry.notes:
            print(f"    Notes: {entry.notes}")
        print("-" * 30)

if __name__ == "__main__":
    main()
