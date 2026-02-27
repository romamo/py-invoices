from datetime import datetime
from unittest.mock import MagicMock

import pytest
from pydantic_invoices.schemas import Invoice, InvoiceLine, InvoiceStatus
from typer.testing import CliRunner

from py_invoices.cli.main import app

runner = CliRunner()


def test_stats_command(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock Repo
    mock_repo = MagicMock()
    mock_repo.get_summary.return_value = {
        "total_count": 10,
        "total_amount": 1000.50,
        "total_paid": 500.00,
        "total_due": 500.50,
        "overdue_count": 2,
    }

    mock_factory = MagicMock()
    mock_factory.create_invoice_repository.return_value = mock_repo

    monkeypatch.setattr("py_invoices.cli.invoices.get_factory", lambda *args: mock_factory)

    result = runner.invoke(app, ["invoices", "stats", "--backend", "memory"])

    if result.exit_code != 0:
        print(f"Stats failed: {result.stdout}")

    assert result.exit_code == 0
    assert "INVOICE STATISTICS" in result.stdout
    assert "Total Invoices:  10" in result.stdout
    assert "Total Amount:    $1000.50" in result.stdout
    assert "Overdue:         2" in result.stdout


def test_clone_command(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Mock Original Invoice
    original_invoice = Invoice.model_construct(
        id=1,
        number="INV-001",
        status=InvoiceStatus.PAID,
        issue_date=datetime.now(),
        due_date=datetime.now().date(),
        payment_terms="Net 30",
        template_name=None,
        client_id=1,
        client_name_snapshot="Test Client",
        client_address_snapshot="Addr",
        client_tax_id_snapshot="TAX123",
        company_id=1,
        total_amount=100.0,
        subtotal=100.0,
        tax_amount=0.0,
        lines=[
            InvoiceLine.model_construct(
                description="Item 1", quantity=1, unit_price=100.0, line_total=100.0
            )
        ],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    # 2. Mock New Invoice (Created)
    # We expect the created invoice to have a new ID and number
    new_invoice = original_invoice.model_copy(
        update={"id": 2, "number": "INV-2024-002", "status": InvoiceStatus.UNPAID}
    )

    # 3. Mock Repos
    mock_invoice_repo = MagicMock()
    mock_invoice_repo.get_by_number.return_value = original_invoice
    mock_invoice_repo.create.return_value = new_invoice
    # Mock summary for NumberingService: return 1 invoice exist, so next is 2
    mock_invoice_repo.get_summary.return_value = {"total_count": 1}

    mock_client = MagicMock()
    mock_client.preferred_template = "invoice.html.j2"
    mock_client_repo = MagicMock()
    mock_client_repo.get_by_id.return_value = mock_client

    mock_audit_repo = MagicMock()

    mock_factory = MagicMock()
    mock_factory.create_invoice_repository.return_value = mock_invoice_repo
    mock_factory.create_client_repository.return_value = mock_client_repo
    mock_factory.create_audit_repository.return_value = mock_audit_repo

    monkeypatch.setattr("py_invoices.cli.invoices.get_factory", lambda *args: mock_factory)

    # 4. Run Command
    result = runner.invoke(app, ["invoices", "clone", "INV-001", "--backend", "memory"])

    if result.exit_code != 0:
        print(f"Clone failed: {result.stdout}")

    assert result.exit_code == 0
    assert "Cloned Invoice INV-001 -> INV-2024-002" in result.stdout
    assert "Total:  $100.00" in result.stdout

    # Verify we tried to find original
    mock_invoice_repo.get_by_number.assert_called_with("INV-001")

    # Verify we created new
    assert mock_invoice_repo.create.called
    created_data = mock_invoice_repo.create.call_args[0][0]
    # Check if lines were copied
    assert len(created_data.lines) == 1
    assert created_data.lines[0].description == "Item 1"
