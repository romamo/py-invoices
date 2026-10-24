"""Test configuration for py-invoices."""

import json
import os
import subprocess
import sys
from collections.abc import Callable, Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from py_invoices import RepositoryFactory


@pytest.fixture(autouse=True, scope="function")
def reset_registry() -> Generator[None]:
    """Ensure backends are available for each test.

    With lazy registration, backends are registered on first factory creation.
    We don't need to clear the registry between tests since each test that needs
    a factory will trigger registration if needed.
    """
    yield
    # No cleanup needed - lazy registration handles this


@pytest.fixture
def factory() -> Generator[RepositoryFactory]:
    """Create a memory backend factory for testing."""
    factory = RepositoryFactory(backend="memory")
    yield factory
    factory.cleanup()


@pytest.fixture
def client_repo(factory: RepositoryFactory) -> Any:
    """Get client repository."""
    return factory.create_client_repository()


@pytest.fixture
def invoice_repo(factory: RepositoryFactory) -> Any:
    """Get invoice repository."""
    return factory.create_invoice_repository()


@pytest.fixture
def payment_repo(factory: RepositoryFactory) -> Any:
    """Get payment repository."""
    return factory.create_payment_repository()


@dataclass(frozen=True, slots=True)
class CliRun:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def envelope(self) -> dict[str, Any]:
        """The JSON envelope a treaty command prints off a terminal."""
        envelope: dict[str, Any] = json.loads(self.stdout)
        return envelope


type Cli = Callable[..., CliRun]


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def cli(data_dir: Path, tmp_path: Path) -> Cli:
    """Run the CLI entry point in a subprocess against a files backend in data_dir."""
    env = {
        **os.environ,
        "INVOICES_BACKEND": "files",
        "INVOICES_STORAGE_PATH": str(data_dir),
        "INVOICES_FILE_FORMAT": "json",
        "PY_INVOICES_AUDIT_LOG": "0",
        "PY_INVOICES_STATE_DIR": str(tmp_path / "state"),
    }

    def run(*args: str) -> CliRun:
        result = subprocess.run(
            [sys.executable, "-m", "py_invoices.cli.main", *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return CliRun(result.returncode, result.stdout, result.stderr)

    return run
