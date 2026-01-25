import pytest
from datetime import datetime
from unittest.mock import MagicMock
from typer.testing import CliRunner
from py_invoices.cli.main import app
from pydantic_invoices.schemas import Invoice, InvoiceStatus, InvoiceType, InvoiceLine

runner = CliRunner()

def test_invoices_details_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Mock Invoice Data
    mock_line = InvoiceLine(
        id=1,
        invoice_id=1,
        description="Test Product",
        quantity=1,
        unit_price=100.0,
        total=100.0
    )
    
    # Using model_construct to bypass validation if needed, though Invoice is stable
    mock_invoice = Invoice(
        id=1,
        number="INV-2026-TEST",
        issue_date=datetime.now(),
        status=InvoiceStatus.UNPAID,
        type=InvoiceType.STANDARD,
        due_date=datetime.now().date(),
        payment_terms="Due on Receipt",
        client_id=1,
        client_name_snapshot="Test Client",
        company_id=1,
        lines=[mock_line],
        payments=[],
        audit_logs=[]
    )

    # 2. Mock Repository and Factory
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = mock_invoice
    
    mock_factory = MagicMock()
    mock_factory.create_invoice_repository.return_value = mock_repo
    
    # 3. Patch get_factory
    monkeypatch.setattr("py_invoices.cli.invoices.get_factory", lambda *args: mock_factory)

    # 4. Run Command
    result = runner.invoke(app, ["invoices", "details", "1"])

    # 5. Assertions
    assert result.exit_code == 0
    assert "Invoice: INV-2026-TEST" in result.stdout
    assert "Test Product" in result.stdout
    assert "$100.00" in result.stdout
    # This specifically checks if line_total vs total works
    assert "Total" in result.stdout
