"""Tests for core services."""
from datetime import date
from pathlib import Path
from typing import Generator

from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    Invoice,
    InvoiceLine,
    Payment,
)
from py_invoices.core import AuditService, NumberingService, PDFService


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
        service.log_invoice_created(1, invoice_number="INV-001", total_amount=1000.0, client_name="Client A")
        service.log_invoice_created(2, invoice_number="INV-002", total_amount=2000.0, client_name="Client B")
        service.log_status_changed(1, invoice_number="INV-001", old_status="UNPAID", new_status="PAID")

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
        service.log_invoice_created(1, invoice_number="INV-001", total_amount=1000.0, client_name="Client A")
        assert len(service.get_logs()) == 1

        service.clear_logs()
        assert len(service.get_logs()) == 0


class TestPDFService:
    """Tests for PDFService."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test PDF service initialization."""
        output_dir = tmp_path / "output"
        service = PDFService(
            template_dir="custom_templates", output_dir=str(output_dir)
        )

        assert service.template_dir == "custom_templates"
        assert service.output_dir == str(output_dir)
        assert output_dir.exists()

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
        template_file.write_text(
            "Invoice: {{ invoice.number }}, Client: {{ company.name }}"
        )

        service = PDFService(
            template_dir=str(template_dir), output_dir=str(tmp_path / "output")
        )

        invoice = Invoice(
            id=1,
            number="INV-001",
            issue_date=date.today(),
            status="UNPAID",
            client_id=1,
            company_id=1,
            lines=[],
            payments=[],
        )

        company = {"name": "Test Company"}

        html = service.generate_html(
            invoice=invoice, company=company, template_name="test.html.j2"
        )

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
        service = PDFService(
            template_dir=str(template_dir), output_dir=str(output_dir)
        )

        invoice = Invoice(
            id=1,
            number="INV-001",
            issue_date=date.today(),
            status="UNPAID",
            client_id=1,
            company_id=1,
            lines=[],
            payments=[],
        )

        output_path = service.save_html(
            invoice=invoice, company={}, template_name="test.html.j2"
        )

        assert output_path == str(output_dir / "INV-001.html")
        assert (output_dir / "INV-001.html").exists()
        content = (output_dir / "INV-001.html").read_text()
        assert "INV-001" in content
