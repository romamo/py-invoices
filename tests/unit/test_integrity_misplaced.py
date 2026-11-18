"""A record stored under another ID than its own (#16): reported, never half-sealed."""

from pathlib import Path

import pytest
from conftest import Cli
from pydantic_invoices.schemas import (
    ClientCreate,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
)
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.backends.files.storage import MisplacedRecordError
from py_invoices.core.audit_service import AuditService
from py_invoices.operations.integrity import Finding, check_stored_invoices


def _files(tmp_path: Path) -> RepositoryFactory:
    return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="md")


def _legacy_invoices(factory: RepositoryFactory, count: int) -> None:
    """Issued invoices from before hashing: unsealed, so --seal has work to do."""
    client = factory.create_client_repository().create(ClientCreate(name="Legacy"))
    for n in range(1, count + 1):
        factory.create_invoice_repository().create(
            InvoiceCreate(
                number=f"INV-2025-000{n}",
                client_id=client.id,
                status=InvoiceStatus.UNPAID,
                lines=[
                    InvoiceLineCreate(description="A", quantity=1, unit_price=Money("1", "EUR"))
                ],
            )
        )


def _move(tmp_path: Path, entity: str, src: str, dst: str) -> None:
    folder = tmp_path / "data" / entity
    (folder / src).rename(folder / dst)


def test_validate_data_reports_a_file_named_for_another_id(tmp_path: Path) -> None:
    factory = _files(tmp_path)
    _legacy_invoices(factory, 2)
    _move(tmp_path, "invoices", "2.md", "7.md")

    report = check_stored_invoices(factory)

    assert not report.ok
    assert [(f.number, f.finding) for f in report.findings] == [
        ("invoices/7.md", Finding.MISPLACED),
        ("INV-2025-0001", Finding.UNSEALED),
        ("INV-2025-0002", Finding.UNSEALED),
    ]
    assert "holds id 2" in report.findings[0].detail


def test_misplaced_records_are_found_in_every_entity_folder(tmp_path: Path) -> None:
    factory = _files(tmp_path)
    _legacy_invoices(factory, 1)
    _move(tmp_path, "clients", "1.md", "4.md")

    assert [(r.location, r.record_id) for r in factory.plugin.misplaced_records()] == [
        ("clients/4.md", 1)
    ]


def test_seal_writes_nothing_while_a_record_is_misplaced(tmp_path: Path) -> None:
    factory = _files(tmp_path)
    _legacy_invoices(factory, 3)
    _move(tmp_path, "invoices", "3.md", "9.md")  # comes after 1 and 2, as in the issue

    report = check_stored_invoices(factory, seal=True)

    assert not report.ok
    assert [(f.number, f.finding) for f in report.findings] == [
        ("invoices/9.md", Finding.MISPLACED),
        ("INV-2025-0001", Finding.UNSEALABLE),
        ("INV-2025-0002", Finding.UNSEALABLE),
        ("INV-2025-0003", Finding.UNSEALABLE),
    ]
    stored = factory.create_invoice_repository().get_all()
    assert [i.content_hash for i in stored] == [None, None, None]
    audit = AuditService(audit_repo=factory.create_audit_repository()).get_logs()
    assert "SEALED" not in [e.action for e in audit]

    _move(tmp_path, "invoices", "9.md", "3.md")
    sealed = check_stored_invoices(factory, seal=True)
    assert sealed.ok and [f.finding for f in sealed.findings] == [Finding.SEALED] * 3


def test_loading_a_file_that_holds_another_id_refuses(tmp_path: Path) -> None:
    """Writing such a record back by the file's ID would overwrite another record."""
    factory = _files(tmp_path)
    _legacy_invoices(factory, 2)
    folder = tmp_path / "data" / "invoices"
    (folder / "1.md").unlink()
    _move(tmp_path, "invoices", "2.md", "1.md")

    with pytest.raises(MisplacedRecordError, match="holds the record with id 2"):
        factory.create_invoice_repository().get_by_id(1)


def test_cli_validate_data_seal_exits_1_without_a_traceback(cli: Cli, data_dir: Path) -> None:
    factory = RepositoryFactory("files", root_dir=str(data_dir), file_format="json")
    _legacy_invoices(factory, 2)
    (data_dir / "invoices" / "2.json").rename(data_dir / "invoices" / "5.json")

    check = cli("validate", "data")
    assert check.exit_code == 1
    assert "invoices/5.json: misplaced, holds id 2" in check.stdout

    seal = cli("validate", "data", "--seal")
    assert seal.exit_code == 1, seal.stderr
    assert "Traceback" not in seal.stderr
    assert "INV-2025-0001: unsealable" in seal.stdout
