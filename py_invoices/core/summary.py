"""Invoice statistics computed the same way for every storage backend."""

from collections.abc import Iterable
from decimal import Decimal

from pydantic_invoices.schemas import Invoice, InvoiceStatus, InvoiceSummary, InvoiceType
from pydantic_invoices.vo import Money

from py_invoices.core.totals import DEFAULT_CURRENCY, invoice_gross

OPEN_STATUSES = (InvoiceStatus.SENT, InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID)
NOT_ISSUED = (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED)


class MixedCurrencyError(ValueError):
    """Documents in several currencies cannot be summed into one amount."""

    def __init__(self, currencies: set[str]) -> None:
        super().__init__(
            f"Cannot summarize invoices in several currencies: {', '.join(sorted(currencies))}"
        )
        self.currencies = currencies


def summary_currency(documents: list[Invoice]) -> str:
    """The single currency of the documents' lines (documents without lines have none)."""
    currencies = {line.unit_price.currency for doc in documents for line in doc.lines}
    if len(currencies) > 1:
        raise MixedCurrencyError(currencies)
    return currencies.pop() if currencies else DEFAULT_CURRENCY


def summarize_invoices(documents: Iterable[Invoice]) -> InvoiceSummary:
    """Summarize invoices and credit notes, using tax-inclusive (gross) amounts.

    - counts cover standard invoices only
    - total_amount is issued invoices minus credit notes (drafts and cancelled excluded)
    - total_paid is payments received on standard invoices
    - total_due is what open invoices still owe after payments and credit notes

    Raises:
        MixedCurrencyError: If the documents use more than one currency
    """
    all_docs = list(documents)
    currency = summary_currency(all_docs)

    def gross(doc: Invoice) -> Money:
        return Money(invoice_gross(doc).amount, currency)

    def paid(doc: Invoice) -> Money:
        # Payments are recorded against one invoice, so they share its currency
        return Money(sum((p.amount.amount for p in doc.payments), start=Decimal(0)), currency)

    invoices = [d for d in all_docs if d.type is InvoiceType.STANDARD]
    credit_notes = [
        d
        for d in all_docs
        if d.type is InvoiceType.CREDIT_NOTE and d.status is not InvoiceStatus.CANCELLED
    ]
    zero = Money(0, currency)

    credited: dict[int, Money] = {}
    for note in credit_notes:
        if note.original_invoice_id is not None:
            credited[note.original_invoice_id] = credited.get(
                note.original_invoice_id, zero
            ) + gross(note)

    issued = [i for i in invoices if i.status not in NOT_ISSUED]
    total_amount = sum((gross(i) for i in issued), start=zero) - sum(
        (gross(n) for n in credit_notes), start=zero
    )
    total_paid = sum((paid(i) for i in invoices), start=zero)
    total_due = zero
    for invoice in invoices:
        if invoice.status in OPEN_STATUSES:
            owed = gross(invoice) - paid(invoice) - credited.get(invoice.id, zero)
            total_due += max(owed, zero)

    return InvoiceSummary(
        total_count=len(invoices),
        paid_count=sum(1 for i in invoices if i.status is InvoiceStatus.PAID),
        unpaid_count=sum(1 for i in invoices if i.status in OPEN_STATUSES),
        overdue_count=sum(1 for i in invoices if i.is_overdue),
        total_amount=total_amount,
        total_paid=total_paid,
        total_due=total_due,
    )
