from collections.abc import Iterator
from contextlib import contextmanager

import typer
from pydantic_invoices.vo import CountryCode
from rich.console import Console
from rich.markup import escape

from py_invoices import RepositoryFactory
from py_invoices.config import InvoiceSettings
from py_invoices.core.pdf_service import WEASYPRINT_INSTALL_DOCS
from py_invoices.operations.errors import (
    ClientNotFoundError,
    ClientNotSpecifiedError,
    CompanyDetailsRequiredError,
    CompanyDetailsUnresolvedError,
    CreditNoteNotFoundError,
    InvoiceNotFoundError,
    MissingDependencyError,
    MissingSystemLibrariesError,
    OperationError,
    ProductNotFoundError,
)

console = Console()


def get_console() -> Console:
    return console


def get_factory(backend: str | None = None) -> RepositoryFactory:
    """Factory from the current environment; `backend` overrides the configured one."""
    settings = InvoiceSettings()
    if backend:
        settings = InvoiceSettings.model_validate({**settings.model_dump(), "backend": backend})
    return RepositoryFactory.from_settings(settings)


def error_lines(error: OperationError) -> list[str]:
    """Render an operation error as console lines, naming the CLI flags that fix it."""
    match error:
        case InvoiceNotFoundError():
            return [f"[red]Error: Invoice '{error.identifier}' not found.[/red]"]
        case ClientNotFoundError(by_id=True):
            return [f"[red]Error: Client with ID {error.identifier} not found.[/red]"]
        case ClientNotFoundError():
            return [f"[red]Error: Client '{error.identifier}' not found.[/red]"]
        case ProductNotFoundError():
            return [f"[red]Error: Product '{error.code}' not found.[/red]"]
        case CreditNoteNotFoundError():
            return [f"[red]Error: Credit Note '{error.number}' not found.[/red]"]
        case ClientNotSpecifiedError():
            return ["[red]Error: Must provide --client-id or --client-name[/red]"]
        case CompanyDetailsUnresolvedError():
            return [
                "[red]Error: Company details (name and address) could not be resolved. "
                "Please provide them via --company-name and --company-address or ensure "
                "the invoice has a valid company_id.[/red]"
            ]
        case CompanyDetailsRequiredError(lookup_attempted=True):
            return [
                "[red]Error: --company-name and --company-address are required when "
                "generating files and cannot be resolved automatically.[/red]"
            ]
        case CompanyDetailsRequiredError():
            return [
                "[red]Error: --company-name and --company-address are required when "
                "generating files.[/red]"
            ]
        case MissingSystemLibrariesError():
            library = f" ({escape(error.library)})" if error.library else ""
            lines = [
                f"[red]Error: {error.extra.upper()} generation cannot load the system "
                f"libraries it needs{library}.[/red]"
            ]
            if error.found_in:
                lines.append(
                    f"[yellow]They are installed in {escape(str(error.found_in))} but not on "
                    "the library search path.[/yellow]"
                )
            if error.steps:
                lines.append("Fix:")
                lines += [f"  [bold]{escape(step)}[/bold]" for step in error.steps]
            lines.append(f"[dim]See {WEASYPRINT_INSTALL_DOCS}[/dim]")
            return lines
        case MissingDependencyError():
            package = escape(f"py-invoices[{error.extra}]")
            return [
                f"[red]Error: {error.extra.upper()} generation dependencies missing.[/red]",
                escape(str(error)),
                f"[yellow]Tip: Install with `pip install '{package}'`[/yellow]",
            ]
    return [f"[red]Error: {error}[/red]"]


def parse_country(value: str | None, option: str) -> CountryCode | None:
    """An ISO 3166-1 alpha-2 country option, or exit with an error naming the option."""
    if value is None:
        return None
    try:
        return CountryCode(value)
    except ValueError:
        console.print(
            f"[red]Error: Invalid {option} '{escape(value)}'. "
            "Use an ISO 3166-1 alpha-2 code such as DE or FR.[/red]"
        )
        raise typer.Exit(code=1) from None


@contextmanager
def cli_errors() -> Iterator[None]:
    """Print an OperationError raised inside the block and exit with code 1."""
    try:
        yield
    except OperationError as e:
        for line in error_lines(e):
            console.print(line)
        raise typer.Exit(code=1) from e
