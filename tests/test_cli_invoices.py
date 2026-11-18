"""End-to-end invoice CLI tests against a files backend in a temporary directory."""

import json
from datetime import date, timedelta
from pathlib import Path

from conftest import Cli, CliRun
from pydantic_invoices.schemas import Invoice, InvoiceCreate, InvoiceLineCreate, InvoiceStatus

from py_invoices import RepositoryFactory
from py_invoices.core.validator import UBLValidator


def factory(data_dir: Path) -> RepositoryFactory:
    return RepositoryFactory("files", root_dir=str(data_dir), file_format="json")


def create(cli: Cli, *extra: str) -> CliRun:
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
        "--issue",
        *extra,
    )


def stored(data_dir: Path, number: str) -> Invoice:
    invoice = factory(data_dir).create_invoice_repository().get_by_number(number)
    assert invoice is not None, number
    return invoice


def no_invoices(data_dir: Path) -> bool:
    return factory(data_dir).create_invoice_repository().get_all() == []


def test_create_exports_formats_with_exact_amounts(
    cli: Cli, data_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = create(cli, "-e", "json", "-e", "html", "-e", "ubl", "--output-dir", str(out))
    assert result.exit_code == 0, result.stdout
    data = result.envelope["data"]
    assert data["effect"] == "created"
    assert data["created_client"]["name"] == "UBL Tech"
    assert data["invoice"]["total"] == {"amount": "1234.50", "currency": "USD"}

    number = f"INV-{date.today().year}-0001"
    assert data["exports"] == [
        {"format": fmt, "path": str(out / f"{number}.{ext}")}
        for fmt, ext in (("json", "json"), ("html", "html"), ("ubl", "xml"))
    ]
    exported = json.loads((out / f"{number}.json").read_text())
    assert exported["lines"][0]["unit_price"] == "1234.50"
    assert "Me &amp; Co" in (out / f"{number}.html").read_text()
    assert UBLValidator.validate_file(str(out / f"{number}.xml")).success

    invoice = stored(data_dir, number)
    assert invoice.company_name_snapshot == "Me & Co"


def test_plain_output_keeps_the_human_format(cli: Cli) -> None:
    result = create(cli, "--format", "plain")
    assert result.exit_code == 0, result.stderr
    assert "Created Client UBL Tech" in result.stdout
    assert "Total:  $1234.50" in result.stdout


def test_default_terms_are_net_30(cli: Cli, data_dir: Path) -> None:
    assert create(cli).exit_code == 0
    invoice = factory(data_dir).create_invoice_repository().get_all()[0]
    assert invoice.payment_terms == "Net 30"
    assert invoice.due_date == invoice.issue_date + timedelta(days=30)


def test_due_on_receipt_is_due_on_the_issue_date(cli: Cli, data_dir: Path) -> None:
    assert create(cli, "--payment-terms", "Due on Receipt").exit_code == 0
    invoice = factory(data_dir).create_invoice_repository().get_all()[0]
    assert invoice.due_date == invoice.issue_date


def test_net_terms_set_the_due_date(cli: Cli, data_dir: Path) -> None:
    assert create(cli, "--payment-terms", "Net 30").exit_code == 0
    invoice = factory(data_dir).create_invoice_repository().get_all()[0]
    assert invoice.due_date == date.today() + timedelta(days=30)


def test_unparseable_terms_need_an_explicit_due_date(cli: Cli, data_dir: Path) -> None:
    result = create(cli, "--payment-terms", "50% upfront")
    assert result.exit_code == 2
    error = result.envelope["error"]
    assert error["phase"] == "validation"
    assert "Cannot derive a due date" in error["message"]
    assert error["suggestion"] == "pass --due-date YYYY-MM-DD"
    assert no_invoices(data_dir)

    due = (date.today() + timedelta(days=10)).isoformat()
    assert create(cli, "--payment-terms", "50% upfront", "--due-date", due).exit_code == 0


def test_unknown_format_is_rejected_before_creating(cli: Cli, data_dir: Path) -> None:
    result = create(cli, "-e", "docx")
    assert result.exit_code == 2
    assert result.envelope["error"]["message"] == "'export' must be one of pdf, html, ubl, json."
    assert no_invoices(data_dir)


def test_duplicate_number_is_a_conflict(cli: Cli) -> None:
    assert create(cli, "--invoice-number", "X-1").exit_code == 0
    result = create(cli, "--invoice-number", "X-1")
    assert result.exit_code == 6
    assert result.envelope["error"]["code"] == "DUPLICATE_INVOICE_NUMBER"
    assert result.envelope["error"]["conflict_id"] == "X-1"


def test_every_argument_error_is_reported_at_once(cli: Cli, data_dir: Path) -> None:
    result = cli("invoices", "create", "--amount", "-5", "--description", "d")
    assert result.exit_code == 2
    error = result.envelope["error"]
    assert [e["field"] for e in error["errors"]] == ["amount", "client_name"]
    assert "positive number" in error["errors"][0]["message"]
    assert no_invoices(data_dir)


def test_details_stats_and_audit(cli: Cli) -> None:
    assert create(cli).exit_code == 0
    number = f"INV-{date.today().year}-0001"

    details = cli("invoices", "details", number)
    assert details.exit_code == 0
    data = details.envelope["data"]
    assert data["total"] == {"amount": "1234.50", "currency": "USD"}
    assert [line["description"] for line in data["lines"]] == ["Consulting"]

    stats = cli("invoices", "stats", "--format", "plain")
    assert "Total Invoices:  1" in stats.stdout
    assert "Total Due:       $1234.50" in stats.stdout

    audit = cli("audit", "list")
    assert "CREATED" in audit.stdout


def test_missing_invoice_is_not_found(cli: Cli) -> None:
    for command in ("details", "pdf", "html", "clone"):
        result = cli("invoices", command, "999")
        assert result.exit_code == 5, command
        assert result.envelope["error"]["code"] == "INVOICE_NOT_FOUND"
        assert result.envelope["error"]["context"] == {"invoice": "999"}


def test_list_pages_newest_first(cli: Cli) -> None:
    empty = cli("invoices", "list", "--format", "plain")
    assert empty.stdout == "No invoices found.\n"

    last_year = date.today().year - 1
    assert create(cli, "--invoice-number", "TODAY-1").exit_code == 0
    for issued in ("01-10", "06-10"):
        clone = cli("invoices", "clone", "TODAY-1", "--date", f"{last_year}-{issued}")
        assert clone.exit_code == 0, clone.stdout
    assert create(cli, "--invoice-number", "TODAY-2").exit_code == 0

    first = cli("invoices", "list", "--limit", "2").envelope
    assert [row["number"] for row in first["data"]] == ["TODAY-2", "TODAY-1"]
    assert first["meta"]["pagination"]["total"] == 4
    assert first["meta"]["pagination"]["has_more"] is True

    cursor = first["meta"]["pagination"]["next_cursor"]
    rest = cli("invoices", "list", "--limit", "2", "--cursor", cursor).envelope
    assert [row["issue_date"] for row in rest["data"]] == [
        f"{last_year}-06-10",
        f"{last_year}-01-10",
    ]


def test_clone_keeps_payment_period_and_company(cli: Cli, data_dir: Path) -> None:
    assert create(cli, "--payment-terms", "Net 14").exit_code == 0
    year = date.today().year

    result = cli("invoices", "clone", f"INV-{year}-0001", "--date", f"{year}-01-10", "--issue")
    assert result.exit_code == 0, result.stdout
    data = result.envelope["data"]
    assert (data["original"], data["invoice"]["number"]) == (f"INV-{year}-0001", f"INV-{year}-0002")

    clone = stored(data_dir, f"INV-{year}-0002")
    assert clone.issue_date == date(year, 1, 10)
    assert clone.due_date == date(year, 1, 24)
    assert clone.company_name_snapshot == "Me & Co"
    assert "CLONED" in cli("audit", "list").stdout


def test_number_lookup_wins_over_id(cli: Cli) -> None:
    assert create(cli, "--invoice-number", "2").exit_code == 0
    assert create(cli, "--invoice-number", "INV-OTHER").exit_code == 0
    result = cli("invoices", "details", "2")
    assert result.envelope["data"]["number"] == "2"


def test_html_writes_the_document(cli: Cli, tmp_path: Path) -> None:
    assert create(cli).exit_code == 0
    number = f"INV-{date.today().year}-0001"
    result = cli("invoices", "html", number, "--output-dir", str(tmp_path / "out"))
    assert result.exit_code == 0, result.stdout
    data = result.envelope["data"]
    assert (data["effect"], data["format"], data["invoice"]) == ("created", "html", number)
    assert "Me &amp; Co" in Path(data["path"]).read_text()


def test_missing_logo_fails_instead_of_embedding_a_broken_path(
    cli: Cli, data_dir: Path, tmp_path: Path
) -> None:
    result = create(cli, "-e", "html", "--company-logo-path", str(tmp_path / "nope.png"))
    assert result.exit_code == 4
    assert result.envelope["error"]["code"] == "LOGO_NOT_FOUND"
    assert no_invoices(data_dir)


def test_credit_note_cli_partial_then_rest(cli: Cli, data_dir: Path) -> None:
    assert create(cli).exit_code == 0
    number = f"INV-{date.today().year}-0001"

    too_much = cli("credit-notes", "create", number, "--reason", "r", "--line", "3")
    assert too_much.exit_code == 1
    assert "out of range" in too_much.stdout

    ok = cli("credit-notes", "create", number, "--reason", "refund")
    assert ok.exit_code == 0, ok.stdout
    assert f"CN-{date.today().year}-0001" in ok.stdout
    assert stored(data_dir, number).status.value == "CREDITED"
    assert "Total Due:       $0.00" in cli("invoices", "stats", "--format", "plain").stdout


def test_export_prerequisites_are_checked_before_saving(cli: Cli, data_dir: Path) -> None:
    result = cli(
        "invoices",
        "create",
        "--client-name",
        "A",
        "--amount",
        "5",
        "--description",
        "d",
        "-e",
        "html",
    )
    assert result.exit_code == 4
    assert result.envelope["error"]["code"] == "COMPANY_DETAILS_REQUIRED"
    assert no_invoices(data_dir)


def test_custom_numbers_cannot_contain_paths(cli: Cli, data_dir: Path) -> None:
    result = create(cli, "--invoice-number", "../escape")
    assert result.exit_code == 2
    assert "cannot contain" in result.envelope["error"]["message"]
    assert no_invoices(data_dir)


def test_currency_option_is_kept(cli: Cli) -> None:
    assert create(cli, "--currency", "EUR").exit_code == 0
    stats = cli("invoices", "stats", "--format", "plain")
    assert "Total Due:       €1234.50" in stats.stdout


def test_draft_update_issue_and_integrity_check(cli: Cli, data_dir: Path) -> None:
    """The flow of #5: clone as a draft, adjust it, issue it; a later hand edit is caught."""
    year = date.today().year
    assert create(cli).exit_code == 0  # issued INV-<year>-0001

    cloned = cli("invoices", "clone", f"INV-{year}-0001", "--unit-price", "900")
    assert cloned.exit_code == 0, cloned.stdout
    draft = cloned.envelope["data"]["invoice"]
    assert (draft["number"], draft["status"]) == ("DRAFT-2", "DRAFT")
    assert draft["total"] == {"amount": "900", "currency": "USD"}

    updated = cli("invoices", "update", "DRAFT-2", "--quantity", "2")
    assert updated.exit_code == 0, updated.stdout
    assert updated.envelope["data"]["invoice"]["total"]["amount"] == "1800"

    issued = cli("invoices", "issue", "DRAFT-2")
    assert issued.exit_code == 0, issued.stdout
    data = issued.envelope["data"]
    assert (data["draft"], data["invoice"]["number"]) == ("DRAFT-2", f"INV-{year}-0002")
    assert len(data["content_hash"]) == 64

    again = cli("invoices", "update", f"INV-{year}-0002", "--quantity", "3")
    assert again.exit_code == 4
    assert again.envelope["error"]["code"] == "INVOICE_NOT_DRAFT"
    assert "credit-notes create" in again.envelope["error"]["suggestion"]

    assert cli("validate", "data").exit_code == 0
    path = data_dir / "invoices" / f"{stored(data_dir, f'INV-{year}-0002').id}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["lines"][0]["quantity"] = 20
    path.write_text(json.dumps(raw), encoding="utf-8")
    check = cli("validate", "data")
    assert check.exit_code == 1
    assert f"INV-{year}-0002: tampered" in check.stdout


def test_clone_line_flags_need_a_single_line_original(cli: Cli, data_dir: Path) -> None:
    assert create(cli).exit_code == 0
    repo = factory(data_dir).create_invoice_repository()
    original = repo.get_by_number(f"INV-{date.today().year}-0001")
    assert original is not None
    repo.create(
        InvoiceCreate(
            number="MULTI-1",
            client_id=original.client_id,
            status=InvoiceStatus.SENT,
            lines=[
                InvoiceLineCreate(description="A", quantity=1, unit_price="1"),
                InvoiceLineCreate(description="B", quantity=1, unit_price="2"),
            ],
        )
    )
    result = cli("invoices", "clone", "MULTI-1", "--amount", "5")
    assert result.exit_code == 4
    assert result.envelope["error"]["code"] == "LINE_SELECTION"
    assert no_invoices_numbered(data_dir, "DRAFT-")


def no_invoices_numbered(data_dir: Path, prefix: str) -> bool:
    repo = factory(data_dir).create_invoice_repository()
    return not [i for i in repo.get_all(limit=1000) if i.number.startswith(prefix)]


def test_payment_note_default_moves_and_old_note_retires(cli: Cli) -> None:
    assert cli("payment-notes", "create", "--content", "IBAN OLD", "--is-default").exit_code == 0
    assert cli("payment-notes", "create", "--content", "IBAN NEW").exit_code == 0
    refused = cli("payment-notes", "deactivate", "1")
    assert refused.exit_code == 1
    assert "default" in refused.stdout
    assert cli("payment-notes", "set-default", "2").exit_code == 0
    assert cli("payment-notes", "deactivate", "1").exit_code == 0
    assert "IBAN NEW" in cli("payment-notes", "default").stdout
    assert "IBAN OLD" not in cli("payment-notes", "list").stdout
