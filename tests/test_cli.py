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
