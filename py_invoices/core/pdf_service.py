"""PDF generation service.

Provides invoice PDF generation using Jinja2 templates and WeasyPrint.
"""

import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from pydantic_invoices.schemas import Invoice

from py_invoices.core.html_service import HTMLService, output_path
from py_invoices.core.ubl_service import UBLService

WEASYPRINT_INSTALL_DOCS = (
    "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation"
)
HOMEBREW_LIB_DIRS = (Path("/opt/homebrew/lib"), Path("/usr/local/lib"))

_LIBRARY_RE = re.compile(r"cannot load library '([^']+)'")


class WeasyPrintMissingError(ImportError):
    """The WeasyPrint package (the ``pdf`` extra) is not installed."""


class PdfSystemLibrariesError(ImportError):
    """WeasyPrint is installed but cannot load its system libraries (Pango, GObject).

    ``steps`` are shell commands for this platform; ``found_in`` is set when the
    libraries exist on disk but are not on the dynamic loader path.
    """

    def __init__(
        self, library: str | None, steps: list[str], found_in: Path | None, cause: str
    ) -> None:
        summary = (
            f"WeasyPrint cannot load system library '{library}'"
            if library
            else "WeasyPrint cannot load its system libraries"
        )
        lines = [summary]
        if found_in:
            lines.append(f"The libraries are in {found_in} but not on the loader path")
        lines += [f"Run: {step}" for step in steps]
        lines.append(f"See {WEASYPRINT_INSTALL_DOCS}")
        super().__init__("\n".join(lines))
        self.library = library
        self.steps = steps
        self.found_in = found_in
        self.cause = cause


def diagnose_missing_libraries(
    error: OSError,
    platform: str = sys.platform,
    homebrew_lib_dirs: Sequence[Path] = HOMEBREW_LIB_DIRS,
) -> PdfSystemLibrariesError:
    """Turn WeasyPrint's library load failure into platform-specific fix steps."""
    match = _LIBRARY_RE.search(str(error))
    library = match.group(1) if match else None

    if platform == "darwin":
        found_in = next(
            (d for d in homebrew_lib_dirs if any(d.glob("libgobject-2.0*.dylib"))), None
        )
        if found_in:
            steps = [f"export DYLD_FALLBACK_LIBRARY_PATH={found_in}"]
        else:
            steps = [
                "brew install pango",
                'export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix)/lib"',
            ]
        return PdfSystemLibrariesError(library, steps, found_in, str(error))

    if platform.startswith("linux"):
        steps = ["sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b"]
        return PdfSystemLibrariesError(library, steps, None, str(error))

    return PdfSystemLibrariesError(library, [], None, str(error))


class PDFService(HTMLService):
    """Service for generating PDF invoices from templates.

    Extends HTMLService with WeasyPrint rendering, including PDF/A-3 output that
    embeds the invoice's UBL XML.
    """

    @staticmethod
    def _get_weasyprint_modules() -> tuple[Any, Any]:
        """Import WeasyPrint's (HTML, Attachment) classes.

        Raises:
            WeasyPrintMissingError: If the WeasyPrint package is not installed
            PdfSystemLibrariesError: If its system libraries (Pango, GObject) cannot load
        """
        try:
            from weasyprint import HTML, Attachment  # type: ignore[import-untyped]
        except OSError as e:
            raise diagnose_missing_libraries(e) from e
        except ImportError as e:
            raise WeasyPrintMissingError(
                f"WeasyPrint is required for PDF generation but could not be imported: {e}"
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
            name="factur-x.xml",
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
