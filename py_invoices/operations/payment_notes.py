"""Payment note operations.

A note's text is never edited: issued invoices print it, so new bank details are a new
note, made the default, with the old one deactivated. Every change is audited.
"""

from pydantic_invoices.interfaces import PaymentNoteRepository
from pydantic_invoices.schemas.payment_note import PaymentNote, PaymentNoteCreate

from py_invoices.core.audit_service import AuditEntity, AuditService
from py_invoices.core.paging import iter_all
from py_invoices.operations.errors import PaymentNoteMissingError, PaymentNoteStateError
from py_invoices.plugins.factory import RepositoryFactory


def list_payment_notes(factory: RepositoryFactory, company_id: int | None) -> list[PaymentNote]:
    """Active payment notes, or those of one company."""
    repo = factory.create_payment_note_repository()
    return repo.get_by_company(company_id) if company_id else repo.get_active()


def default_payment_note(factory: RepositoryFactory, company_id: int | None) -> PaymentNote | None:
    return factory.create_payment_note_repository().get_default(company_id)


def _audit(factory: RepositoryFactory) -> AuditService:
    return AuditService(audit_repo=factory.create_audit_repository())


def _clear_other_defaults(repo: PaymentNoteRepository, note: PaymentNote) -> list[int]:
    """Unset the default on the other notes of the note's company; return their IDs."""
    cleared = []
    for other in list(iter_all(repo)):
        if other.id != note.id and other.is_default and other.company_id == note.company_id:
            repo.update(other.model_copy(update={"is_default": False}))
            cleared.append(other.id)
    return cleared


def _default_value(cleared: list[int]) -> str | None:
    return f"default was {', '.join(map(str, cleared))}" if cleared else None


def create_payment_note(factory: RepositoryFactory, data: PaymentNoteCreate) -> PaymentNote:
    """Create a payment note; a new default replaces the previous default of its company.

    The scope is the note's `company_id`: a company's default and the global default
    (`company_id` None) are separate.
    """
    repo = factory.create_payment_note_repository()
    created = repo.create(data)
    cleared = _clear_other_defaults(repo, created) if created.is_default else []
    _audit(factory).log_record_event(
        AuditEntity.PAYMENT_NOTE,
        created.id,
        "CREATED",
        new_value=f"{created.title}: {created.content}"
        + (" (default)" if created.is_default else ""),
        old_value=_default_value(cleared),
    )
    return created


def _find(repo: PaymentNoteRepository, note_id: int) -> PaymentNote:
    note = repo.get_by_id(note_id)
    if note is None:
        raise PaymentNoteMissingError(note_id)
    return note


def set_default_payment_note(factory: RepositoryFactory, note_id: int) -> PaymentNote:
    """Make an active note the default of its company, replacing the previous default.

    Raises:
        PaymentNoteMissingError: If there is no such note
        PaymentNoteStateError: If the note is inactive
    """
    repo = factory.create_payment_note_repository()
    note = _find(repo, note_id)
    if not note.is_active:
        raise PaymentNoteStateError(f"Payment note {note_id} is inactive; it cannot be the default")
    if note.is_default:
        return note
    updated = repo.update(note.model_copy(update={"is_default": True}))
    cleared = _clear_other_defaults(repo, updated)
    _audit(factory).log_record_event(
        AuditEntity.PAYMENT_NOTE,
        note_id,
        "SET_DEFAULT",
        new_value=f"default for company {note.company_id or 'all'}",
        old_value=_default_value(cleared),
    )
    return updated


def deactivate_payment_note(factory: RepositoryFactory, note_id: int) -> PaymentNote:
    """Retire a note so it is no longer offered; issued invoices keep their snapshot.

    Raises:
        PaymentNoteMissingError: If there is no such note
        PaymentNoteStateError: If the note is the default (make another note the default first)
    """
    repo = factory.create_payment_note_repository()
    note = _find(repo, note_id)
    if note.is_default:
        raise PaymentNoteStateError(
            f"Payment note {note_id} is the default; make another note the default first"
        )
    if not note.is_active:
        return note
    updated = repo.update(note.model_copy(update={"is_active": False}))
    _audit(factory).log_record_event(
        AuditEntity.PAYMENT_NOTE, note_id, "DEACTIVATED", old_value="active", new_value="inactive"
    )
    return updated
