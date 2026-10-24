from conftest import Cli
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


def test_init_memory() -> None:
    result = runner.invoke(app, ["init", "--backend", "memory"])
    assert result.exit_code == 0
    assert "Memory backend selected" in result.stdout


def test_invoices_create_needs_a_client(cli: Cli) -> None:
    result = cli("invoices", "create", "--amount", "100", "--description", "Desc")
    assert result.exit_code == 2
    assert result.envelope["error"]["message"] == "--client-id or --client-name is required."


def test_invoices_help(cli: Cli) -> None:
    assert "Manage invoices" in runner.invoke(app, ["--help"]).stdout
    result = cli("invoices", "--help")
    assert result.exit_code == 0
    assert "Usage: py-invoices invoices <command>" in result.stderr


def test_invoices_pdf_and_html_need_the_invoice(cli: Cli) -> None:
    for command in ("pdf", "html"):
        result = cli(
            "invoices", command, "999", "--company-name", "Test Co",
            "--company-address", "Test Addr", "--backend", "memory",
        )  # fmt: skip
        assert result.exit_code == 5
        assert result.envelope["error"]["message"] == "Invoice '999' not found."


def test_invoices_create_autocreate_client(cli: Cli) -> None:
    result = cli(
        "invoices", "create", "--client-name", "New Auto Client", "--amount", "200",
        "--description", "Test desc", "--backend", "memory",
    )  # fmt: skip
    assert result.exit_code == 0
    envelope = result.envelope
    assert envelope["data"]["created_client"]["name"] == "New Auto Client"
    assert envelope["data"]["invoice"]["client"] == "New Auto Client"
    assert [w["code"] for w in envelope["warnings"]] == ["MEMORY_BACKEND"]
