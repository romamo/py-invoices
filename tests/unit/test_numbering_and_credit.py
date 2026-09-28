"""Numbering series and credit note limits."""

from datetime import date

import pytest
from pydantic_invoices.schemas import (
    ClientCreate,
    Invoice,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceType,
)

from py_invoices import RepositoryFactory
from py_invoices.core.credit_service import CreditService
from py_invoices.core.numbering_service import NumberingService

YEAR = date.today().year


@pytest.fixture
def factory() -> RepositoryFactory:
    return RepositoryFactory(backend="memory")


def _invoice(factory: RepositoryFactory, number: str, amount: str = "100") -> Invoice:
    client = factory.create_client_repository().create(ClientCreate(name=f"C {number}"))
    return factory.create_invoice_repository().create(
        InvoiceCreate(
            number=number,
            client_id=client.id,
            status=InvoiceStatus.SENT,
            lines=[
                InvoiceLineCreate(description="A", quantity=1, unit_price=amount),
                InvoiceLineCreate(description="B", quantity=1, unit_price=amount),
            ],
        )
    )


def test_next_number_continues_from_highest_issued(factory: RepositoryFactory) -> None:
    _invoice(factory, f"INV-{YEAR}-0007")
    _invoice(factory, "CUSTOM-1")
    _invoice(factory, f"INV-{YEAR - 1}-0042")
    service = NumberingService(invoice_repo=factory.create_invoice_repository())
    assert service.generate_number() == f"INV-{YEAR}-0008"


def test_deleting_an_invoice_does_not_reuse_a_lower_number(factory: RepositoryFactory) -> None:
    first = _invoice(factory, f"INV-{YEAR}-0001")
    _invoice(factory, f"INV-{YEAR}-0002")
    repo = factory.create_invoice_repository()
    repo.delete(first.id)
    assert NumberingService(invoice_repo=repo).generate_number() == f"INV-{YEAR}-0003"


def test_sequence_restarts_each_year(factory: RepositoryFactory) -> None:
    _invoice(factory, f"INV-{YEAR - 1}-0099")
    service = NumberingService(invoice_repo=factory.create_invoice_repository())
    assert service.generate_number() == f"INV-{YEAR}-0001"


def test_credit_notes_have_their_own_series(factory: RepositoryFactory) -> None:
    original = _invoice(factory, f"INV-{YEAR}-0005")
    repo = factory.create_invoice_repository()
    note = CreditService(repo).create_credit_note(original, reason="x", refund_lines_indices=[0])
    assert note.number == f"CN-{YEAR}-0001"
    assert NumberingService(invoice_repo=repo).generate_number() == f"INV-{YEAR}-0006"


def test_cannot_credit_more_than_the_invoice_total(factory: RepositoryFactory) -> None:
    original = _invoice(factory, "INV-A")
    service = CreditService(factory.create_invoice_repository())
    service.create_credit_note(original, reason="first", refund_lines_indices=[0])
    with pytest.raises(ValueError, match="exceeds"):
        service.create_credit_note(original, reason="again")


def test_full_credit_marks_invoice_credited(factory: RepositoryFactory) -> None:
    original = _invoice(factory, "INV-B")
    repo = factory.create_invoice_repository()
    service = CreditService(repo)
    service.create_credit_note(original, reason="first", refund_lines_indices=[0])
    assert repo.get_by_id(original.id).status is InvoiceStatus.SENT
    service.create_credit_note(original, reason="rest", refund_lines_indices=[1])
    assert repo.get_by_id(original.id).status is InvoiceStatus.CREDITED


def test_rejects_bad_line_indices_and_credit_notes(factory: RepositoryFactory) -> None:
    original = _invoice(factory, "INV-C")
    service = CreditService(factory.create_invoice_repository())
    with pytest.raises(ValueError, match="out of range"):
        service.create_credit_note(original, refund_lines_indices=[5])
    with pytest.raises(ValueError, match="Duplicate"):
        service.create_credit_note(original, refund_lines_indices=[0, 0])
    note = service.create_credit_note(original, refund_lines_indices=[0])
    assert note.type is InvoiceType.CREDIT_NOTE
    with pytest.raises(ValueError, match="another credit note"):
        service.create_credit_note(note.model_copy(update={"status": InvoiceStatus.SENT}))


def test_crediting_an_old_invoice_does_not_fail_on_due_date(factory: RepositoryFactory) -> None:
    client = factory.create_client_repository().create(ClientCreate(name="Old"))
    repo = factory.create_invoice_repository()
    old = repo.create(
        InvoiceCreate(
            number="INV-OLD",
            client_id=client.id,
            status=InvoiceStatus.SENT,
            issue_date=date(2020, 1, 1),
            due_date=date(2020, 2, 1),
            lines=[InvoiceLineCreate(description="A", quantity=1, unit_price="10")],
        )
    )
    note = CreditService(repo).create_credit_note(old, reason="late")
    assert note.due_date == date.today()
