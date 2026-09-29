"""Tests for core services."""

import re
import zlib
from datetime import datetime
from pathlib import Path

import pytest
from pydantic_invoices.schemas import (
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    InvoiceType,
)

from py_invoices.core import AuditService, NumberingService, PDFService, UBLService
from py_invoices.core.pdf_service import PdfSystemLibrariesError, WeasyPrintMissingError
from py_invoices.core.validator import UBLValidator


class TestNumberingService:
    """Tests for NumberingService."""

    def test_default_format(self) -> None:
        """Test default invoice number format."""
        service = NumberingService()
        number = service.generate_number(1, year=2025)
        assert number == "INV-2025-0001"

    def test_custom_format(self) -> None:
        """Test custom invoice number format."""
        service = NumberingService("INVOICE-{year}-{month:02d}-{sequence:03d}")
        number = service.generate_number(42, year=2025)
        # Month will be current month, so we just check the structure
        assert number.startswith("INVOICE-2025-")
        assert number.endswith("-042")

    def test_sequence_padding(self) -> None:
        """Test sequence number padding."""
        service = NumberingService()
        assert service.generate_number(1, year=2025) == "INV-2025-0001"
        assert service.generate_number(99, year=2025) == "INV-2025-0099"
        assert service.generate_number(1000, year=2025) == "INV-2025-1000"

    def test_parse_number(self) -> None:
        """Test parsing invoice numbers."""
        service = NumberingService()
        parsed = service.parse_number("INV-2025-0042")
        assert parsed["prefix"] == "INV"
        assert parsed["year"] == 2025
        assert parsed["sequence"] == 42


class TestAuditService:
    """Tests for AuditService."""

    def test_log_invoice_created(self) -> None:
        """Test logging invoice creation."""
        service = AuditService()
        entry = service.log_invoice_created(
            1,
            invoice_number="INV-2025-0001",
            total_amount=1000.0,
            client_name="Test Client",
            user_id="admin",
        )

        assert entry.invoice_id == 1
        assert entry.invoice_number == "INV-2025-0001"
        assert entry.action == "CREATED"
        assert "Test Client" in (entry.new_value or "")
        assert entry.user == "admin"

    def test_log_status_changed(self) -> None:
        """Test logging status changes."""
        service = AuditService()
        entry = service.log_status_changed(
            1,
            invoice_number="INV-2025-0001",
            old_status="UNPAID",
            new_status="PAID",
        )

        assert entry.action == "STATUS_CHANGED"
        assert entry.old_value == "UNPAID"
        assert entry.new_value == "PAID"
        assert "PAID" in (entry.new_value or "")

    def test_log_payment_added(self) -> None:
        """Test logging payment additions."""
        service = AuditService()
        entry = service.log_payment_added(
            1,
            invoice_number="INV-2025-0001",
            payment=500.0,
            old_balance=1000.0,
            new_balance=500.0,
            payment_method="Bank Transfer",
        )

        assert entry.action == "PAYMENT_ADDED"
        assert "$500.00" in (entry.new_value or "")
        assert "Bank Transfer" in (entry.notes or "")

    def test_get_logs_filtering(self) -> None:
        """Test filtering audit logs."""
        service = AuditService()

        # Create multiple logs
        service.log_invoice_created(
            1, invoice_number="INV-001", total_amount=1000.0, client_name="Client A"
        )
        service.log_invoice_created(
            2, invoice_number="INV-002", total_amount=2000.0, client_name="Client B"
        )
        service.log_status_changed(
            1, invoice_number="INV-001", old_status="UNPAID", new_status="PAID"
        )

        # Filter by invoice_id
        logs = service.get_logs(invoice_id=1)
        assert len(logs) == 2

        # Filter by action
        logs = service.get_logs(action="CREATED")
        assert len(logs) == 2

        # Filter by invoice_number
        logs = service.get_logs(invoice_number="INV-002")
        assert len(logs) == 1

    def test_clear_logs(self) -> None:
        """Test clearing audit logs."""
        service = AuditService()
        service.log_invoice_created(
            1, invoice_number="INV-001", total_amount=1000.0, client_name="Client A"
        )
        assert len(service.get_logs()) == 1

        service.clear_logs()
        assert len(service.get_logs()) == 0


class TestPDFService:
    """Tests for PDFService."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test PDF service initialization."""
        output_dir = tmp_path / "output"
        service = PDFService(template_dir="custom_templates", output_dir=str(output_dir))

        assert service.template_dir == "custom_templates"
        assert service.output_dir == str(output_dir)
        assert not output_dir.exists()  # created on first save, not at construction

    def test_default_template_resolution(self, tmp_path: Path) -> None:
        """Test default template directory resolution."""
        # Case 1: Package templates (when no local templates dir)
        # We need to ensure CWD doesn't have 'templates' for this test
        # We can pass an output dir that definitely exists
        service = PDFService(output_dir=str(tmp_path / "output"))

        # Should point to package directory (absolute path)
        assert "py_invoices" in service.template_dir
        assert "templates" in service.template_dir
        assert Path(service.template_dir).is_absolute()

    def test_generate_html(self, tmp_path: Path) -> None:
        """Test HTML generation."""
        # Create a simple template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "test.html.j2"
        template_file.write_text("Invoice: {{ invoice.number }}, Client: {{ company.name }}")

        service = PDFService(template_dir=str(template_dir), output_dir=str(tmp_path / "output"))

        invoice = Invoice(
            id=1,
            number="INV-001",
            issue_date=datetime.now().date(),
            status=InvoiceStatus.UNPAID,
            client_id=1,
            company_id=1,
            original_invoice_id=None,
            reason=None,
            due_date=None,
            client_name_snapshot=None,
            client_address_snapshot=None,
            client_tax_id_snapshot=None,
            lines=[],
            payments=[],
        )

        company = {"name": "Test Company"}

        html = service.generate_html(invoice=invoice, company=company, template_name="test.html.j2")

        assert "INV-001" in html
        assert "Test Company" in html

    def test_save_html(self, tmp_path: Path) -> None:
        """Test saving HTML to file."""
        # Create a simple template
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template_file = template_dir / "test.html.j2"
        template_file.write_text("Invoice: {{ invoice.number }}")

        output_dir = tmp_path / "output"
        service = PDFService(template_dir=str(template_dir), output_dir=str(output_dir))

        invoice = Invoice(
            id=1,
            number="INV-001",
            issue_date=datetime.now().date(),
            status=InvoiceStatus.UNPAID,
            client_id=1,
            company_id=1,
            client_name_snapshot="Test Client",
            client_address_snapshot="123 Test St",
            client_tax_id_snapshot="US-12345",
            original_invoice_id=None,
            reason=None,
            due_date=None,
            lines=[],
            payments=[],
        )

        output_path = service.save_html(invoice=invoice, company={}, template_name="test.html.j2")

        assert output_path == str(output_dir / "INV-001.html")
        assert (output_dir / "INV-001.html").exists()
        content = (output_dir / "INV-001.html").read_text()
        assert "INV-001" in content

    def test_facturx_bytes_generation(self, tmp_path: Path) -> None:
        """Factur-X output is a PDF/A-3B document with the UBL XML embedded."""
        service = PDFService(output_dir=str(tmp_path))
        try:
            service._get_weasyprint_modules()
        except (WeasyPrintMissingError, PdfSystemLibrariesError) as e:
            pytest.skip(f"WeasyPrint unavailable: {e}")

        pdf_bytes = service.generate_facturx_bytes(_invoice("FX-BYTES-001"), {"name": "Test Co"})

        assert pdf_bytes.startswith(b"%PDF-")
        streams = _pdf_streams(pdf_bytes)
        xmp = next(s for s in streams if b"pdfaid" in s)
        assert re.search(rb'pdfaid:part(>|=")3', xmp)
        assert re.search(rb'pdfaid:conformance(>|=")B', xmp)
        assert any(b"<Invoice" in s and b"FX-BYTES-001" in s for s in streams)


def _pdf_streams(pdf: bytes) -> list[bytes]:
    """Every stream in a PDF, inflated when Flate-compressed."""
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        raw = match.group(1)
        try:
            streams.append(zlib.decompress(raw))
        except zlib.error:
            streams.append(raw)
    return streams


class TestUBLService:
    """Tests for UBLService."""

    def test_generate_ubl_bytes(self, tmp_path: Path) -> None:
        """Test generating UBL XML as bytes."""
        service = UBLService(output_dir=str(tmp_path))

        invoice = _invoice("UBL-BYTES-001")

        company = {"name": "Test Co", "tax_id": "FR123"}

        # Generate bytes
        xml_bytes = service.generate_ubl_bytes(invoice, company)
        assert isinstance(xml_bytes, bytes)
        assert b"<Invoice" in xml_bytes
        assert b"UBL-BYTES-001" in xml_bytes
        assert b"Test Client" in xml_bytes


def _invoice(number: str, invoice_type: InvoiceType = InvoiceType.STANDARD) -> Invoice:
    return Invoice(
        id=1,
        number=number,
        type=invoice_type,
        client_id=1,
        client_name_snapshot="Test Client",
        client_address_snapshot="123 St",
        lines=[
            InvoiceLine(
                id=1, invoice_id=1, description="Work", quantity=2, unit_price="50", tax_rate=20
            )
        ],
    )


class TestRendering:
    """Escaping and totals in the bundled templates."""

    def test_html_escapes_user_data(self, tmp_path: Path) -> None:
        invoice = _invoice("INV-X").model_copy(
            update={
                "client_name_snapshot": "<script>alert(1)</script>",
                "client_address_snapshot": "A & B\nC",
            }
        )
        html = UBLService(output_dir=str(tmp_path)).generate_html(
            invoice, {"name": "Me <b>", "address": "Road 1\nTown"}, template_name="invoice.html.j2"
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "A &amp; B<br>C" in html
        assert "Me &lt;b&gt;" in html

    def test_html_shows_tax_and_gross_total(self, tmp_path: Path) -> None:
        html = UBLService(output_dir=str(tmp_path)).generate_html(
            _invoice("INV-T"), {"name": "Co", "address": "Road"}, template_name="invoice.html.j2"
        )
        assert "$100.00" in html
        assert "$20.00" in html
        assert "$120.00" in html

    def test_ubl_escapes_and_totals(self, tmp_path: Path) -> None:
        xml = UBLService(output_dir=str(tmp_path)).generate_ubl_bytes(
            _invoice("INV-U"), {"name": "Smith & Co", "address": "Road"}
        )
        assert UBLValidator.validate_bytes(xml, source="test").success
        assert b"Smith &amp; Co" in xml
        assert b'<cbc:PayableAmount currencyID="USD">120.00</cbc:PayableAmount>' in xml

    def test_credit_note_uses_ubl_credit_note_document(self, tmp_path: Path) -> None:
        xml = UBLService(output_dir=str(tmp_path)).generate_ubl_bytes(
            _invoice("CN-1", InvoiceType.CREDIT_NOTE),
            {"name": "Co", "address": "Road"},
            original_invoice_number="INV-1",
        )
        result = UBLValidator.validate_bytes(xml, source="test")
        assert result.success, result.messages
        assert b"<CreditNote" in xml
        assert b"<cbc:CreditNoteTypeCode>381</cbc:CreditNoteTypeCode>" in xml
        assert b"<cbc:ID>INV-1</cbc:ID>" in xml
