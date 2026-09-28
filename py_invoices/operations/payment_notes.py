"""Payment note operations."""

from pydantic_invoices.schemas.payment_note import PaymentNote, PaymentNoteCreate

from py_invoices.plugins.factory import RepositoryFactory


def list_payment_notes(factory: RepositoryFactory, company_id: int | None) -> list[PaymentNote]:
    """Active payment notes, or those of one company."""
    repo = factory.create_payment_note_repository()
    return repo.get_by_company(company_id) if company_id else repo.get_active()


def default_payment_note(factory: RepositoryFactory, company_id: int | None) -> PaymentNote | None:
    return factory.create_payment_note_repository().get_default(company_id)


def create_payment_note(factory: RepositoryFactory, data: PaymentNoteCreate) -> PaymentNote:
    return factory.create_payment_note_repository().create(data)
