"""Issue lifecycle: what an issued invoice locks, its content hash, and the update guard.

An invoice is a DRAFT until it is issued. Issuing locks its content (EU VAT Directive
2006/112/EC, art. 233): every backend's repository refuses to change the locked fields
of an issued invoice or to delete it, and a correction goes through a credit note.
"""

import hashlib
import json
from decimal import Decimal
from typing import Any

from pydantic_invoices.schemas import Invoice, InvoiceStatus

from py_invoices.core.validator import BusinessValidator

DRAFT_NUMBER_PREFIX = "DRAFT-"

LOCKED_FIELDS = (
    "number",
    "issue_date",
    "due_date",
    "type",
    "payment_terms",
    "original_invoice_id",
    "reason",
    "company_id",
    "client_id",
    "client_name_snapshot",
    "client_address_snapshot",
    "client_tax_id_snapshot",
    "client_city_snapshot",
    "client_postal_code_snapshot",
    "client_country_snapshot",
    "company_name_snapshot",
    "company_address_snapshot",
    "company_tax_id_snapshot",
    "payment_note_ids",
    "payment_notes_snapshot",
    "template_name",
)
"""Fields fixed at issue. Status, payments and the hash itself change by their own rules."""


class InvoiceLockedError(ValueError):
    """An issued invoice's content cannot change; a correction is a credit note."""

    def __init__(self, number: str, fields: list[str]) -> None:
        super().__init__(
            f"Invoice {number} is issued; {', '.join(fields)} cannot change. "
            "Issue a credit note to correct it."
        )
        self.number = number
        self.fields = fields


def is_draft(invoice: Invoice) -> bool:
    return invoice.status is InvoiceStatus.DRAFT


def draft_number(invoice_id: int) -> str:
    """The provisional number of a draft; the final one is assigned at issue."""
    return f"{DRAFT_NUMBER_PREFIX}{invoice_id}"


def _number_text(value: Decimal | float) -> str:
    """A number without trailing zeros, so 900, 900.00 (SQL Numeric) and 900.0 hash alike."""
    text = format(Decimal(str(value)).normalize(), "f")
    return "0" if text == "-0" else text


def locked_content(invoice: Invoice) -> dict[str, Any]:
    """The locked fields and lines as JSON values, in a stable shape across backends."""
    data = invoice.model_dump(mode="json", include=set(LOCKED_FIELDS))
    data["lines"] = [
        {
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": _number_text(line.unit_price.amount),
            "currency": line.unit_price.currency,
            # SQL stores a missing tax rate as 0
            "tax_rate": _number_text(line.tax_rate or 0),
        }
        for line in invoice.lines
    ]
    return data


def content_hash(invoice: Invoice) -> str:
    """SHA-256 over the canonical JSON of the locked content."""
    canonical = json.dumps(locked_content(invoice), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def changed_locked_fields(stored: Invoice, updated: Invoice) -> list[str]:
    before, after = locked_content(stored), locked_content(updated)
    return sorted(key for key in before if before[key] != after[key])


def guard_update(stored: Invoice, updated: Invoice) -> None:
    """Refuse an update that changes an issued invoice's content or breaks the state machine.

    A draft may change freely. Once issued, only the status (by a valid transition)
    may change, and a hash may be added once (sealing an invoice issued before hashing)
    if it matches the content.

    Raises:
        InvoiceLockedError: If a locked field, the lines or the hash would change
        ValueError: If the status transition is not allowed
    """
    if is_draft(stored):
        return
    changed = changed_locked_fields(stored, updated)
    if updated.content_hash != stored.content_hash and not (
        stored.content_hash is None and updated.content_hash == content_hash(updated)
    ):
        changed.append("content_hash")
    if changed:
        raise InvoiceLockedError(stored.number, changed)
    BusinessValidator.validate_state_transition(stored.status, updated.status)


def guard_delete(stored: Invoice) -> None:
    """Only drafts can be deleted.

    Raises:
        InvoiceLockedError: If the invoice is issued
    """
    if not is_draft(stored):
        raise InvoiceLockedError(stored.number, ["the invoice itself (delete)"])
