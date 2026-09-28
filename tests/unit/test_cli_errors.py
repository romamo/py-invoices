from io import StringIO

from rich.console import Console

from py_invoices.cli.utils import error_lines
from py_invoices.operations.errors import MissingDependencyError


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
