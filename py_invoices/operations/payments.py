"""Payment operations."""

from dataclasses import dataclass

from pydantic_invoices.schemas import Invoice, Payment
from pydantic_invoices.vo import Money

from py_invoices.operations.errors import InvoiceNotFoundError
from py_invoices.plugins.factory import RepositoryFactory


@dataclass(frozen=True, slots=True)
class InvoicePayments:
    invoice: Invoice
    payments: list[Payment]
    total_paid: Money
    balance_due: Money


def invoice_payments(factory: RepositoryFactory, invoice_number: str) -> InvoicePayments:
    """Payments recorded against an invoice, with the total paid and the balance due."""
    invoice = factory.create_invoice_repository().get_by_number(invoice_number)
    if invoice is None:
        raise InvoiceNotFoundError(invoice_number)
    payments = factory.create_payment_repository().get_by_invoice(invoice.id)
    total_paid = sum((p.amount for p in payments), start=Money(0))
    return InvoicePayments(
        invoice=invoice,
        payments=payments,
        total_paid=total_paid,
        balance_due=max(Money(0), invoice.total_amount - total_paid),
    )
