"""Tests for settings configuration."""

import json
import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from py_invoices import InvoiceSettings, RepositoryFactory


def run_with_env(code: str, env: dict[str, str], cwd: Path) -> Any:
    """Run `code` in a fresh interpreter with only `env` as INVOICES_* variables.

    The code must print JSON; a subprocess sets a real environment without patching
    os.environ, and `cwd` keeps a project .env file out of the result.
    """
    base = {k: v for k, v in os.environ.items() if not k.upper().startswith("INVOICES_")}
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        env={**base, **env},
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


SETTINGS_JSON = (
    "from py_invoices import InvoiceSettings; print(InvoiceSettings().model_dump_json())"
)


class TestInvoiceSettings:
    """Tests for InvoiceSettings."""

    def test_default_settings(self) -> None:
        """Test default settings values."""
        settings = InvoiceSettings()
        assert settings.backend == "memory"
        assert settings.database_url is None
        assert settings.database_echo is False
        assert settings.template_dir is None
        assert settings.output_dir == "output"

    def test_programmatic_settings(self) -> None:
        """Test creating settings programmatically."""
        settings = InvoiceSettings(
            backend="sqlite",
            database_url="sqlite:///test.db",
            database_echo=True,
            template_dir="./my_templates",
            output_dir="./my_output",
        )

        assert settings.backend == "sqlite"
        assert settings.database_url == "sqlite:///test.db"
        assert settings.database_echo is True
        assert settings.template_dir == "./my_templates"
        assert settings.output_dir == "./my_output"

    def test_environment_variables(self, tmp_path: Path) -> None:
        """Test loading from environment variables."""
        env = {
            "INVOICES_BACKEND": "postgres",
            "INVOICES_DATABASE_URL": "postgresql://localhost/test",
            "INVOICES_DATABASE_ECHO": "true",
        }

        settings = run_with_env(SETTINGS_JSON, env, tmp_path)

        assert settings["backend"] == "postgres"
        assert settings["database_url"] == "postgresql://localhost/test"
        assert settings["database_echo"] is True

    def test_case_insensitive_env_vars(self, tmp_path: Path) -> None:
        """Test that environment variables are case-insensitive."""
        settings = run_with_env(SETTINGS_JSON, {"invoices_backend": "sqlite"}, tmp_path)

        assert settings["backend"] == "sqlite"


class TestRepositoryFactoryFromSettings:
    """Tests for RepositoryFactory.from_settings()."""

    def test_from_settings_with_none(self) -> None:
        """Test from_settings with None (loads from environment)."""
        factory = RepositoryFactory.from_settings(None)
        assert factory is not None
        assert factory.health_check() is True

    def test_from_settings_with_explicit_settings(self) -> None:
        """Test from_settings with explicit settings object."""
        settings = InvoiceSettings(backend="memory")
        factory = RepositoryFactory.from_settings(settings)

        assert factory is not None
        assert factory.health_check() is True

    def test_from_settings_memory_backend(self) -> None:
        """Test creating memory backend via settings."""
        settings = InvoiceSettings(backend="memory")
        factory = RepositoryFactory.from_settings(settings)

        # Should be able to create repositories
        client_repo = factory.create_client_repository()
        invoice_repo = factory.create_invoice_repository()
        payment_repo = factory.create_payment_repository()

        assert client_repo is not None
        assert invoice_repo is not None
        assert payment_repo is not None

    def test_from_settings_with_database_config(self) -> None:
        """Test that database config is passed through."""
        settings = InvoiceSettings(
            backend="memory",  # Memory backend ignores these, but they should be passed
            database_url="sqlite:///test.db",
            database_echo=True,
        )

        factory = RepositoryFactory.from_settings(settings)
        assert factory is not None

    def test_from_settings_invalid_backend(self) -> None:
        """Test from_settings with invalid backend."""
        # Pydantic validation should catch this before factory creation
        with pytest.raises(ValidationError):
            InvoiceSettings(backend="invalid")

    def test_from_settings_environment_integration(self, tmp_path: Path) -> None:
        """Test full integration with environment variables."""
        code = (
            "import json; from py_invoices import RepositoryFactory; "
            "f = RepositoryFactory.from_settings(); "
            "print(json.dumps({'backend': f.plugin.name, 'healthy': f.health_check()}))"
        )
        env = {"INVOICES_BACKEND": "memory", "INVOICES_TEMPLATE_DIR": "./test_templates"}

        result = run_with_env(code, env, tmp_path)

        assert result == {"backend": "memory", "healthy": True}


class TestLazyBackendRegistration:
    """Tests for lazy backend registration."""

    def test_backends_registered_on_factory_creation(self) -> None:
        """Test that backends are registered when factory is created."""
        from py_invoices import PluginRegistry

        # Create factory - should trigger registration if not already registered
        factory = RepositoryFactory(backend="memory")

        # Now backends should be registered
        plugins = PluginRegistry.list_plugins()
        assert "memory" in plugins
        assert factory.health_check() is True

    def test_multiple_factory_creation_doesnt_duplicate(self) -> None:
        """Test that creating multiple factories doesn't duplicate registrations."""
        from py_invoices import PluginRegistry

        # Get initial count
        RepositoryFactory(backend="memory")
        count1 = len(PluginRegistry.list_plugins())

        # Create second factory
        RepositoryFactory(backend="memory")
        count2 = len(PluginRegistry.list_plugins())

        # Should have same number of plugins (lazy registration is idempotent)
        assert count1 == count2
        assert count1 > 0
