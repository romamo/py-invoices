"""PDF generation service.

Provides invoice PDF generation using Jinja2 templates and WeasyPrint.
"""

import os
from typing import Any, cast

from pydantic_invoices.schemas import Invoice

from py_invoices.core.html_service import HTMLService, output_path
from py_invoices.core.ubl_service import UBLService


class PDFService(HTMLService):
    """Service for generating PDF invoices from templates.

    Extends HTMLService with WeasyPrint rendering, including PDF/A-3 output that
    embeds the invoice's UBL XML.
    """

    @staticmethod
    def _get_weasyprint_modules() -> tuple[Any, Any]:
        """Import WeasyPrint's (HTML, Attachment) classes.

        Raises:
            ImportError: If WeasyPrint or its system libraries (pango) are missing
        """
        try:
            from weasyprint import HTML, Attachment  # type: ignore[import-untyped]
        except (ImportError, OSError) as e:
            raise ImportError(
                "WeasyPrint is required for PDF generation but was not found or "
                "is missing system dependencies (like pango).\n"
                "Install it with: pip install py-invoices[pdf]\n"
                "On macOS, you may also need: brew install pango libffi\n"
                "If libraries are installed but not found, try running:\n"
                "export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib\n"
                f"Original error: {e}"
            ) from e
        return HTML, Attachment

    def _write_bytes(self, filename: str, content: bytes) -> str:
        path = output_path(self.output_dir, filename)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def _render_pdf(self, html_content: str, **write_options: Any) -> bytes:
        html_cls, _ = self._get_weasyprint_modules()
        pdf_bytes = html_cls(
            string=html_content, base_url=os.path.abspath(self.template_dir)
        ).write_pdf(**write_options)
        if pdf_bytes is None:
            raise RuntimeError("WeasyPrint returned no PDF data")
        return cast(bytes, pdf_bytes)

    def generate_facturx_bytes(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        ubl_template_name: str | None = None,
        **context: Any,
    ) -> bytes:
        """Generate a PDF/A-3b document with its UBL XML embedded as an attachment.

        The XML template defaults to the one for the document type (Invoice or CreditNote).
        """
        _, attachment_cls = self._get_weasyprint_modules()
        ubl = UBLService(template_dir=self.template_dir, output_dir=self.output_dir)
        xml_content = ubl.generate_ubl(invoice, company, ubl_template_name, **context)
        html_content = self.generate_html(
            invoice=invoice, company=company, template_name=template_name, **context
        )
        attachment = attachment_cls(
            string=xml_content,
            filename="factur-x.xml",
            description="Factur-X Invoice Data",
        )
        return self._render_pdf(html_content, attachments=[attachment], pdf_variant="pdf/a-3b")

    def generate_facturx(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        ubl_template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Save a PDF/A-3b invoice with embedded XML; defaults to "<number>_facturx.pdf"."""
        pdf_bytes = self.generate_facturx_bytes(
            invoice=invoice,
            company=company,
            template_name=template_name,
            ubl_template_name=ubl_template_name,
            **context,
        )
        return self._write_bytes(output_filename or f"{invoice.number}_facturx.pdf", pdf_bytes)

    def generate_pdf_bytes(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        **context: Any,
    ) -> bytes:
        """Render the invoice to PDF bytes.

        Raises:
            ImportError: If WeasyPrint is not installed or system dependencies missing
        """
        html_content = self.generate_html(
            invoice=invoice, company=company, template_name=template_name, **context
        )
        return self._render_pdf(html_content)

    def generate_pdf(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Save the invoice as PDF and return its path (defaults to "<number>.pdf").

        Raises:
            ImportError: If WeasyPrint is not installed or system dependencies missing
        """
        pdf_bytes = self.generate_pdf_bytes(
            invoice=invoice, company=company, template_name=template_name, **context
        )
        return self._write_bytes(output_filename or f"{invoice.number}.pdf", pdf_bytes)
