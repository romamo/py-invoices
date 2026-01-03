"""PDF generation service.

Provides invoice PDF generation using Jinja2 templates and WeasyPrint.
"""

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

    from pydantic_invoices.schemas import Invoice

from py_invoices.core.html_service import HTMLService


class PDFService(HTMLService):
    """Service for generating PDF invoices from templates.

    This service extends HTMLService to add WeasyPrint PDF generation capabilities.
    Also supports Factur-X (ZUGFeRD) generation using UBLService.
    """

    def __init__(
        self,
        template_dir: str | None = None,
        output_dir: str = "output",
        default_template: str = "invoice.html.j2",
    ):
        """Initialize PDF service.

        Args:
            template_dir: Directory containing Jinja2 templates (optional)
            output_dir: Directory for generated PDF files
            default_template: Default template filename

        Raises:
            ImportError: If jinja2 is not installed
        """
        super().__init__(template_dir, output_dir, default_template)

    def generate_facturx(
        self,
        invoice: "Invoice",
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        ubl_template_name: str = "ubl_invoice.xml.j2",
        logo_path: str | None = None,
        **context: Any,
    ) -> str:
        """Generate Factur-X (PDF/A-3 + XML) invoice.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            output_filename: Custom output filename (defaults to invoice number)
            template_name: HTML Template to use
            ubl_template_name: UBL Template to use
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Path to generated PDF file
        """
        pdf_bytes = self.generate_facturx_bytes(
            invoice=invoice,
            company=company,
            template_name=template_name,
            ubl_template_name=ubl_template_name,
            logo_path=logo_path,
            **context
        )

        # Determine output path
        if not output_filename:
            output_filename = f"{invoice.number}_facturx.pdf"
        output_path = os.path.join(self.output_dir, output_filename)

        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        return output_path

    @staticmethod
    def _get_weasyprint_modules() -> tuple[Any, Any]:
        """Import weasyprint modules with unified error handling.

        Returns:
            Tuple containing (HTML, Attachment) classes from weasyprint.

        Raises:
            ImportError: If weasyprint is not installed or system dependencies are missing.
        """
        try:
            from weasyprint import HTML, Attachment  # type: ignore[import-untyped]

            return HTML, Attachment
        except (ImportError, OSError) as e:
            raise ImportError(
                "WeasyPrint is required for PDF generation but was not found or "
                "is missing system dependencies (like pango).\n"
                "Install it with: pip install py-invoices[pdf]\n"
                "On macOS, you may also need: brew install pango libffi\n"
                f"Original error: {e}"
            ) from e

    def generate_facturx_bytes(
        self,
        invoice: "Invoice",
        company: dict[str, Any],
        template_name: str | None = None,
        ubl_template_name: str = "ubl_invoice.xml.j2",
        logo_path: str | None = None,
        **context: Any,
    ) -> bytes:
        """Generate Factur-X (PDF/A-3 + XML) invoice as bytes.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            template_name: HTML Template to use
            ubl_template_name: UBL Template to use
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Raw PDF bytes
        """
        html_cls, attachment_cls = self._get_weasyprint_modules()

        # 1. Generate XML Content
        # Simpler: render using self.generate_html but with UBL template
        xml_content = self.generate_html(
            invoice=invoice, company=company, template_name=ubl_template_name, **context
        )

        # 2. Generate PDF with Attachment
        # Generate HTML
        html_content = self.generate_html(
            invoice=invoice,
            company=company,
            template_name=template_name,
            logo_path=logo_path,
            **context,
        )

        # Create Attachment
        attachment = attachment_cls(
            string=xml_content,
            filename="factur-x.xml",
            description="Factur-X Invoice Data",
        )

        # Generate PDF/A-3
        # render pdf bytes
        pdf_bytes = html_cls(
            string=html_content, base_url=os.path.abspath(self.template_dir)
        ).write_pdf(attachments=[attachment], pdf_variant="pdf/a-3b")

        if pdf_bytes is None:
             raise RuntimeError("Failed to generate PDF")

        from typing import cast
        return cast(bytes, pdf_bytes)


    def generate_pdf(
        self,
        invoice: "Invoice",
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        logo_path: str | None = None,
        **context: Any,
    ) -> str:
        """Generate PDF for an invoice and save to file.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            output_filename: Custom output filename (defaults to invoice number)
            template_name: Template to use (defaults to default_template)
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Path to generated PDF file

        Raises:
            ImportError: If WeasyPrint is not installed or system dependencies missing
        """
        # Generate PDF bytes
        pdf_bytes = self.generate_pdf_bytes(
            invoice=invoice,
            company=company,
            template_name=template_name,
            logo_path=logo_path,
            **context,
        )

        # Determine output path
        if not output_filename:
            output_filename = f"{invoice.number}.pdf"

        output_path = os.path.join(self.output_dir, output_filename)

        # Save PDF
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        return output_path

    def generate_pdf_bytes(
        self,
        invoice: "Invoice",
        company: dict[str, Any],
        template_name: str | None = None,
        logo_path: str | None = None,
        **context: Any,
    ) -> bytes:
        """Generate PDF for an invoice and return as bytes.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            template_name: Template to use (defaults to default_template)
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Raw PDF bytes

        Raises:
            ImportError: If WeasyPrint is not installed or system dependencies missing
        """
        html_cls, _ = self._get_weasyprint_modules()

        # Generate HTML
        html_content = self.generate_html(
            invoice=invoice,
            company=company,
            template_name=template_name,
            logo_path=logo_path,
            **context,
        )

        # Generate PDF
        pdf_bytes = html_cls(
            string=html_content, base_url=os.path.abspath(self.template_dir)
        ).write_pdf()

        if pdf_bytes is None:
            raise RuntimeError("Failed to generate PDF bytes")

        from typing import cast

        return cast(bytes, pdf_bytes)

