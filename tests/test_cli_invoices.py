"""End-to-end invoice CLI tests against a files backend in a temporary directory."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from py_invoices import RepositoryFactory
from py_invoices.cli.main import app
from py_invoices.core.validator import UBLValidator

runner = CliRunner()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def cli(data_dir: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    env = {
        "INVOICES_BACKEND": "files",
        "INVOICES_STORAGE_PATH": str(data_dir),
        "INVOICES_FILE_FORMAT": "json",
    }

    def invoke(*args: str) -> Result:
        return runner.invoke(app, list(args), env=env)

    return invoke


def factory(data_dir: Path) -> RepositoryFactory:
    return RepositoryFactory("files", root_dir=str(data_dir), file_format="json")


def create(cli, *extra: str):  # type: ignore[no-untyped-def]
    return cli(
        "invoices",
        "create",
        "--client-name",
        "UBL Tech",
        "--client-address",
        "99 XML Blvd",
        "--amount",
        "1234.50",
        "--description",
        "Consulting",
        "--company-name",
        "Me & Co",
        "--company-address",
        "Road 1",
        *extra,
    )


def test_create_exports_formats_with_exact_amounts(cli, data_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = create(cli, "-f", "json", "-f", "html", "-f", "ubl", "--output-dir", str(out))
    assert result.exit_code == 0, result.stdout
    assert "Created Client UBL Tech" in result.stdout
    assert "Total:  $1234.50" in result.stdout

    number = f"INV-{date.today().year}-0001"
    stored = json.loads((out / f"{number}.json").read_text())
    assert stored["lines"][0]["unit_price"] == "1234.50"
    assert "Me &amp; Co" in (out / f"{number}.html").read_text()
    assert UBLValidator.validate_file(str(out / f"{number}.xml")).success

    invoice = factory(data_dir).create_invoice_repository().get_by_number(number)
    assert invoice.company_name_snapshot == "Me & Co"
    assert invoice.due_date == date.today()


def test_net_terms_set_the_due_date(cli, data_dir: Path) -> None:
    assert create(cli, "--payment-terms", "Net 30").exit_code == 0
    invoice = factory(data_dir).create_invoice_repository().get_all()[0]
    assert invoice.due_date == date.today() + timedelta(days=30)


def test_unparseable_terms_need_an_explicit_due_date(cli, data_dir: Path) -> None:
    result = create(cli, "--payment-terms", "50% upfront")
    assert result.exit_code == 1
    assert "Cannot derive a due date" in result.stdout
    assert factory(data_dir).create_invoice_repository().get_all() == []

    due = (date.today() + timedelta(days=10)).isoformat()
    assert create(cli, "--payment-terms", "50% upfront", "--due-date", due).exit_code == 0


def test_unknown_format_is_rejected_before_creating(cli, data_dir: Path) -> None:
    result = create(cli, "-f", "docx")
    assert result.exit_code == 1
    assert "Unknown format(s): docx" in result.stdout
    assert factory(data_dir).create_invoice_repository().get_all() == []


def test_duplicate_number_and_bad_amount_are_rejected(cli) -> None:
    assert create(cli, "--invoice-number", "X-1").exit_code == 0
    result = create(cli, "--invoice-number", "X-1")
    assert result.exit_code == 1
    assert "already used" in result.stdout

    result = cli("invoices", "create", "--client-name", "A", "--amount", "-5", "--description", "d")
    assert result.exit_code == 1
    assert "positive number" in result.stdout


def test_details_stats_and_audit(cli) -> None:
    assert create(cli).exit_code == 0
    number = f"INV-{date.today().year}-0001"

    details = cli("invoices", "details", number)
    assert details.exit_code == 0
    assert "$1234.50" in details.stdout

    stats = cli("invoices", "stats")
    assert "Total Invoices:  1" in stats.stdout
    assert "Total Due:       $1234.50" in stats.stdout

    audit = cli("audit", "list")
    assert "CREATED" in audit.stdout


def test_clone_keeps_payment_period_and_company(cli, data_dir: Path) -> None:
    assert create(cli, "--payment-terms", "Net 14").exit_code == 0
    year = date.today().year

    result = cli("invoices", "clone", f"INV-{year}-0001", "--date", f"{year}-01-10")
    assert result.exit_code == 0, result.stdout
    assert f"INV-{year}-0001 -> INV-{year}-0002" in result.stdout

    clone = factory(data_dir).create_invoice_repository().get_by_number(f"INV-{year}-0002")
    assert clone.issue_date == date(year, 1, 10)
    assert clone.due_date == date(year, 1, 24)
    assert clone.company_name_snapshot == "Me & Co"
    assert "CLONED" in cli("audit", "list").stdout


def test_number_lookup_wins_over_id(cli) -> None:
    assert create(cli, "--invoice-number", "2").exit_code == 0
    assert create(cli, "--invoice-number", "INV-OTHER").exit_code == 0
    result = cli("invoices", "details", "2")
    assert "Invoice: 2" in result.stdout


def test_missing_logo_fails_instead_of_embedding_a_broken_path(cli, tmp_path: Path) -> None:
    result = create(cli, "-f", "html", "--company-logo-path", str(tmp_path / "nope.png"))
    assert result.exit_code == 1
    assert "logo not found" in result.stdout


def test_credit_note_cli_partial_then_rest(cli, data_dir: Path) -> None:
    repo_factory = factory(data_dir)
    assert create(cli).exit_code == 0
    number = f"INV-{date.today().year}-0001"

    too_much = cli("credit-notes", "create", number, "--reason", "r", "--line", "3")
    assert too_much.exit_code == 1
    assert "out of range" in too_much.stdout

    ok = cli("credit-notes", "create", number, "--reason", "refund")
    assert ok.exit_code == 0, ok.stdout
    assert f"CN-{date.today().year}-0001" in ok.stdout
    assert repo_factory.create_invoice_repository().get_by_number(number).status.value == (
        "CREDITED"
    )
    assert "Total Due:       $0.00" in cli("invoices", "stats").stdout


def test_export_prerequisites_are_checked_before_saving(cli, data_dir: Path) -> None:
    result = cli(
        "invoices",
        "create",
        "--client-name",
        "A",
        "--amount",
        "5",
        "--description",
        "d",
        "-f",
        "html",
    )
    assert result.exit_code == 1
    assert "could not be resolved" in result.stdout
    assert factory(data_dir).create_invoice_repository().get_all() == []


def test_custom_numbers_cannot_contain_paths(cli, data_dir: Path) -> None:
    result = create(cli, "--invoice-number", "../escape")
    assert result.exit_code == 1
    assert "cannot contain" in result.stdout


def test_currency_option_is_kept(cli, data_dir: Path) -> None:
    assert create(cli, "--currency", "EUR").exit_code == 0
    stats = cli("invoices", "stats")
    assert "Total Due:       €1234.50" in stats.stdout
