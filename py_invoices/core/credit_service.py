"""Credit Note Service.

Provides functionality for creating and managing credit notes.
"""

from collections import Counter
from datetime import date

from pydantic_invoices.interfaces import InvoiceRepository
from pydantic_invoices.schemas import (
    Invoice,
    InvoiceCreate,
    InvoiceLine,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceType,
)
from pydantic_invoices.vo import Money

from py_invoices.core.numbering_service import CREDIT_NOTE_NUMBER_FORMAT, NumberingService
from py_invoices.core.paging import iter_all
from py_invoices.core.totals import as_money, invoice_currency, invoice_gross
from py_invoices.core.validator import BusinessValidator

NOT_CREDITABLE = (
    InvoiceStatus.DRAFT,
    InvoiceStatus.CANCELLED,
    InvoiceStatus.CREDITED,
    InvoiceStatus.REFUNDED,
)
REFUND_PREFIX = "Refund: "


def _gross(lines: list[InvoiceLineCreate], currency: str) -> Money:
    """Tax-inclusive total of credit lines, computed like a stored document's total."""
    draft = Invoice(
        id=0,
        number="draft",
        client_id=0,
        lines=[
            InvoiceLine(
                id=i,
                invoice_id=0,
                description=line.description,
                quantity=line.quantity,
                unit_price=as_money(line.unit_price, currency),
                tax_rate=line.tax_rate,
            )
            for i, line in enumerate(lines, start=1)
        ],
    )
    return invoice_gross(draft)


def _line_key(description: str, unit_price: Money, quantity: int) -> tuple[str, str, int]:
    return description.removeprefix(REFUND_PREFIX), str(unit_price.amount), quantity


class CreditService:
    """Service for handling Credit Notes."""

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        numbering_service: NumberingService | None = None,
    ):
        """Initialize Credit Service.

        Args:
            invoice_repo: Repository for invoices
            numbering_service: Numbering for credit notes; defaults to the "CN-" series
        """
        self.invoice_repo = invoice_repo
        self.numbering_service = numbering_service or NumberingService(
            CREDIT_NOTE_NUMBER_FORMAT, invoice_repo=invoice_repo
        )

    def _notes_for(self, original_invoice: Invoice) -> list[Invoice]:
        return [
            note
            for note in iter_all(self.invoice_repo)
            if note.type is InvoiceType.CREDIT_NOTE
            and note.original_invoice_id == original_invoice.id
            and note.status is not InvoiceStatus.CANCELLED
        ]

    def credited_amount(self, original_invoice: Invoice) -> Money:
        """Tax-inclusive total of the credit notes already issued against an invoice."""
        currency = invoice_currency(original_invoice)
        return sum(
            (invoice_gross(note) for note in self._notes_for(original_invoice)),
            start=Money(0, currency),
        )

    def create_credit_note(
        self,
        original_invoice: Invoice,
        reason: str | None = None,
        lines: list[InvoiceLineCreate] | None = None,
        refund_lines_indices: list[int] | None = None,
    ) -> Invoice:
        """Create a Credit Note for a given invoice.

        Amounts stay positive; the CREDIT_NOTE type marks them as a reduction.
        When the invoice becomes fully credited it is moved to CREDITED.

        Args:
            original_invoice: The source invoice to credit.
            reason: Reason for the credit note.
            lines: Explicit lines for a partial credit.
            refund_lines_indices: Indices of original lines to credit, used if `lines` is None.
                With neither, the whole invoice is credited.

        Raises:
            ValueError: If the invoice cannot be credited or the credit exceeds what is left.
        """
        if original_invoice.type is InvoiceType.CREDIT_NOTE:
            raise ValueError("Cannot issue a credit note for another credit note.")
        if original_invoice.status in NOT_CREDITABLE:
            raise ValueError(
                f"Cannot issue a credit note for a {original_invoice.status.value} invoice."
            )

        cn_lines = self._credit_lines(original_invoice, lines, refund_lines_indices)
        if refund_lines_indices is not None and lines is None:
            self._reject_recredited_lines(original_invoice, refund_lines_indices)
        currency = invoice_currency(original_invoice)
        credit_total = _gross(cn_lines, currency)
        remaining = invoice_gross(original_invoice) - self.credited_amount(original_invoice)
        if credit_total > remaining:
            raise ValueError(
                f"Credit of {credit_total} exceeds the {remaining} left to credit on "
                f"invoice {original_invoice.number}."
            )
        fully_credited = credit_total == remaining
        if fully_credited:
            # Check before saving anything, so a refused transition leaves no credit note
            BusinessValidator.validate_state_transition(
                original_invoice.status, InvoiceStatus.CREDITED
            )

        today = date.today()
        credit_note = self.invoice_repo.create(
            InvoiceCreate(
                number=self.numbering_service.generate_number(),
                issue_date=today,
                status=InvoiceStatus.DRAFT,
                type=InvoiceType.CREDIT_NOTE,
                original_invoice_id=original_invoice.id,
                reason=reason,
                client_id=original_invoice.client_id,
                company_id=original_invoice.company_id,
                lines=cn_lines,
                due_date=today,
                payment_terms="Immediate",
                client_name_snapshot=original_invoice.client_name_snapshot,
                client_address_snapshot=original_invoice.client_address_snapshot,
                client_tax_id_snapshot=original_invoice.client_tax_id_snapshot,
                client_city_snapshot=original_invoice.client_city_snapshot,
                client_postal_code_snapshot=original_invoice.client_postal_code_snapshot,
                client_country_snapshot=original_invoice.client_country_snapshot,
                company_name_snapshot=original_invoice.company_name_snapshot,
                company_address_snapshot=original_invoice.company_address_snapshot,
                company_tax_id_snapshot=original_invoice.company_tax_id_snapshot,
                template_name=original_invoice.template_name,
            )
        )

        if fully_credited:
            self.invoice_repo.update(
                original_invoice.model_copy(update={"status": InvoiceStatus.CREDITED})
            )
        return credit_note

    def _reject_recredited_lines(self, original_invoice: Invoice, indices: list[int]) -> None:
        """Refuse to credit a line that an earlier credit note already covers."""
        already = Counter(
            _line_key(line.description, line.unit_price, line.quantity)
            for note in self._notes_for(original_invoice)
            for line in note.lines
        )
        on_invoice = Counter(
            _line_key(line.description, line.unit_price, line.quantity)
            for line in original_invoice.lines
        )
        for index in indices:
            line = original_invoice.lines[index]
            key = _line_key(line.description, line.unit_price, line.quantity)
            if already[key] >= on_invoice[key]:
                raise ValueError(
                    f"Line {index} of invoice {original_invoice.number} is already credited."
                )
            already[key] += 1

    @staticmethod
    def _credit_lines(
        original_invoice: Invoice,
        lines: list[InvoiceLineCreate] | None,
        refund_lines_indices: list[int] | None,
    ) -> list[InvoiceLineCreate]:
        if lines is not None:
            if not lines:
                raise ValueError("A credit note needs at least one line.")
            return lines

        def copy(index: int, prefix: str) -> InvoiceLineCreate:
            line = original_invoice.lines[index]
            return InvoiceLineCreate(
                description=f"{prefix}{line.description}",
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=line.tax_rate,
            )

        if refund_lines_indices is None:
            return [copy(i, "") for i in range(len(original_invoice.lines))]

        if not refund_lines_indices:
            raise ValueError("A credit note needs at least one line.")
        if len(set(refund_lines_indices)) != len(refund_lines_indices):
            raise ValueError(f"Duplicate line indices: {refund_lines_indices}")
        count = len(original_invoice.lines)
        invalid = [i for i in refund_lines_indices if not 0 <= i < count]
        if invalid:
            raise ValueError(
                f"Line indices {invalid} out of range; invoice {original_invoice.number} "
                f"has {count} lines (0-{count - 1})."
            )
        return [copy(i, REFUND_PREFIX) for i in refund_lines_indices]
