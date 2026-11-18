"""Each issuing company numbers its documents in its own series (#12)."""

from datetime import date
from pathlib import Path

import pytest
from pydantic_invoices.schemas import (
    ClientCreate,
    Invoice,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)

from py_invoices import RepositoryFactory
from py_invoices.core.audit_service import AuditEntity, AuditService
from py_invoices.core.numbering_service import NumberingService, NumberTakenError
from py_invoices.operations.companies import create_company, set_number_prefix
from py_invoices.operations.credit_notes import create_credit_note
from py_invoices.operations.errors import NumberPrefixError, SeriesNumberTakenError
from py_invoices.operations.invoices import issue_invoice

BACKENDS = ["memory", "files", "sqlite"]
YEAR = date.today().year


def _factory(backend: str, tmp_path: Path) -> RepositoryFactory:
    if backend == "files":
        return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="json")
    if backend == "sqlite":
        return RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    return RepositoryFactory("memory")


def _company(factory: RepositoryFactory, name: str, prefix: str | None = None) -> int:
    return create_company(factory, name, None, None, None, None, number_prefix=prefix).id


def _invoice(factory: RepositoryFactory, number: str, company_id: int) -> Invoice:
    """An issued invoice with the given number, or a draft for a DRAFT- number."""
    client = factory.create_client_repository().create(ClientCreate(name=f"C {number}"))
    return factory.create_invoice_repository().create(
        InvoiceCreate(
            number=number,
            issue_date=date(YEAR, 1, 1),
            status=InvoiceStatus.DRAFT if number.startswith("DRAFT-") else InvoiceStatus.SENT,
            client_id=client.id,
            company_id=company_id,
            lines=[InvoiceLineCreate(description="Work", quantity=1, unit_price="100")],
        )
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_each_company_continues_its_own_series(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    first = _company(factory, "First")
    second = _company(factory, "Second", prefix="SC")
    for sequence in range(1, 4):
        _invoice(factory, f"INV-{YEAR}-{sequence:04d}", first)
    _invoice(factory, f"SC-INV-{YEAR}-0001", second)

    assert issue_invoice(factory, _invoice(factory, "DRAFT-a", second).number).number == (
        f"SC-INV-{YEAR}-0002"
    )
    assert issue_invoice(factory, _invoice(factory, "DRAFT-b", first).number).number == (
        f"INV-{YEAR}-0004"
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_credit_notes_follow_the_company_series(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    first = _company(factory, "First")
    second = _company(factory, "Second", prefix="SC")
    _invoice(factory, f"INV-{YEAR}-0001", first)
    create_credit_note(factory, f"INV-{YEAR}-0001", "refund")
    _invoice(factory, f"SC-INV-{YEAR}-0001", second)

    note = create_credit_note(factory, f"SC-INV-{YEAR}-0001", "refund").credit_note
    assert note.number == f"SC-CN-{YEAR}-0001"
    assert note.company_id == second


def test_next_sequence_counts_only_the_issuing_company() -> None:
    factory = RepositoryFactory("memory")
    _invoice(factory, f"INV-{YEAR}-0005", company_id=1)
    service = NumberingService(invoice_repo=factory.create_invoice_repository())
    assert service.next_sequence(YEAR, company_id=2) == 1
    assert service.next_sequence(YEAR, company_id=1) == 6
    assert service.next_sequence(YEAR) == 6


def test_a_number_held_by_another_company_fails_fast() -> None:
    factory = RepositoryFactory("memory")
    _invoice(factory, f"INV-{YEAR}-0001", company_id=1)
    service = NumberingService(invoice_repo=factory.create_invoice_repository())
    with pytest.raises(NumberTakenError):
        service.generate_number(year=YEAR, company_id=2)


def test_mixed_legacy_series_continue_from_each_company_highest(tmp_path: Path) -> None:
    """A store from before #12: both companies took numbers from one INV series."""
    factory = _factory("files", tmp_path)
    first = _company(factory, "First")
    second = _company(factory, "Second")
    for sequence in range(2, 5):
        _invoice(factory, f"INV-{YEAR}-{sequence:04d}", first)
    _invoice(factory, f"INV-{YEAR}-0001", second)
    _invoice(factory, f"INV-{YEAR}-0005", second)

    # Each continues from its own highest number
    assert issue_invoice(factory, _invoice(factory, "DRAFT-a", second).number).number == (
        f"INV-{YEAR}-0006"
    )
    # The first company's next own number, 0005, is held by the second company
    draft = _invoice(factory, "DRAFT-b", first)
    with pytest.raises(SeriesNumberTakenError) as raised:
        issue_invoice(factory, draft.number)
    assert (raised.value.number, raised.value.company_id) == (f"INV-{YEAR}-0005", first)

    set_number_prefix(factory, first, "FC")
    assert issue_invoice(factory, draft.number).number == f"FC-INV-{YEAR}-0001"
    stored = factory.create_invoice_repository().get_by_number(f"INV-{YEAR}-0004")
    assert stored is not None and stored.company_id == first


def test_set_number_prefix_validates_and_audits() -> None:
    factory = RepositoryFactory("memory")
    first = _company(factory, "First", prefix="FC")
    second = _company(factory, "Second")
    with pytest.raises(NumberPrefixError):
        set_number_prefix(factory, second, "FC")
    with pytest.raises(NumberPrefixError):
        set_number_prefix(factory, second, "S/C")
    with pytest.raises(NumberPrefixError):
        _company(factory, "Third", prefix="FC")

    assert set_number_prefix(factory, second, "SC").number_prefix == "SC"
    stored = factory.create_company_repository().get_by_id(first)
    assert stored is not None and stored.number_prefix == "FC"
    entry = AuditService(audit_repo=factory.create_audit_repository()).get_logs()[-1]
    assert (entry.entity_type, entry.entity_id, entry.action, entry.new_value) == (
        AuditEntity.COMPANY,
        second,
        "NUMBER_PREFIX_SET",
        "SC",
    )
