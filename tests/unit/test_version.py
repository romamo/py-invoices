"""Tests for version consistency."""
from pathlib import Path

import tomllib

from py_invoices import __version__


def test_version_sync() -> None:
    """Ensure pyproject.toml and package __version__ are in sync."""
    # Read pyproject.toml
    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"

    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)

    project_version = pyproject_data["project"]["version"]

    assert __version__ == project_version, (
        f"Version mismatch: __init__.py has {__version__}, "
        f"but pyproject.toml has {project_version}"
    )
