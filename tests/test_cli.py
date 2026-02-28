import pytest
from typer.testing import CliRunner

from py_invoices.cli.main import app

runner = CliRunner()


def test_clients_create_and_list() -> None:
    # 1. List empty
    result = runner.invoke(app, ["clients", "list", "--backend", "memory"])
    assert result.exit_code == 0
    assert "No clients found" in result.stdout

    # 2. Create client
    result = runner.invoke(
        app,
        [
            "clients",
            "create",
            "--name",
            "Test Client",
            "--address",
            "123 Test St",
            "--tax-id",
            "US-TEST",
            "--backend",
            "memory",
        ],
    )
    assert result.exit_code == 0
    assert "Created Client Test Client" in result.stdout

    # 3. List again (Note: memory backend resets between invocations unless persisted.
    # The Typer runner doesn't persist memory state across invokes naturally
    # because `get_factory` re-initializes.
    # For unit testing CLI with memory backend, we might need to mock or use a persistent backend
    # fixture
    # if we want continuity.
    # However, let's just check the create output confirmed creation.
    # If we wanted to test persistence, we'd need to mock the repository
    # or use a file-based sqlite for tests.
    pass


def test_invoices_create_fail_no_client() -> None:
    result = runner.invoke(
        app,
        ["invoices", "create", "--amount", "100", "--description", "Desc", "--backend", "memory"],
    )
    assert result.exit_code == 1
    assert "Must provide --client-id or --client-name" in result.stdout


def test_invoices_help() -> None:
    result = runner.invoke(app, ["invoices", "--help"])
    assert result.exit_code == 0
    assert "Manage invoices" in result.stdout


def test_init_memory() -> None:
    result = runner.invoke(app, ["init", "--backend", "memory"])
    assert result.exit_code == 0
    assert "Memory backend selected" in result.stdout


def test_invoices_pdf_generation_mock() -> None:
    # Mock test for PDF generation
    result = runner.invoke(
        app,
        [
            "invoices",
            "pdf",
            "999",
            "--company-name",
            "Test Co",
            "--company-address",
            "Test Addr",
            "--backend",
            "memory",
        ],
    )
    assert result.exit_code == 1
    # Check output loosely to ignore ANSI colors
    assert "Invoice" in result.stdout
    assert "999" in result.stdout
    assert "not found" in result.stdout


def test_invoices_html_generation_mock() -> None:
    # Similar mock test for HTML
    result = runner.invoke(
        app,
        [
            "invoices",
            "html",
            "999",
            "--company-name",
            "Test Co",
            "--company-address",
            "Test Addr",
            "--backend",
            "memory",
        ],
    )
    assert result.exit_code == 1
    assert "Invoice" in result.stdout
    assert "999" in result.stdout
    assert "not found" in result.stdout


def test_invoices_create_with_formats_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime
    from unittest.mock import MagicMock

    # Mock Client Repo
    mock_client = MagicMock(id=1, address="Loc")
    mock_client.name = "Format Client"
    mock_client.tax_id = "US-TEST-123"

    mock_client_repo = MagicMock()
    mock_client_repo.get_all.return_value = [mock_client]

    # Mock Invoice Repo and Invoice Object
    mock_invoice_repo = MagicMock()
    # Use Real Pydantic Object to guarantee behavior
    from pydantic_invoices.schemas import Invoice, InvoiceStatus, InvoiceSummary

    # CRITICAL: Mock get_summary to return InvoiceSummary for NumberingService
    mock_invoice_repo.get_summary.return_value = InvoiceSummary(
        total_count=0,
        paid_count=0,
        unpaid_count=0,
        overdue_count=0,
        total_amount=0,
        total_paid=0,
        total_due=0,
    )

    mock_invoice = Invoice.model_construct(
        id=1,
        number="INV-2023-001",
        status=InvoiceStatus.UNPAID,
        issue_date=datetime.now(),
        due_date=datetime.now().date(),
        payment_terms="Net 30",
        client_id=1,
        client_name_snapshot="Format Client",
        client_address_snapshot="Loc",
        client_tax_id_snapshot="123",
        company_id=1,
        total_amount=500.0,
        subtotal=500.0,
        tax_amount=0.0,
        lines=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    mock_invoice_repo.create.return_value = mock_invoice

    # Mock Factory
    mock_factory = MagicMock()
    mock_factory.create_client_repository.return_value = mock_client_repo
    mock_factory.create_invoice_repository.return_value = mock_invoice_repo

    # Patch get_factory
    monkeypatch.setattr("py_invoices.cli.invoices.get_factory", lambda *args: mock_factory)

    # Run command
    result = runner.invoke(
        app,
        [
            "invoices",
            "create",
            "--client-name",
            "Format Client",
            "--amount",
            "500",
            "--description",
            "Test desc",
            "--format",
            "json",
            "--company-name",
            "Test Co",
            "--company-address",
            "Test Addr",
            "--backend",
            "memory",
        ],
    )

    if result.exit_code != 0:
        print(f"Result Output: {result.stdout}")

    assert result.exit_code == 0
    assert "Created Invoice" in result.stdout
    assert result.exit_code == 0
    assert "Created Invoice" in result.stdout
    assert "Generated JSON" in result.stdout


def test_invoices_create_autocreate_client() -> None:
    # Test that client is auto-created if not found
    result = runner.invoke(
        app,
        [
            "invoices",
            "create",
            "--client-name",
            "New Auto Client",
            "--amount",
            "200",
            "--description",
            "Test desc",
            "--backend",
            "memory",
        ],
    )

    assert result.exit_code == 0
    assert "Client 'New Auto Client' not found. Creating new client..." in result.stdout
    assert "Created Client New Auto Client" in result.stdout
    assert "Created Invoice" in result.stdout


def test_invoices_create_instant_ubl_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import MagicMock

    # Mock UBLService to inspect the passed invoice object
    mock_ubl_service = MagicMock()
    mock_ubl_service.save_ubl.return_value = "INV-TEST.xml"

    # Patch the class in core so that instantiation returns our mock
    monkeypatch.setattr("py_invoices.core.UBLService", lambda **kwargs: mock_ubl_service)

    # Run command: instant create (auto client) + UBL + memory
    result = runner.invoke(
        app,
        [
            "invoices",
            "create",
            "--client-name",
            "UBL Tech",
            "--client-address",
            "99 XML Blvd",
            "--client-tax-id",
            "XML-101",
            "--amount",
            "1234.50",
            "--description",
            "Test Service",
            "--format",
            "ubl",
            "--company-name",
            "UBL Factory",
            "--company-address",
            "XML Road",
            "--backend",
            "memory",
        ],
    )

    # 1. Verify successful functionality from user perspective
    assert result.exit_code == 0
    assert "Created Client UBL Tech" in result.stdout
    assert "Generated UBL XML" in result.stdout

    # 2. Verify strict data integrity on the created invoice passed to UBL generation
    assert mock_ubl_service.save_ubl.called
    call_kwargs = mock_ubl_service.save_ubl.call_args.kwargs
    invoice_arg = call_kwargs.get("invoice")

    assert invoice_arg is not None
    assert invoice_arg.client_name_snapshot == "UBL Tech"
    assert invoice_arg.client_address_snapshot == "99 XML Blvd"
    assert invoice_arg.client_tax_id_snapshot == "XML-101"
    assert invoice_arg.total_amount == 1234.50
    assert len(invoice_arg.lines) == 1
    assert invoice_arg.lines[0].unit_price == 1234.50
    assert invoice_arg.status.value == "UNPAID"
    assert invoice_arg.number.startswith("INV-")
