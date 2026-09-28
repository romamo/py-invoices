"""Credit note operations."""

from dataclasses import dataclass

from pydantic_invoices.schemas import Invoice

from py_invoices.core.credit_service import CreditService
from py_invoices.core.numbering_service import NumberingService
from py_invoices.operations.errors import (
    CreditNoteNotFoundError,
    CreditNoteRejectedError,
    InvoiceNotFoundError,
)
from py_invoices.plugins.factory import RepositoryFactory


@dataclass(frozen=True, slots=True)
class CreatedCreditNote:
    original: Invoice
    credit_note: Invoice


def create_credit_note(
    factory: RepositoryFactory, invoice_number: str, reason: str
) -> CreatedCreditNote:
    """Credit an invoice in full."""
    invoice_repo = factory.create_invoice_repository()
    credit_service = CreditService(invoice_repo, NumberingService(invoice_repo=invoice_repo))

    original = invoice_repo.get_by_number(invoice_number)
    if original is None:
        raise InvoiceNotFoundError(invoice_number)
    try:
        credit_note = credit_service.create_credit_note(original_invoice=original, reason=reason)
    except ValueError as e:
        raise CreditNoteRejectedError(str(e)) from e
    return CreatedCreditNote(original=original, credit_note=credit_note)


def find_credit_note(factory: RepositoryFactory, number: str) -> Invoice:
    """Find a document by number; it may be a regular invoice, which callers can check."""
    document = factory.create_invoice_repository().get_by_number(number)
    if document is None:
        raise CreditNoteNotFoundError(number)
    return document
