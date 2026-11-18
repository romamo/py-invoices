"""Where the invoice CLI reads settings and stored paths from, and where it writes files."""

from datetime import date
from pathlib import Path

from conftest import Cli
from pydantic_invoices.schemas.company import CompanyCreate
from test_cli_invoices import create, factory

NUMBER = f"INV-{date.today().year}-0001"


def test_output_dir_follows_the_setting_then_the_flag(cli: Cli, tmp_path: Path) -> None:
    assert create(cli).exit_code == 0
    work = tmp_path / "work"
    work.mkdir()

    from_dotenv = work / ".env"
    from_dotenv.write_text("INVOICES_OUTPUT_DIR=Outbox\n")
    result = cli("invoices", "html", NUMBER, cwd=work)
    assert result.exit_code == 0, result.stdout
    assert Path(result.envelope["data"]["path"]) == work / "Outbox" / f"{NUMBER}.html"

    exported = tmp_path / "exported"
    result = cli(
        "invoices", "html", NUMBER, cwd=work, extra_env={"INVOICES_OUTPUT_DIR": str(exported)}
    )
    assert result.exit_code == 0, result.stdout
    assert Path(result.envelope["data"]["path"]) == exported / f"{NUMBER}.html"

    flag = tmp_path / "flag"
    result = cli("invoices", "html", NUMBER, "--output-dir", str(flag), cwd=work)
    assert result.exit_code == 0, result.stdout
    assert Path(result.envelope["data"]["path"]) == flag / f"{NUMBER}.html"


def test_create_export_follows_the_output_dir_setting(cli: Cli, tmp_path: Path) -> None:
    exported = tmp_path / "exported"
    result = create(cli, "-e", "json", extra_env={"INVOICES_OUTPUT_DIR": str(exported)})
    assert result.exit_code == 0, result.stdout
    assert result.envelope["data"]["exports"] == [
        {"format": "json", "path": str(exported / f"{NUMBER}.json")}
    ]


def test_cwd_applies_to_dotenv_storage_and_a_stored_logo(
    cli: Cli, tmp_path: Path, data_dir: Path
) -> None:
    store = tmp_path
    (store / ".env").write_text("INVOICES_OUTPUT_DIR=Outbox\n")
    (store / "assets").mkdir()
    (store / "assets" / "logo.png").write_bytes(b"logo")
    factory(data_dir).create_company_repository().create(
        CompanyCreate(
            name="Me Ltd", address="Road 1", logo_path="./assets/logo.png", is_default=True
        )
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    relative_store = {"INVOICES_STORAGE_PATH": "./data"}

    created = create(cli, "--cwd", "..", cwd=elsewhere, extra_env=relative_store)
    assert created.exit_code == 0, created.stdout
    result = cli("invoices", "html", NUMBER, "--cwd", "..", cwd=elsewhere, extra_env=relative_store)
    assert result.exit_code == 0, result.stdout

    path = store / "Outbox" / f"{NUMBER}.html"
    assert Path(result.envelope["data"]["path"]) == path
    assert "data:image/png;base64,bG9nbw==" in path.read_text()
    assert not (elsewhere / "data").exists()
