"""Issued invoices keep the payment notes they were issued with (#6)."""

from datetime import date
from pathlib import Path

import pytest
from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceLineCreate, InvoiceStatus
from pydantic_invoices.schemas.company import CompanyCreate
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.operations.invoices import clone_invoice, render_invoice_html

BACKENDS = ["memory", "files-md", "files-yaml", "sqlite"]


def _factory(backend: str, tmp_path: Path) -> RepositoryFactory:
    if backend.startswith("files"):
        fmt = backend.removeprefix("files-")
        return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format=fmt)
    if backend == "sqlite":
        return RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    return RepositoryFactory("memory")


def _legacy_invoice(factory: RepositoryFactory, note_id: int) -> None:
    """An invoice stored before snapshots existed: payment note IDs only."""
    factory.create_company_repository().create(
        CompanyCreate(name="Seller GmbH", address="Hauptstr. 1, Berlin")
    )
    client = factory.create_client_repository().create(ClientCreate(name="Buyer"))
    factory.create_invoice_repository().create(
        InvoiceCreate(
            number="INV-PN-1",
            issue_date=date(2026, 1, 5),
            status=InvoiceStatus.UNPAID,
            client_id=client.id,
            payment_note_ids=[note_id],
            lines=[
                InvoiceLineCreate(description="Work", quantity=1, unit_price=Money("100", "EUR"))
            ],
        )
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_editing_a_payment_note_does_not_change_issued_invoices(
    backend: str, tmp_path: Path
) -> None:
    factory = _factory(backend, tmp_path)
    notes = factory.create_payment_note_repository()
    note = notes.create(PaymentNoteCreate(title="Bank", content="IBAN DE-OLD"))
    _legacy_invoice(factory, note.id)

    cloned = clone_invoice(factory, "INV-PN-1", date(2026, 2, 5)).invoice
    notes.update(note.model_copy(update={"content": "IBAN DE-NEW"}))

    stored = factory.create_invoice_repository().get_by_id(cloned.id)
    assert stored is not None
    assert stored.payment_note_ids == [note.id]
    html = render_invoice_html(factory, stored)
    assert "IBAN DE-OLD" in html
    assert "IBAN DE-NEW" not in html


def test_legacy_invoice_without_snapshot_renders_current_notes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    factory = _factory("files-md", tmp_path)
    notes = factory.create_payment_note_repository()
    note = notes.create(PaymentNoteCreate(title="Bank", content="IBAN DE-OLD"))
    _legacy_invoice(factory, note.id)
    notes.update(note.model_copy(update={"content": "IBAN DE-NEW"}))

    legacy = factory.create_invoice_repository().get_by_number("INV-PN-1")
    assert legacy is not None
    assert legacy.payment_notes_snapshot is None
    assert "IBAN DE-NEW" in render_invoice_html(factory, legacy)
    assert "no payment notes snapshot" in caplog.text
