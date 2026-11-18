"""Payment note operations."""

from pydantic_invoices.schemas.payment_note import PaymentNote, PaymentNoteCreate

from py_invoices.core.paging import iter_all
from py_invoices.plugins.factory import RepositoryFactory


def list_payment_notes(factory: RepositoryFactory, company_id: int | None) -> list[PaymentNote]:
    """Active payment notes, or those of one company."""
    repo = factory.create_payment_note_repository()
    return repo.get_by_company(company_id) if company_id else repo.get_active()


def default_payment_note(factory: RepositoryFactory, company_id: int | None) -> PaymentNote | None:
    return factory.create_payment_note_repository().get_default(company_id)


def create_payment_note(factory: RepositoryFactory, data: PaymentNoteCreate) -> PaymentNote:
    """Create a payment note; a new default replaces the previous default of its company.

    The scope is the note's `company_id`: a company's default and the global default
    (`company_id` None) are separate.
    """
    repo = factory.create_payment_note_repository()
    created = repo.create(data)
    if created.is_default:
        for note in list(iter_all(repo)):
            if note.id != created.id and note.is_default and note.company_id == created.company_id:
                repo.update(note.model_copy(update={"is_default": False}))
    return created
