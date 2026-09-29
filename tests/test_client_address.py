"""Buyer postal address: CLI options, invoice snapshots, and persistence."""

from pathlib import Path

import pytest
from click.testing import Result
from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceStatus
from typer.testing import CliRunner

from py_invoices import RepositoryFactory
from py_invoices.cli.main import app
from py_invoices.core.credit_service import CreditService
from py_invoices.operations.invoices import clone_invoice

runner = CliRunner()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def cli(data_dir: Path):  # type: ignore[no-untyped-def]
    env = {
        "INVOICES_BACKEND": "files",
        "INVOICES_STORAGE_PATH": str(data_dir),
        "INVOICES_FILE_FORMAT": "json",
    }

    def invoke(*args: str) -> Result:
        return runner.invoke(app, list(args), env=env)

    return invoke


def files_factory(data_dir: Path) -> RepositoryFactory:
    return RepositoryFactory("files", root_dir=str(data_dir), file_format="json")


def test_client_create_stores_address(cli, data_dir: Path) -> None:  # type: ignore[no-untyped-def]
    result = cli(
        "clients", "create", "--name", "Acme", "--address", "Main St 1",
        "--city", "Berlin", "--postal-code", "10115", "--country", "de",
    )  # fmt: skip

    assert result.exit_code == 0, result.stdout
    client = files_factory(data_dir).create_client_repository().get_by_name("Acme")
    assert client is not None
    assert (client.city, client.postal_code, client.country) == ("Berlin", "10115", "DE")
    details = cli("clients", "details", "Acme")
    assert "Country: DE" in details.stdout


def test_invalid_country_is_rejected(cli) -> None:  # type: ignore[no-untyped-def]
    result = cli("clients", "create", "--name", "Acme", "--address", "x", "--country", "Germany")

    assert result.exit_code == 1
    assert "Invalid --country 'Germany'" in result.stdout


def test_new_client_address_is_snapshotted(cli, data_dir: Path) -> None:  # type: ignore[no-untyped-def]
    result = cli(
        "invoices", "create", "--amount", "100", "--description", "Work",
        "--client-name", "Buyer SARL", "--client-address", "1 Rue Haute",
        "--client-city", "Paris", "--client-postal-code", "75001", "--client-country", "fr",
        "--invoice-number", "INV-ADDR-1",
    )  # fmt: skip

    assert result.exit_code == 0, result.stdout
    invoice = files_factory(data_dir).create_invoice_repository().get_by_number("INV-ADDR-1")
    assert invoice is not None
    assert invoice.client_city_snapshot == "Paris"
    assert invoice.client_postal_code_snapshot == "75001"
    assert invoice.client_country_snapshot == "FR"


def test_clone_and_credit_note_copy_address_snapshots(
    cli,  # type: ignore[no-untyped-def]
    data_dir: Path,
) -> None:
    cli(
        "invoices", "create", "--amount", "100", "--description", "Work",
        "--client-name", "Buyer SARL", "--client-city", "Paris",
        "--client-postal-code", "75001", "--client-country", "FR",
        "--invoice-number", "INV-ADDR-2",
    )  # fmt: skip
    factory = files_factory(data_dir)
    repo = factory.create_invoice_repository()
    original = repo.get_by_number("INV-ADDR-2")
    assert original is not None

    cloned = clone_invoice(factory, "INV-ADDR-2", original.issue_date).invoice
    credit_note = CreditService(repo).create_credit_note(
        repo.update(original.model_copy(update={"status": InvoiceStatus.SENT})), reason="Refund"
    )

    for copy in (cloned, credit_note):
        assert copy.client_city_snapshot == "Paris"
        assert copy.client_postal_code_snapshot == "75001"
        assert copy.client_country_snapshot == "FR"


def test_sqlite_round_trip(tmp_path: Path) -> None:
    factory = RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    try:
        client = factory.create_client_repository().create(
            ClientCreate(name="Acme", city="Lyon", postal_code="69001", country="FR")
        )
        stored = factory.create_client_repository().get_by_id(client.id)
        assert stored is not None
        assert (stored.city, stored.postal_code, stored.country) == ("Lyon", "69001", "FR")

        invoice = factory.create_invoice_repository().create(
            InvoiceCreate(
                number="INV-SQL-1",
                client_id=client.id,
                client_city_snapshot="Lyon",
                client_postal_code_snapshot="69001",
                client_country_snapshot="fr",
            )
        )
        loaded = factory.create_invoice_repository().get_by_id(invoice.id)
        assert loaded is not None
        assert loaded.client_city_snapshot == "Lyon"
        assert loaded.client_postal_code_snapshot == "69001"
        assert loaded.client_country_snapshot == "FR"
    finally:
        factory.cleanup()
