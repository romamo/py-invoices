"""DRAFT -> issue lifecycle, locked issued invoices (#5); audited master data (#7)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceType,
)
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.core.audit_service import AuditEntity, AuditLogEntry, AuditService
from py_invoices.core.credit_service import CreditService
from py_invoices.core.lifecycle import InvoiceLockedError, content_hash
from py_invoices.operations import payment_notes
from py_invoices.operations.errors import (
    InvoiceNotDraftError,
    LineSelectionError,
    PaymentNoteStateError,
)
from py_invoices.operations.integrity import Finding, check_stored_invoices
from py_invoices.operations.invoices import (
    CompanyOverrides,
    DraftChanges,
    LineChange,
    NewInvoice,
    clone_invoice,
    create_invoice,
    issue_invoice,
    list_overdue_invoices,
    render_invoice_html,
    update_invoice,
)

BACKENDS = ["memory", "files", "sqlite"]
YEAR = date.today().year


def _factory(backend: str, tmp_path: Path) -> RepositoryFactory:
    if backend == "files":
        return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="json")
    if backend == "sqlite":
        return RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    return RepositoryFactory("memory")


def _new(amount: str = "100", issue: bool = False) -> NewInvoice:
    return NewInvoice(
        amount=Money(amount, "EUR"),
        description="Work",
        client_name="Buyer",
        issue=issue,
    )


def _audit(factory: RepositoryFactory) -> list[AuditLogEntry]:
    return AuditService(audit_repo=factory.create_audit_repository()).get_logs()


@pytest.mark.parametrize("backend", BACKENDS)
def test_create_makes_a_draft_and_issue_locks_it(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    draft = create_invoice(factory, _new()).invoice
    assert (draft.status, draft.number, draft.content_hash) == (
        InvoiceStatus.DRAFT,
        f"DRAFT-{draft.id}",
        None,
    )

    issued = issue_invoice(factory, draft.number)
    assert issued.number == f"INV-{YEAR}-0001"
    assert issued.status is InvoiceStatus.SENT
    assert issued.content_hash == content_hash(issued)
    assert issued.lines[0].unit_price == Money("100", "EUR")
    assert [e.action for e in _audit(factory) if e.invoice_id == issued.id] == [
        "CREATED",
        "ISSUED",
    ]

    repo = factory.create_invoice_repository()
    changed_line = issued.lines[0].model_copy(update={"unit_price": Money("1", "EUR")})
    with pytest.raises(InvoiceLockedError, match="lines"):
        repo.update(issued.model_copy(update={"lines": [changed_line]}))
    with pytest.raises(InvoiceLockedError):
        repo.delete(issued.id)
    with pytest.raises(ValueError, match="SENT to DRAFT"):
        repo.update(issued.model_copy(update={"status": InvoiceStatus.DRAFT}))
    paid = repo.update(issued.model_copy(update={"status": InvoiceStatus.PAID}))
    assert paid.status is InvoiceStatus.PAID
    with pytest.raises(InvoiceNotDraftError):
        update_invoice(factory, issued.number, DraftChanges(issue_date=date(YEAR, 1, 1)))
    with pytest.raises(InvoiceNotDraftError):
        issue_invoice(factory, issued.number)


@pytest.mark.parametrize("backend", BACKENDS)
def test_draft_edits_keep_currency_and_reach_storage(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    draft = create_invoice(factory, _new()).invoice
    edited = update_invoice(
        factory,
        draft.number,
        DraftChanges(line_change=LineChange(unit_price=Decimal("950"), quantity=2)),
    )
    stored = factory.create_invoice_repository().get_by_id(draft.id)
    assert stored is not None
    assert stored.lines[0].unit_price == Money("950", "EUR")
    assert stored.total_amount == Money("1900", "EUR") == edited.total_amount
    assert "UPDATED" in [e.action for e in _audit(factory)]


def test_numbers_follow_the_order_of_issue(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    first = create_invoice(factory, _new()).invoice
    second = create_invoice(factory, _new()).invoice
    assert issue_invoice(factory, second.number).number == f"INV-{YEAR}-0001"
    assert issue_invoice(factory, first.number).number == f"INV-{YEAR}-0002"


def test_issue_date_moves_the_due_date(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    draft = create_invoice(factory, _new()).invoice
    assert draft.due_date is not None
    issued = issue_invoice(factory, draft.number, date(YEAR + 1, 1, 1))
    assert issued.due_date == date(YEAR + 1, 1, 1) + (draft.due_date - draft.issue_date)


def test_create_with_issue_is_one_step(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    invoice = create_invoice(factory, _new(issue=True)).invoice
    assert (invoice.number, invoice.status) == (f"INV-{YEAR}-0001", InvoiceStatus.SENT)


def test_clone_overrides_the_only_line_and_refuses_several(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    original = create_invoice(factory, _new(issue=True)).invoice
    cloned = clone_invoice(
        factory,
        original.number,
        date(YEAR, 6, 1),
        line_change=LineChange(unit_price=Decimal("120"), description="June"),
        due_date=date(YEAR, 6, 15),
    ).invoice
    assert cloned.status is InvoiceStatus.DRAFT
    assert (cloned.lines[0].description, cloned.lines[0].unit_price) == (
        "June",
        Money("120", "EUR"),
    )
    assert cloned.due_date == date(YEAR, 6, 15)

    client = factory.create_client_repository().create(ClientCreate(name="Multi"))
    multi = factory.create_invoice_repository().create(
        InvoiceCreate(
            number="M-1",
            client_id=client.id,
            status=InvoiceStatus.SENT,
            lines=[
                InvoiceLineCreate(description="A", quantity=1, unit_price=Money("1", "EUR")),
                InvoiceLineCreate(description="B", quantity=1, unit_price=Money("2", "EUR")),
            ],
        )
    )
    with pytest.raises(LineSelectionError):
        clone_invoice(factory, multi.number, date(YEAR, 6, 1), LineChange(quantity=2))
    draft = clone_invoice(factory, multi.number, date(YEAR, 6, 1)).invoice
    with pytest.raises(LineSelectionError):
        update_invoice(factory, draft.number, DraftChanges(line_change=LineChange(quantity=2)))
    edited = update_invoice(
        factory, draft.number, DraftChanges(line_change=LineChange(quantity=3), line=1)
    )
    assert [line.quantity for line in edited.lines] == [1, 3]


def test_drafts_are_not_overdue_and_render_with_a_watermark(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    draft = create_invoice(
        factory,
        NewInvoice(
            amount=Money("5", "EUR"),
            description="Old",
            client_name="Buyer",
            company=CompanyOverrides(name="Seller", address="Road 1"),
        ),
    ).invoice
    draft = update_invoice(
        factory,
        draft.number,
        DraftChanges(issue_date=date(2000, 1, 1), due_date=date(2000, 1, 31)),
    )
    assert list_overdue_invoices(factory) == []
    assert 'class="draft-watermark"' in render_invoice_html(factory, draft)
    issued = issue_invoice(factory, draft.number)
    assert [i.number for i in list_overdue_invoices(factory)] == [issued.number]
    assert 'class="draft-watermark"' not in render_invoice_html(factory, issued)


def test_credit_notes_are_issued_and_locked(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    invoice = create_invoice(factory, _new(issue=True)).invoice
    repo = factory.create_invoice_repository()
    note = CreditService(repo).create_credit_note(invoice, reason="refund")
    assert note.type is InvoiceType.CREDIT_NOTE
    assert note.status is InvoiceStatus.SENT
    assert note.content_hash == content_hash(note)
    original = repo.get_by_id(invoice.id)
    assert original is not None and original.status is InvoiceStatus.CREDITED


def test_legacy_unpaid_invoice_follows_the_sent_rules(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    client = factory.create_client_repository().create(ClientCreate(name="Legacy"))
    repo = factory.create_invoice_repository()
    legacy = repo.create(
        InvoiceCreate(
            number="INV-2025-0001",
            client_id=client.id,
            status=InvoiceStatus.UNPAID,
            lines=[InvoiceLineCreate(description="A", quantity=1, unit_price=Money("1", "EUR"))],
        )
    )
    with pytest.raises(ValueError, match="SENT to DRAFT"):
        repo.update(legacy.model_copy(update={"status": InvoiceStatus.DRAFT}))
    CreditService(repo).create_credit_note(legacy, reason="void")
    credited = repo.get_by_id(legacy.id)
    assert credited is not None and credited.status is InvoiceStatus.CREDITED


def test_validate_data_finds_an_edited_file_and_seals_legacy_invoices(tmp_path: Path) -> None:
    factory = _factory("files", tmp_path)
    issued = create_invoice(factory, _new(issue=True)).invoice
    client = factory.create_client_repository().create(ClientCreate(name="Legacy"))
    factory.create_invoice_repository().create(
        InvoiceCreate(
            number="INV-2025-0009",
            client_id=client.id,
            status=InvoiceStatus.UNPAID,
            lines=[InvoiceLineCreate(description="A", quantity=1, unit_price=Money("1", "EUR"))],
        )
    )
    create_invoice(factory, _new())  # a draft, never checked

    report = check_stored_invoices(factory)
    assert report.ok and (report.checked, report.drafts) == (2, 1)
    assert [(f.number, f.finding) for f in report.findings] == [("INV-2025-0009", Finding.UNSEALED)]

    sealed = check_stored_invoices(factory, seal=True)
    assert [f.finding for f in sealed.findings] == [Finding.SEALED]
    assert "SEALED" in [e.action for e in _audit(factory)]
    assert check_stored_invoices(factory).findings == []

    # A hand edit of the stored file, as in the issue
    path = tmp_path / "data" / "invoices" / f"{issued.id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["lines"][0]["unit_price"]["amount"] = "1.00"
    path.write_text(json.dumps(data), encoding="utf-8")
    tampered = check_stored_invoices(factory)
    assert not tampered.ok
    assert [(f.number, f.finding) for f in tampered.findings] == [(issued.number, Finding.TAMPERED)]


@pytest.mark.parametrize("backend", BACKENDS)
def test_payment_notes_change_through_new_notes_and_are_audited(
    backend: str, tmp_path: Path
) -> None:
    factory = _factory(backend, tmp_path)
    old = payment_notes.create_payment_note(
        factory, PaymentNoteCreate(title="Bank", content="IBAN OLD", is_default=True)
    )
    new = payment_notes.create_payment_note(
        factory, PaymentNoteCreate(title="Bank", content="IBAN NEW")
    )
    with pytest.raises(PaymentNoteStateError, match="default"):
        payment_notes.deactivate_payment_note(factory, old.id)
    payment_notes.set_default_payment_note(factory, new.id)
    retired = payment_notes.deactivate_payment_note(factory, old.id)
    assert not retired.is_active
    with pytest.raises(PaymentNoteStateError, match="inactive"):
        payment_notes.set_default_payment_note(factory, old.id)
    default = payment_notes.default_payment_note(factory, None)
    assert default is not None and default.id == new.id

    note_events = [
        (e.entity_id, e.action)
        for e in _audit(factory)
        if e.entity_type is AuditEntity.PAYMENT_NOTE
    ]
    assert note_events == [
        (old.id, "CREATED"),
        (new.id, "CREATED"),
        (new.id, "SET_DEFAULT"),
        (old.id, "DEACTIVATED"),
    ]
    assert all(e.id is not None for e in _audit(factory))


def test_audit_entries_name_their_record() -> None:
    legacy = AuditLogEntry.model_validate({"invoice_id": 5, "action": "CREATED"})
    assert (legacy.entity_type, legacy.entity_id) == (AuditEntity.INVOICE, 5)
    with pytest.raises(ValueError, match="no invoice_id"):
        AuditLogEntry(entity_type=AuditEntity.CLIENT, entity_id=1, invoice_id=1, action="CREATED")
    with pytest.raises(ValueError, match="differs"):
        AuditLogEntry(entity_id=1, invoice_id=2, action="CREATED")


@pytest.mark.parametrize("backend", BACKENDS)
def test_hash_survives_each_backends_round_trip(backend: str, tmp_path: Path) -> None:
    """SQL Numeric reads 900 back as 900.00; the hash must not see a change."""
    factory = _factory(backend, tmp_path)
    draft = create_invoice(factory, _new(amount="900")).invoice
    update_invoice(
        factory,
        draft.number,
        DraftChanges(line_change=LineChange(unit_price=Decimal("899.5"))),
    )
    issue_invoice(factory, draft.number)
    assert check_stored_invoices(factory).findings == []


def test_issue_snapshots_payment_notes_a_draft_lacks(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    note = payment_notes.create_payment_note(
        factory, PaymentNoteCreate(title="Bank", content="IBAN AT ISSUE")
    )
    client = factory.create_client_repository().create(ClientCreate(name="Api"))
    draft = factory.create_invoice_repository().create(
        InvoiceCreate(
            number="API-1",
            client_id=client.id,
            payment_note_ids=[note.id],
            lines=[InvoiceLineCreate(description="A", quantity=1, unit_price=Money("1", "EUR"))],
        )
    )
    assert draft.payment_notes_snapshot is None
    issued = issue_invoice(factory, draft.number)
    assert issued.number == "API-1"
    assert [n.content for n in issued.payment_notes_snapshot or []] == ["IBAN AT ISSUE"]
