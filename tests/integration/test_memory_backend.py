"""Integration tests for memory backend."""
from datetime import date, datetime, timedelta
from typing import Any

from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    PaymentCreate,
)


def test_client_crud_operations(client_repo: Any) -> None:
    """Test client CRUD operations."""
    # Create
    client = client_repo.create(
        ClientCreate(
            name="Test Client",
            address="123 Test St",
            tax_id="12345",
            email="test@example.com",
            phone=None,
        )
    )
    assert client.id is not None
    assert client.name == "Test Client"

    # Read
    retrieved = client_repo.get_by_id(client.id)
    assert retrieved is not None
    assert retrieved.name == "Test Client"

    # Update
    client.name = "Updated Client"
    updated = client_repo.update(client)
    assert updated is not None
    assert updated.name == "Updated Client"

    # Delete
    assert client_repo.delete(client.id) is True
    assert client_repo.get_by_id(client.id) is None


def test_invoice_creation_with_lines(
    client_repo: Any, invoice_repo: Any
) -> None:
    """Test creating invoice with line items."""
    # Create client first
    client = client_repo.create(
        ClientCreate(
            name="Invoice Test Client",
            address="456 Invoice St",
            tax_id="67890",
            email=None,
            phone=None,
        )
    )

    # Create invoice
    invoice = invoice_repo.create(
        InvoiceCreate(
            number="INV-001",
            issue_date=datetime.now(),
            status=InvoiceStatus.UNPAID,
            original_invoice_id=None,
            reason=None,
            due_date=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[
                InvoiceLineCreate(
                    description="Item 1",
                    quantity=2,
                    unit_price=100.0,
                ),
                InvoiceLineCreate(
                    description="Item 2",
                    quantity=1,
                    unit_price=50.0,
                ),
            ],
        )
    )

    assert invoice.id is not None
    assert invoice.number == "INV-001"
    assert len(invoice.lines) == 2
    assert invoice.total_amount == 250.0


def test_invoice_queries(client_repo: Any, invoice_repo: Any) -> None:
    """Test invoice query methods."""
    # Create client
    client = client_repo.create(
        ClientCreate(
            name="Query Test",
            address="789 Query Ave",
            tax_id="11111",
            email=None,
            phone=None,
        )
    )

    # Create multiple invoices
    invoice_repo.create(
        InvoiceCreate(
            number="INV-001",
            issue_date=datetime.now(),
            status=InvoiceStatus.UNPAID,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            due_date=date.today() + timedelta(days=7),
            lines=[InvoiceLineCreate(description="Test 1", quantity=1, unit_price=100)],
        )
    )
    invoice_repo.create(
        InvoiceCreate(
            number="INV-002",
            issue_date=datetime.now(),
            status=InvoiceStatus.UNPAID,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            due_date=date.today() - timedelta(days=1),
            lines=[InvoiceLineCreate(description="Test 2", quantity=1, unit_price=200)],
        )
    )

    # Test queries
    all_invoices = invoice_repo.get_all()
    assert len(all_invoices) == 2

    # Test get_by_status
    unpaid = invoice_repo.get_by_status(InvoiceStatus.UNPAID)
    assert len(unpaid) == 2 # Both INV-001 and INV-002 are now UNPAID
    assert unpaid[0].number == "INV-001"

    # Test get_overdue
    overdue = invoice_repo.get_overdue()
    assert len(overdue) == 1
    assert overdue[0].number == "INV-002"

    # Test summary
    summary = invoice_repo.get_summary()
    assert summary["total_count"] == 2
    assert summary["paid_count"] == 0
    assert summary["unpaid_count"] == 2
    assert summary["overdue_count"] == 1


def test_payment_operations(
    client_repo: Any, invoice_repo: Any, payment_repo: Any
) -> None:
    """Test payment operations."""
    # Create client and invoice
    client = client_repo.create(
        ClientCreate(
            name="Payment Test",
            address="321 Pay St",
            tax_id="22222",
            email=None,
            phone=None,
        )
    )

    invoice = invoice_repo.create(
        InvoiceCreate(
            number="INV-PAY",
            issue_date=datetime.now(),
            due_date=date.today() + timedelta(days=7),
            status=InvoiceStatus.UNPAID,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[InvoiceLineCreate(description="Test", quantity=1, unit_price=500)],
        )
    )

    # Create payment
    payment = payment_repo.create(
        PaymentCreate(
            invoice_id=invoice.id,
            amount=250.0,
            payment_date=datetime.now(),
            payment_method="Bank Transfer",
            reference=None,
        )
    )

    assert payment.id is not None
    assert payment.amount == 250.0

    # Get payments for invoice
    payments = payment_repo.get_by_invoice(invoice.id)
    assert len(payments) == 1
    assert payments[0].amount == 250.0

    # Get by date range
    start = datetime.now() - timedelta(hours=1)
    end = datetime.now() + timedelta(hours=1)
    payments = payment_repo.get_by_date_range(start, end)
    assert len(payments) == 1
