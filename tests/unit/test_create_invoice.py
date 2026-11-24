"""`create_invoice` picks the issuing company and the payment notes printed on the invoice."""

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate, PaymentNoteSnapshot
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.operations.companies import create_company, set_number_prefix
from py_invoices.operations.errors import (
    CompanyInactiveError,
    CompanyNotFoundError,
    PaymentNoteMissingError,
    PaymentNoteUnusableError,
)
from py_invoices.operations.invoices import NewInvoice, clone_invoice, create_invoice
from py_invoices.operations.payment_notes import create_payment_note, deactivate_payment_note

BACKENDS = ["memory", "files", "sqlite"]
YEAR = date.today().year


@pytest.fixture(params=BACKENDS)
def factory(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[RepositoryFactory]:
    if request.param == "files":
        created = RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="json")
    elif request.param == "sqlite":
        created = RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    else:
        created = RepositoryFactory("memory")
    yield created
    created.cleanup()


def _company(factory: RepositoryFactory, name: str, prefix: str | None = None) -> int:
    company_id = create_company(factory, name, None, f"{name} Road", None, None).id
    if prefix:
        set_number_prefix(factory, company_id, prefix)
    return company_id


def _note(
    factory: RepositoryFactory, content: str, company_id: int | None, *, default: bool = False
) -> int:
    return create_payment_note(
        factory,
        PaymentNoteCreate(title="Bank", content=content, company_id=company_id, is_default=default),
    ).id


def _new(**fields: Any) -> NewInvoice:
    return NewInvoice(
        amount=Money(Decimal("10"), "USD"), description="Work", client_name="Acme", **fields
    )


def _contents(snapshot: list[PaymentNoteSnapshot] | None) -> list[str]:
    return [note.content for note in snapshot or []]


def test_the_issuing_companys_default_note_is_attached(factory: RepositoryFactory) -> None:
    first = _company(factory, "First")
    second = _company(factory, "Second")
    _note(factory, "IBAN FIRST", first, default=True)
    other = _note(factory, "IBAN SECOND", second, default=True)

    invoice = create_invoice(factory, _new(company_id=second)).invoice
    assert invoice.payment_note_ids == [other]
    assert _contents(invoice.payment_notes_snapshot) == ["IBAN SECOND"]


def test_the_global_default_note_serves_a_company_without_one(factory: RepositoryFactory) -> None:
    _company(factory, "First")
    other = _company(factory, "Second")
    _note(factory, "IBAN OTHER", other, default=True)
    shared = _note(factory, "IBAN SHARED", None, default=True)

    invoice = create_invoice(factory, _new()).invoice
    assert invoice.payment_note_ids == [shared]


def test_no_default_note_leaves_the_invoice_without_notes(factory: RepositoryFactory) -> None:
    _company(factory, "First")
    _note(factory, "IBAN NOT DEFAULT", None)
    invoice = create_invoice(factory, _new()).invoice
    assert (invoice.payment_note_ids, invoice.payment_notes_snapshot) == ([], [])


def test_chosen_notes_replace_the_default(factory: RepositoryFactory) -> None:
    company = _company(factory, "First")
    _note(factory, "IBAN DEFAULT", company, default=True)
    usd = _note(factory, "IBAN USD", company)
    eur = _note(factory, "IBAN EUR", None)

    invoice = create_invoice(factory, _new(payment_note_ids=(eur, usd))).invoice
    assert invoice.payment_note_ids == [eur, usd]
    assert _contents(invoice.payment_notes_snapshot) == ["IBAN EUR", "IBAN USD"]


def test_a_bank_account_alone_replaces_the_default(factory: RepositoryFactory) -> None:
    company = _company(factory, "First")
    _note(factory, "IBAN DEFAULT", company, default=True)
    invoice = create_invoice(factory, _new(bank_account="IBAN TYPED")).invoice
    assert invoice.payment_note_ids == []
    assert _contents(invoice.payment_notes_snapshot) == ["IBAN TYPED"]


def test_chosen_notes_and_a_bank_account_are_both_printed(factory: RepositoryFactory) -> None:
    company = _company(factory, "First")
    usd = _note(factory, "IBAN USD", company)
    invoice = create_invoice(
        factory, _new(payment_note_ids=(usd,), bank_account="IBAN TYPED")
    ).invoice
    assert invoice.payment_note_ids == [usd]
    assert _contents(invoice.payment_notes_snapshot) == ["IBAN USD", "IBAN TYPED"]


def test_a_clone_carries_the_chosen_notes(factory: RepositoryFactory) -> None:
    company = _company(factory, "First")
    usd = _note(factory, "IBAN USD", company)
    original = create_invoice(factory, _new(payment_note_ids=(usd,), issue=True)).invoice
    clone = clone_invoice(factory, original.number, date.today()).invoice
    assert _contents(clone.payment_notes_snapshot) == ["IBAN USD"]


def test_unknown_inactive_and_foreign_notes_are_refused(factory: RepositoryFactory) -> None:
    first = _company(factory, "First")
    second = _company(factory, "Second")
    foreign = _note(factory, "IBAN SECOND", second)
    retired = _note(factory, "IBAN OLD", first)
    deactivate_payment_note(factory, retired)

    with pytest.raises(PaymentNoteMissingError):
        create_invoice(factory, _new(payment_note_ids=(999,)))
    with pytest.raises(PaymentNoteUnusableError, match="inactive"):
        create_invoice(factory, _new(payment_note_ids=(retired,)))
    with pytest.raises(PaymentNoteUnusableError, match="company 2"):
        create_invoice(factory, _new(company_id=first, payment_note_ids=(foreign,)))
    assert factory.create_invoice_repository().get_all() == []


def test_company_id_picks_the_issuer_and_its_number_series(factory: RepositoryFactory) -> None:
    _company(factory, "First", "FA")
    second = _company(factory, "Second", "SB")

    invoice = create_invoice(factory, _new(company_id=second, issue=True)).invoice
    assert invoice.company_id == second
    assert invoice.company_name_snapshot == "Second"
    assert invoice.number == f"SB-INV-{YEAR}-0001"


def test_unknown_and_inactive_companies_are_refused(factory: RepositoryFactory) -> None:
    _company(factory, "First")
    closed = _company(factory, "Closed")
    repo = factory.create_company_repository()
    record = repo.get_by_id(closed)
    assert record is not None
    repo.update(record.model_copy(update={"is_active": False}))

    with pytest.raises(CompanyNotFoundError):
        create_invoice(factory, _new(company_id=99))
    with pytest.raises(CompanyInactiveError):
        create_invoice(factory, _new(company_id=closed))
    assert factory.create_invoice_repository().get_all() == []
