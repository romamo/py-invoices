from io import StringIO
from pathlib import Path

from rich.console import Console

from py_invoices.cli.app import exit_for
from py_invoices.cli.utils import error_lines
from py_invoices.operations.errors import (
    CreditNoteRejectedError,
    MissingDependencyError,
    MissingSystemLibrariesError,
)


def render(lines: list[str]) -> str:
    out = StringIO()
    console = Console(file=out, width=200)
    for line in lines:
        console.print(line)
    return out.getvalue()


def test_missing_dependency_tip_keeps_extra_name() -> None:
    text = render(error_lines(MissingDependencyError("pdf", "no [lib] found")))

    assert "pip install 'py-invoices[pdf]'" in text
    assert "no [lib] found" in text


def test_missing_dependency_exit_suggests_the_extra() -> None:
    exit_ = exit_for(MissingDependencyError("pdf", "no weasyprint"))

    assert (exit_.name.value, exit_.code) == ("PRECONDITION", "MISSING_DEPENDENCY")
    assert exit_.suggestion == "pip install 'py-invoices[pdf]'"


def test_missing_system_libraries_exit_lists_the_fix_steps(tmp_path: Path) -> None:
    error = MissingSystemLibrariesError("pdf", "libgobject", ["brew install pango"], tmp_path, "x")

    exit_ = exit_for(error)

    assert exit_.code == "MISSING_SYSTEM_LIBRARIES"
    assert exit_.suggestion == "brew install pango"
    assert exit_.context == {
        "extra": "pdf",
        "steps": ["brew install pango"],
        "library": "libgobject",
        "found_in": str(tmp_path),
    }


def test_unmapped_operation_error_is_a_general_error_named_after_it() -> None:
    exit_ = exit_for(CreditNoteRejectedError("already credited"))

    assert (exit_.name.value, exit_.code) == ("GENERAL_ERROR", "CREDIT_NOTE_REJECTED")
