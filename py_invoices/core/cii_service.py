"""CII generation service.

Renders UN/CEFACT Cross Industry Invoice (CII D16B) XML for the Factur-X EN 16931
profile, the XML that a Factur-X PDF embeds as factur-x.xml.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic_invoices.schemas import Invoice, InvoiceType
from pydantic_invoices.vo import CountryCode

from py_invoices.core.html_service import HTMLService

CII_TEMPLATE = "cii_invoice.xml.j2"
EN16931_GUIDELINE = "urn:cen.eu:en16931:2017"

# UNTDID 1001 document type codes
INVOICE_TYPE_CODE = "380"
CREDIT_NOTE_TYPE_CODE = "381"

# VAT identifiers start with an ISO 3166-1 alpha-2 code, or EL for Greece (BR-CO-9)
_GREECE_VAT_PREFIX = "EL"
_VAT_ID_RE = re.compile(r"[A-Z]{2}[0-9A-Z+*.]{2,13}")


class FacturXDataError(ValueError):
    """The invoice lacks data that an EN 16931 invoice must contain."""

    def __init__(self, invoice_number: str, problems: list[str]) -> None:
        super().__init__(
            f"Invoice {invoice_number} cannot be issued as an EN 16931 e-invoice: "
            + "; ".join(problems)
        )
        self.problems = problems


@dataclass(frozen=True, slots=True)
class CIIParty:
    country: CountryCode
    # A VAT identifier (scheme VA) or, for sellers, a local tax number (scheme FC)
    registration_id: str | None = None
    registration_scheme: str | None = None
    # Legal registration number (seller BT-30); buyer tax numbers that are not VAT
    # identifiers go here too (BT-47)
    legal_id: str | None = None


@dataclass(frozen=True, slots=True)
class CIIContext:
    type_code: str
    seller: CIIParty
    buyer: CIIParty
    delivery_date: date
    guideline: str = EN16931_GUIDELINE

    @staticmethod
    def category(rate: Decimal | float | None) -> str:
        """VAT category: standard rate (S) or zero rated (Z)."""
        return "S" if rate else "Z"

    @staticmethod
    def rate(rate: Decimal | float | None) -> str:
        value = Decimal(str(rate or 0)).normalize()
        return format(value, "f")


def is_vat_identifier(tax_id: str) -> bool:
    """A VAT number: country prefix (EL for Greece) and 2-13 characters (BR-CO-9)."""
    if not _VAT_ID_RE.fullmatch(tax_id):
        return False
    prefix = tax_id[:2]
    if prefix == _GREECE_VAT_PREFIX:
        return True
    try:
        CountryCode(prefix)
    except ValueError:
        return False
    return True


def _country(value: Any, field: str, problems: list[str]) -> CountryCode | None:
    if not value:
        problems.append(f"{field} is missing")
        return None
    try:
        return CountryCode(str(value))
    except ValueError:
        problems.append(f"{field} '{value}' is not an ISO 3166-1 alpha-2 code")
        return None


def cii_context(
    invoice: Invoice, company: dict[str, Any], delivery_date: date | None = None
) -> CIIContext:
    """The EN 16931 data for `invoice`; raises FacturXDataError listing everything missing."""
    problems = []
    if not invoice.lines:
        problems.append("the invoice has no lines")
    if not company.get("name"):
        problems.append("seller name (company['name']) is missing")
    # country_code as built by the CLI; country as in a dumped Company schema
    seller_country = _country(
        company.get("country_code") or company.get("country"), "seller country code", problems
    )
    seller_tax_id = str(company.get("tax_id") or "")
    seller_registration = company.get("registration_number") or None
    if seller_tax_id and not is_vat_identifier(seller_tax_id) and not seller_registration:
        # BR-CO-26: a local tax number alone does not identify the seller
        problems.append(
            "seller needs a VAT identifier (company['tax_id']) or a legal registration "
            "number (company['registration_number'])"
        )
    if not seller_tax_id:
        # BR-S-02 / BR-Z-02: standard and zero rated invoices need a seller tax identifier
        problems.append("seller VAT or tax number (company['tax_id']) is missing")
    if not invoice.client_name_snapshot:
        problems.append("buyer name is missing")
    buyer_country = _country(invoice.client_country_snapshot, "buyer country code", problems)
    if problems or seller_country is None or buyer_country is None:
        raise FacturXDataError(invoice.number, problems)

    buyer_tax_id = invoice.client_tax_id_snapshot
    buyer_vat = buyer_tax_id if buyer_tax_id and is_vat_identifier(buyer_tax_id) else None
    return CIIContext(
        type_code=(
            CREDIT_NOTE_TYPE_CODE if invoice.type is InvoiceType.CREDIT_NOTE else INVOICE_TYPE_CODE
        ),
        seller=CIIParty(
            country=seller_country,
            registration_id=seller_tax_id,
            registration_scheme="VA" if is_vat_identifier(seller_tax_id) else "FC",
            legal_id=seller_registration,
        ),
        buyer=CIIParty(
            country=buyer_country,
            registration_id=buyer_vat,
            registration_scheme="VA" if buyer_vat else None,
            legal_id=buyer_tax_id if buyer_tax_id and not buyer_vat else None,
        ),
        delivery_date=delivery_date or invoice.issue_date,
    )


class CIIService(HTMLService):
    """Service for generating CII XML. Reuses the Jinja2 setup of HTMLService."""

    def __init__(
        self,
        template_dir: str | None = None,
        output_dir: str = "output",
        default_template: str = CII_TEMPLATE,
    ):
        super().__init__(template_dir, output_dir, default_template)

    def generate_cii(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        delivery_date: date | None = None,
        **context: Any,
    ) -> str:
        """Render EN 16931 CII XML for an invoice or credit note.

        `company` needs name, country_code or country (ISO 3166-1 alpha-2) and tax_id, plus
        registration_number when tax_id is not a VAT number; the invoice
        needs a buyer name and client_country_snapshot. The delivery date defaults to
        the issue date. Pass original_invoice_number to reference the credited invoice.

        Raises:
            FacturXDataError: If data an EN 16931 invoice requires is missing.
        """
        cii = cii_context(invoice, company, delivery_date)
        return self.generate_html(
            invoice=invoice, company=company, template_name=template_name, cii=cii, **context
        )
