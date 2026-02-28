from typer.testing import CliRunner

from py_invoices.cli.main import app
from py_invoices.config import get_settings

runner = CliRunner()


def test_config_show_command() -> None:
    """Test the config show command displays expected information."""
    result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "Invoices Engine Configuration" in result.stdout
    assert "Backend" in result.stdout
    if get_settings().database_url:
        assert "Database URL" in result.stdout
    assert "Default File Format" in result.stdout
    assert "Output Directory" in result.stdout
    assert "Template Directory" in result.stdout

    # Verify specific default values appearing in the output (assuming defaults)
    # Note: These assertions might need adjustment if specific env vars are set during test
    settings = get_settings()
    assert settings.backend in result.stdout
    assert settings.file_format in result.stdout
