"""Where the invoice CLI reads settings and stored paths from, and where it writes files."""

from datetime import date
from pathlib import Path

from conftest import Cli
from test_cli_invoices import create

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
