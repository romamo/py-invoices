"""Credit note operations."""

from dataclasses import dataclass

from pydantic_invoices.schemas import Invoice, InvoiceLineCreate

from py_invoices.core.audit_service import AuditService
from py_invoices.core.credit_service import CreditService
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


def credit_invoice(
    factory: RepositoryFactory,
    original: Invoice,
    reason: str | None,
    lines: list[InvoiceLineCreate] | None = None,
    line_indices: list[int] | None = None,
) -> Invoice:
    """Issue a credit note (whole invoice, chosen lines, or explicit lines) and audit it."""
    invoice_repo = factory.create_invoice_repository()
    try:
        credit_note = CreditService(invoice_repo).create_credit_note(
            original_invoice=original,
            reason=reason,
            lines=lines,
            refund_lines_indices=line_indices,
        )
    except ValueError as e:
        raise CreditNoteRejectedError(str(e)) from e
    AuditService(audit_repo=factory.create_audit_repository()).log_credit_note_created(
        credit_note, original
    )
    return credit_note


def create_credit_note(
    factory: RepositoryFactory,
    invoice_number: str,
    reason: str,
    line_indices: list[int] | None = None,
) -> CreatedCreditNote:
    """Credit an invoice, in full or only the lines at `line_indices`."""
    original = factory.create_invoice_repository().get_by_number(invoice_number)
    if original is None:
        raise InvoiceNotFoundError(invoice_number)
    credit_note = credit_invoice(factory, original, reason, line_indices=line_indices)
    return CreatedCreditNote(original=original, credit_note=credit_note)


def find_credit_note(factory: RepositoryFactory, number: str) -> Invoice:
    """Find a document by number; it may be a regular invoice, which callers can check."""
    document = factory.create_invoice_repository().get_by_number(number)
    if document is None:
        raise CreditNoteNotFoundError(number)
    return document
