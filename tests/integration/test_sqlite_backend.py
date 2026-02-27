"""Integration tests for SQLite storage backend."""

from collections.abc import Generator
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    PaymentCreate,
)
from sqlmodel import Session, SQLModel, create_engine

from py_invoices.backends.sqlmodel.client_repo import SQLModelClientRepository
from py_invoices.backends.sqlmodel.invoice_repo import SQLModelInvoiceRepository
from py_invoices.backends.sqlmodel.payment_repo import SQLModelPaymentRepository


@pytest.fixture
def session(tmp_path: Path) -> Generator[Session, None, None]:
    """Create a temporary SQLite database session."""
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"
    engine = create_engine(database_url)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture
def client_repo(session: Session) -> SQLModelClientRepository:
    """Create a client repository."""
    return SQLModelClientRepository(session)


@pytest.fixture
def invoice_repo(session: Session) -> SQLModelInvoiceRepository:
    """Create an invoice repository."""
    return SQLModelInvoiceRepository(session)


@pytest.fixture
def payment_repo(session: Session) -> SQLModelPaymentRepository:
    """Create a payment repository."""
    return SQLModelPaymentRepository(session)


def test_client_crud_operations(client_repo: SQLModelClientRepository) -> None:
    """Test CRUD operations for clients."""
    # Create
    client_data = ClientCreate(
        name="Test Client",
        address="123 Test St",
        tax_id="TEST-001",
        email=None,
        phone=None,
    )
    client = client_repo.create(client_data)
    assert client.id is not None
    assert client.name == "Test Client"

    # Get by ID
    fetched = client_repo.get_by_id(client.id)
    assert fetched is not None
    assert fetched.name == "Test Client"

    # Update
    client.name = "Updated Client"
    updated = client_repo.update(client)
    assert updated.name == "Updated Client"

    # Search
    results = client_repo.search("Updated")
    assert len(results) == 1
    assert results[0].name == "Updated Client"

    # Delete
    assert client_repo.delete(client.id) is True
    assert client_repo.get_by_id(client.id) is None


def test_invoice_creation_with_lines(
    client_repo: SQLModelClientRepository, invoice_repo: SQLModelInvoiceRepository
) -> None:
    """Test creating an invoice with lines."""
    # Setup client
    client = client_repo.create(
        ClientCreate(
            name="Invoice Client",
            address="456 Client Rd",
            tax_id="TAX-999",
            email=None,
            phone=None,
        )
    )

    # Create invoice
    invoice_data = InvoiceCreate(
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
            InvoiceLineCreate(description="Consulting", quantity=10, unit_price=100.0),
            InvoiceLineCreate(description="Travel", quantity=1, unit_price=50.0),
        ],
    )

    invoice = invoice_repo.create(invoice_data)
    assert invoice.id is not None
    assert len(invoice.lines) == 2
    assert invoice.total_amount == 1050.0

    # Verify storage
    fetched = invoice_repo.get_by_id(invoice.id)
    assert fetched is not None
    assert fetched.number == "INV-001"
    assert len(fetched.lines) == 2


def test_invoice_queries(
    client_repo: SQLModelClientRepository, invoice_repo: SQLModelInvoiceRepository
) -> None:
    """Test various invoice query methods."""
    client = client_repo.create(
        ClientCreate(
            name="Q Client",
            address="...",
            tax_id="...",
            email=None,
            phone=None,
        )
    )

    # Create several invoices
    for i in range(5):
        invoice_repo.create(
            InvoiceCreate(
                number=f"QUERY-{i}",
                issue_date=datetime.now(),
                status=InvoiceStatus.UNPAID if i < 3 else InvoiceStatus.PAID,
                original_invoice_id=None,
                reason=None,
                due_date=None,
                client_id=client.id,
                client_name_snapshot=client.name,
                client_address_snapshot=client.address,
                client_tax_id_snapshot=client.tax_id,
                lines=[],
            )
        )

    # Get all
    all_invoices = invoice_repo.get_all()
    assert len(all_invoices) == 5

    # Filter by status
    unpaid = invoice_repo.get_by_status(InvoiceStatus.UNPAID)
    assert len(unpaid) == 3

    # Filter by client
    client_invoices = invoice_repo.get_by_client(client.id)
    assert len(client_invoices) == 5

    # Get summary
    summary = invoice_repo.get_summary()
    assert summary["total_count"] == 5
    assert summary["unpaid_count"] == 3


def test_payment_operations(
    client_repo: SQLModelClientRepository,
    invoice_repo: SQLModelInvoiceRepository,
    payment_repo: SQLModelPaymentRepository,
) -> None:
    """Test adding and querying payments."""
    client = client_repo.create(
        ClientCreate(
            name="P Client",
            address="...",
            tax_id="...",
            email=None,
            phone=None,
        )
    )
    invoice = invoice_repo.create(
        InvoiceCreate(
            number="PAY-001",
            issue_date=datetime.now(),
            status=InvoiceStatus.UNPAID,
            original_invoice_id=None,
            reason=None,
            due_date=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[InvoiceLineCreate(description="Work", quantity=1, unit_price=1000)],
        )
    )

    # Add payment
    payment_data = PaymentCreate(
        invoice_id=invoice.id,
        amount=600.0,
        payment_date=datetime.now(),
        payment_method="Wire Transfer",
        reference=None,
    )
    payment = payment_repo.create(payment_data)
    assert payment.id is not None

    # Check totals
    total_paid = payment_repo.get_total_for_invoice(invoice.id)
    assert total_paid == 600.0

    # Get by date range (roughly covering today)
    start = datetime.now() - timedelta(hours=1)
    end = datetime.now() + timedelta(hours=1)
    payments = payment_repo.get_by_date_range(start, end)
    assert len(payments) == 1
    assert payments[0].amount == 600.0
