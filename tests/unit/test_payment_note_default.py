"""A new default payment note replaces the previous default of its company (#7)."""

from pathlib import Path

import pytest
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate

from py_invoices import RepositoryFactory
from py_invoices.core.paging import iter_all
from py_invoices.operations.payment_notes import create_payment_note

BACKENDS = ["memory", "files", "sqlite"]


def _factory(backend: str, tmp_path: Path) -> RepositoryFactory:
    if backend == "files":
        return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="md")
    if backend == "sqlite":
        return RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    return RepositoryFactory("memory")


def _defaults(factory: RepositoryFactory) -> list[tuple[str, int | None]]:
    notes = iter_all(factory.create_payment_note_repository())
    return sorted((n.content, n.company_id) for n in notes if n.is_default)


@pytest.mark.parametrize("backend", BACKENDS)
def test_new_default_clears_previous_default_in_same_company(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    create_payment_note(factory, PaymentNoteCreate(title="Bank", content="OLD", is_default=True))
    other = PaymentNoteCreate(title="Bank", content="OTHER", company_id=2, is_default=True)
    create_payment_note(factory, other)
    create_payment_note(factory, PaymentNoteCreate(title="Bank", content="NEW", is_default=True))

    assert _defaults(factory) == [("NEW", None), ("OTHER", 2)]


@pytest.mark.parametrize("backend", BACKENDS)
def test_non_default_note_keeps_existing_default(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    create_payment_note(factory, PaymentNoteCreate(title="Bank", content="OLD", is_default=True))
    create_payment_note(factory, PaymentNoteCreate(title="Bank", content="EXTRA"))

    assert _defaults(factory) == [("OLD", None)]
