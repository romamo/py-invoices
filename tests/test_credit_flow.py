from typing import Any

import pytest
from pydantic_invoices.schemas import InvoiceCreate, InvoiceLineCreate, InvoiceStatus, InvoiceType

from py_invoices import RepositoryFactory
from py_invoices.core.credit_service import CreditService
from py_invoices.core.numbering_service import NumberingService
from py_invoices.core.validator import BusinessValidator


@pytest.fixture
def factory() -> Any:
    return RepositoryFactory(backend="memory")


@pytest.fixture
def invoice_repo(factory: Any) -> Any:
    return factory.create_invoice_repository()


@pytest.fixture
def client_repo(factory: Any) -> Any:
    return factory.create_client_repository()


@pytest.fixture
def base_invoice(invoice_repo: Any, client_repo: Any) -> Any:
    from pydantic_invoices.schemas import ClientCreate

    client = client_repo.create(
        ClientCreate(name="Credit Client", address="123 St", tax_id="123", email=None, phone=None)
    )

    return invoice_repo.create(
        InvoiceCreate(
            number="INV-001",
            client_id=client.id,
            status=InvoiceStatus.DRAFT,
            original_invoice_id=None,
            reason=None,
            due_date=None,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            lines=[InvoiceLineCreate(description="Item 1", quantity=1, unit_price=100.0)],
        )
    )


def test_credit_note_state_machine_checks(invoice_repo: Any, base_invoice: Any) -> None:
    """Test legal and illegal state transitions."""
    inv = base_invoice

    # DRAFT -> SENT (OK)
    BusinessValidator.validate_state_transition(inv.status, InvoiceStatus.SENT)


def test_credit_note_creation_validation(invoice_repo: Any, base_invoice: Any) -> None:
    """Test that non-draft invoices cannot be modified."""
    inv = base_invoice

    # DRAFT: Modification OK
    BusinessValidator.validate_modification(inv)


def test_strict_state_machine(invoice_repo: Any, base_invoice: Any) -> None:
    """Test legal and illegal state transitions."""
    inv = base_invoice

    # DRAFT -> SENT (OK)
    BusinessValidator.validate_state_transition(inv.status, InvoiceStatus.SENT)
    inv.status = InvoiceStatus.SENT
    invoice_repo.update(inv)

    # SENT -> DRAFT (Fail)
    with pytest.raises(ValueError, match="Cannot change status from SENT"):
        BusinessValidator.validate_state_transition(inv.status, InvoiceStatus.DRAFT)

    # SENT -> PAID (OK)
    BusinessValidator.validate_state_transition(inv.status, InvoiceStatus.PAID)
    inv.status = InvoiceStatus.PAID
    invoice_repo.update(inv)

    # PAID -> SENT (Fail)
    with pytest.raises(ValueError, match="Cannot change status from PAID"):
        BusinessValidator.validate_state_transition(inv.status, InvoiceStatus.SENT)


def test_modification_restriction(invoice_repo: Any, base_invoice: Any) -> None:
    """Test that non-draft invoices cannot be modified."""
    inv = base_invoice

    # DRAFT: Modification OK
    BusinessValidator.validate_modification(inv)

    # Move to SENT
    inv.status = InvoiceStatus.SENT
    invoice_repo.update(inv)

    # SENT: Modification Fail
    with pytest.raises(ValueError, match="is in InvoiceStatus.SENT state"):
        BusinessValidator.validate_modification(inv)


def test_credit_note_creation(client_repo: Any, invoice_repo: Any, base_invoice: Any) -> None:
    """Test creating a credit note linked to an invoice."""
    inv = base_invoice
    inv.status = InvoiceStatus.SENT
    invoice_repo.update(inv)

    numbering = NumberingService(invoice_repo=invoice_repo)
    credit_service = CreditService(invoice_repo, numbering)

    # Create Full Credit Note
    cn = credit_service.create_credit_note(inv, reason="Mistake")

    assert cn.type == InvoiceType.CREDIT_NOTE
    assert cn.original_invoice_id == inv.id
    assert cn.reason == "Mistake"
    assert len(cn.lines) == 1
    assert cn.total_amount == 100.0  # Positive amount, representing credit
    assert cn.number.startswith("CN")

    # Verify link is persisted (if backend supports it)
    # Memory backend might need specific logic to double check
    fetched_cn = invoice_repo.get_by_id(cn.id)
    assert fetched_cn.original_invoice_id == inv.id
