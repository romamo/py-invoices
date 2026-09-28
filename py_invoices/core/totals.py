"""Invoice totals and money display shared by every renderer."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from pydantic_invoices.schemas import Invoice, InvoiceLine
from pydantic_invoices.vo import Money

DEFAULT_CURRENCY = "USD"
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}
CENT = Decimal("0.01")


def cents(value: Money) -> Decimal:
    """Amount rounded half-up to the cent, as UBL and other exact outputs need."""
    return value.amount.quantize(CENT, rounding=ROUND_HALF_UP)


def format_money(value: Money) -> str:
    """Format as "$1234.50" for known symbols, otherwise "1234.50 CHF"."""
    amount = abs(cents(value))
    sign = "-" if value.amount < 0 else ""
    symbol = CURRENCY_SYMBOLS.get(value.currency)
    if symbol:
        return f"{sign}{symbol}{amount}"
    return f"{sign}{amount} {value.currency}"


def as_money(value: Money.Input, currency: str = DEFAULT_CURRENCY) -> Money:
    """A Money from a schema input value; plain numbers take the given currency."""
    return value if isinstance(value, Money) else Money(value, currency)


def invoice_currency(invoice: Invoice) -> str:
    return invoice.lines[0].unit_price.currency if invoice.lines else DEFAULT_CURRENCY


@dataclass(frozen=True, slots=True)
class TaxSubtotal:
    rate: Decimal
    taxable: Money
    tax: Money


@dataclass(frozen=True, slots=True)
class InvoiceTotals:
    currency: str
    net: Money
    tax: Money
    gross: Money
    tax_subtotals: tuple[TaxSubtotal, ...]


def line_net(line: InvoiceLine) -> Money:
    """A line's amount rounded to the cent, as shown on documents."""
    return Money(cents(line.total), line.total.currency)


def invoice_totals(invoice: Invoice) -> InvoiceTotals:
    """Net, tax and gross amounts.

    Line amounts are rounded first and summed (EN16931 BR-CO-10); tax is rounded per rate.
    """
    currency = invoice_currency(invoice)
    by_rate: dict[Decimal, Money] = {}
    for line in invoice.lines:
        rate = Decimal(str(line.tax_rate or 0))
        by_rate[rate] = by_rate.get(rate, Money(0, currency)) + line_net(line)

    subtotals = tuple(
        TaxSubtotal(
            rate=rate,
            taxable=taxable,
            tax=Money(
                (taxable.amount * rate / 100).quantize(CENT, rounding=ROUND_HALF_UP), currency
            ),
        )
        for rate, taxable in sorted(by_rate.items())
    )
    net = sum((s.taxable for s in subtotals), start=Money(0, currency))
    tax = sum((s.tax for s in subtotals), start=Money(0, currency))
    return InvoiceTotals(
        currency=currency, net=net, tax=tax, gross=net + tax, tax_subtotals=subtotals
    )


def invoice_gross(invoice: Invoice) -> Money:
    """Tax-inclusive total: the amount the customer is billed and owes."""
    return invoice_totals(invoice).gross
