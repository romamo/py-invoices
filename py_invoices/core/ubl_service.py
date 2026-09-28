"""UBL generation service.

Renders UBL 2.1 XML (Invoice, or CreditNote for credit notes) using Jinja2.
"""

from typing import Any

from pydantic_invoices.schemas import Invoice, InvoiceType

from py_invoices.core.html_service import HTMLService

UBL_INVOICE_TEMPLATE = "ubl_invoice.xml.j2"
UBL_CREDIT_NOTE_TEMPLATE = "ubl_credit_note.xml.j2"


class UBLService(HTMLService):
    """Service for generating UBL XML documents. Reuses the Jinja2 setup of HTMLService."""

    def __init__(
        self,
        template_dir: str | None = None,
        output_dir: str = "output",
        default_template: str = UBL_INVOICE_TEMPLATE,
    ):
        super().__init__(template_dir, output_dir, default_template)

    def _template_for(self, invoice: Invoice, template_name: str | None) -> str:
        if template_name:
            return template_name
        if invoice.type is InvoiceType.CREDIT_NOTE:
            return UBL_CREDIT_NOTE_TEMPLATE
        return self.default_template

    def generate_ubl(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Render UBL XML; credit notes default to the UBL CreditNote document."""
        return self.generate_html(
            invoice=invoice,
            company=company,
            template_name=self._template_for(invoice, template_name),
            **context,
        )

    def generate_ubl_bytes(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        **context: Any,
    ) -> bytes:
        """Generate UBL XML as UTF-8 bytes."""
        return self.generate_ubl(invoice, company, template_name, **context).encode("utf-8")

    def save_ubl(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Save UBL XML and return its path (defaults to "<number>.xml")."""
        xml_content = self.generate_ubl(invoice, company, template_name, **context)
        return self._write(output_filename or f"{invoice.number}.xml", xml_content)
