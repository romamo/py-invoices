from io import StringIO
from pathlib import Path

from rich.console import Console

from py_invoices.cli.utils import error_lines
from py_invoices.core.pdf_service import (
    WEASYPRINT_INSTALL_DOCS,
    PdfSystemLibrariesError,
    WeasyPrintMissingError,
    diagnose_missing_libraries,
)
from py_invoices.operations.errors import MissingDependencyError, MissingSystemLibrariesError
from py_invoices.operations.invoices import _pdf_unavailable


def render(lines: list[str]) -> str:
    out = StringIO()
    console = Console(file=out, width=200)
    for line in lines:
        console.print(line)
    return out.getvalue()


LOAD_ERROR = OSError(
    "cannot load library 'libgobject-2.0-0': dlopen(libgobject-2.0-0, 0x0002): not found"
)


def test_macos_libraries_installed_but_not_on_loader_path(tmp_path: Path) -> None:
    empty, brew = tmp_path / "empty", tmp_path / "brew"
    empty.mkdir()
    brew.mkdir()
    (brew / "libgobject-2.0.0.dylib").touch()

    error = diagnose_missing_libraries(LOAD_ERROR, "darwin", [empty, brew])

    assert error.library == "libgobject-2.0-0"
    assert error.found_in == brew
    assert error.steps == [f"export DYLD_FALLBACK_LIBRARY_PATH={brew}"]


def test_macos_libraries_not_installed(tmp_path: Path) -> None:
    error = diagnose_missing_libraries(LOAD_ERROR, "darwin", [tmp_path])

    assert error.found_in is None
    assert error.steps[0] == "brew install pango"


def test_linux_suggests_apt_packages() -> None:
    error = diagnose_missing_libraries(LOAD_ERROR, "linux", [])

    assert error.steps == ["sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b"]


def test_other_platforms_point_to_docs() -> None:
    error = diagnose_missing_libraries(OSError("boom"), "win32", [])

    assert error.library is None
    assert error.steps == []
    assert WEASYPRINT_INSTALL_DOCS in str(error)


def test_system_library_failure_is_not_reported_as_missing_package(tmp_path: Path) -> None:
    mapped = _pdf_unavailable(diagnose_missing_libraries(LOAD_ERROR, "darwin", [tmp_path]))
    assert isinstance(mapped, MissingSystemLibrariesError)

    missing = _pdf_unavailable(WeasyPrintMissingError("No module named 'weasyprint'"))
    assert isinstance(missing, MissingDependencyError)


def test_cli_shows_fix_steps_instead_of_pip_install(tmp_path: Path) -> None:
    (tmp_path / "libgobject-2.0.0.dylib").touch()
    cause: PdfSystemLibrariesError = diagnose_missing_libraries(LOAD_ERROR, "darwin", [tmp_path])
    error = MissingSystemLibrariesError("pdf", cause.library, cause.steps, cause.found_in, "x")

    text = render(error_lines(error))

    assert "(libgobject-2.0-0)" in text
    assert f"installed in {tmp_path}" in text
    assert f"export DYLD_FALLBACK_LIBRARY_PATH={tmp_path}" in text
    assert "pip install" not in text
