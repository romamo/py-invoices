"""PDF generation service.

Provides invoice PDF generation using Jinja2 templates and WeasyPrint.
"""

import base64
import io
import os
import re
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, cast

from pydantic_invoices.schemas import Invoice

from py_invoices.core.cii_service import CIIService
from py_invoices.core.html_service import HTMLService, output_path

FACTURX_FILENAME = "factur-x.xml"

# Factur-X 1.0 XMP: the fx properties plus the PDF/A extension schema that declares them
FACTURX_XMP = b"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
      xmlns:pdfaExtension="http://www.aiim.org/pdfa/ns/extension/"
      xmlns:pdfaSchema="http://www.aiim.org/pdfa/ns/schema#"
      xmlns:pdfaProperty="http://www.aiim.org/pdfa/ns/property#">
    <pdfaExtension:schemas>
      <rdf:Bag>
        <rdf:li rdf:parseType="Resource">
          <pdfaSchema:schema>Factur-X PDFA Extension Schema</pdfaSchema:schema>
          <pdfaSchema:namespaceURI>urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#</pdfaSchema:namespaceURI>
          <pdfaSchema:prefix>fx</pdfaSchema:prefix>
          <pdfaSchema:property>
            <rdf:Seq>
              <rdf:li rdf:parseType="Resource">
                <pdfaProperty:name>DocumentFileName</pdfaProperty:name>
                <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                <pdfaProperty:category>external</pdfaProperty:category>
                <pdfaProperty:description>Embedded XML file name</pdfaProperty:description>
              </rdf:li>
              <rdf:li rdf:parseType="Resource">
                <pdfaProperty:name>DocumentType</pdfaProperty:name>
                <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                <pdfaProperty:category>external</pdfaProperty:category>
                <pdfaProperty:description>INVOICE</pdfaProperty:description>
              </rdf:li>
              <rdf:li rdf:parseType="Resource">
                <pdfaProperty:name>Version</pdfaProperty:name>
                <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                <pdfaProperty:category>external</pdfaProperty:category>
                <pdfaProperty:description>Factur-X version</pdfaProperty:description>
              </rdf:li>
              <rdf:li rdf:parseType="Resource">
                <pdfaProperty:name>ConformanceLevel</pdfaProperty:name>
                <pdfaProperty:valueType>Text</pdfaProperty:valueType>
                <pdfaProperty:category>external</pdfaProperty:category>
                <pdfaProperty:description>Factur-X profile</pdfaProperty:description>
              </rdf:li>
            </rdf:Seq>
          </pdfaSchema:property>
        </rdf:li>
      </rdf:Bag>
    </pdfaExtension:schemas>
  </rdf:Description>
  <rdf:Description rdf:about=""
      xmlns:fx="urn:factur-x:pdfa:CrossIndustryDocument:invoice:1p0#">
    <fx:DocumentType>INVOICE</fx:DocumentType>
    <fx:DocumentFileName>factur-x.xml</fx:DocumentFileName>
    <fx:Version>1.0</fx:Version>
    <fx:ConformanceLevel>EN 16931</fx:ConformanceLevel>
  </rdf:Description>
</rdf:RDF>
"""

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
        cii_template_name: str | None = None,
        delivery_date: date | None = None,
        **context: Any,
    ) -> bytes:
        """Generate a Factur-X (EN 16931 profile) invoice or credit note.

        A PDF/A-3b document embedding CII XML as factur-x.xml, with the Factur-X XMP
        metadata. See CIIService.generate_cii for the data the invoice and company need.

        Raises:
            FacturXDataError: If data an EN 16931 invoice requires is missing.
        """
        _, attachment_cls = self._get_weasyprint_modules()
        cii = CIIService(template_dir=self.template_dir, output_dir=self.output_dir)
        xml_content = cii.generate_cii(
            invoice, company, cii_template_name, delivery_date, **context
        )
        html_content = self.generate_html(
            invoice=invoice, company=company, template_name=template_name, **context
        )
        # A data URL gives the embedded file the text/xml subtype Factur-X requires
        xml_url = "data:text/xml;base64," + base64.b64encode(xml_content.encode()).decode()
        attachment = attachment_cls(
            url=xml_url,
            name=FACTURX_FILENAME,
            description="Factur-X invoice data (EN 16931)",
            relationship="Alternative",
        )
        return self._render_pdf(
            html_content,
            attachments=[attachment],
            pdf_variant="pdf/a-3b",
            xmp_metadata=[io.BytesIO(FACTURX_XMP)],
        )

    def generate_facturx(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        cii_template_name: str | None = None,
        delivery_date: date | None = None,
        **context: Any,
    ) -> str:
        """Save a Factur-X PDF; defaults to "<number>_facturx.pdf"."""
        pdf_bytes = self.generate_facturx_bytes(
            invoice=invoice,
            company=company,
            template_name=template_name,
            cii_template_name=cii_template_name,
            delivery_date=delivery_date,
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
