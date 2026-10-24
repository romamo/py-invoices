"""The treaty app: command groups that answer with JSON envelopes and typed exit codes.

Groups move here from typer one at a time; `main` routes their names to this app.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic_invoices.vo import CountryCode, Money, TaxId
from treaty import App, CliExit, Ctx, Exit, Flag

from py_invoices import RepositoryFactory, __version__
from py_invoices.cli.utils import get_factory
from py_invoices.constants import APP_NAME, CLI_NAME
from py_invoices.core.pdf_service import WEASYPRINT_INSTALL_DOCS
from py_invoices.core.totals import format_money
from py_invoices.operations.errors import (
    ClientNotFoundError,
    CompanyDetailsRequiredError,
    CompanyDetailsUnresolvedError,
    DuplicateInvoiceNumberError,
    InvoiceNotFoundError,
    LogoNotFoundError,
    MissingDependencyError,
    MissingSystemLibrariesError,
    OperationError,
    PaymentNoteNotFoundError,
    SummaryUnavailableError,
)

app = App(CLI_NAME, version=__version__, description=f"CLI for {APP_NAME} management")

app.scalar(date, parse=date.fromisoformat, pattern=r"\d{4}-\d{2}-\d{2}", serialize=date.isoformat)
app.scalar(CountryCode, parse=CountryCode, pattern="[A-Za-z]{2}")
app.scalar(TaxId, parse=TaxId, pattern=r"[A-Za-z0-9\- .]{5,30}")

type Backend = Literal["memory", "sqlite", "postgres", "mysql", "files"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Common:
    backend: Backend | None = Flag(
        default=None, description="Storage backend; default INVOICES_BACKEND or memory"
    )


@dataclass(frozen=True, slots=True)
class Store:
    """The repository factory for the run's backend."""

    factory: RepositoryFactory

    @classmethod
    def acquire(cls, args: Common, ctx: Ctx) -> Self:
        return cls(get_factory(args.backend))


@dataclass(frozen=True, slots=True)
class Amount:
    amount: Decimal
    currency: str

    @classmethod
    def of(cls, money: Money) -> Self:
        return cls(money.amount, money.currency)


def show_money(value: object) -> str:
    """An Amount as JSON data, formatted for plain output."""
    if not isinstance(value, dict):
        raise TypeError(f"expected an amount object, got {value!r}")
    return format_money(Money(Decimal(value["amount"]), value["currency"]))


def _error_code(error: OperationError) -> str:
    """InvalidAmountError -> INVALID_AMOUNT"""
    name = type(error).__name__.removesuffix("Error")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def exit_for(error: OperationError) -> CliExit:
    """The exit an operation error ends the run with, naming the flags that fix it."""
    code = _error_code(error)
    match error:
        case InvoiceNotFoundError():
            return Exit.NOT_FOUND(
                str(error),
                code=code,
                context={"invoice": error.identifier},
                suggestion=f"{CLI_NAME} invoices list shows invoice numbers",
            )
        case ClientNotFoundError():
            return Exit.NOT_FOUND(
                str(error),
                code=code,
                context={"client": error.identifier},
                suggestion=f"{CLI_NAME} clients list shows client IDs",
            )
        case PaymentNoteNotFoundError():
            return Exit.NOT_FOUND(str(error), code=code, context={"payment_note": error.note_id})
        case DuplicateInvoiceNumberError():
            return Exit.CONFLICT(
                str(error),
                code=code,
                context={"invoice_number": error.number},
                conflict_id=error.number,
                suggestion="omit --invoice-number to number the invoice automatically",
            )
        case CompanyDetailsUnresolvedError() | CompanyDetailsRequiredError():
            return Exit.PRECONDITION(
                str(error),
                code="COMPANY_DETAILS_REQUIRED",
                suggestion="pass --company-name and --company-address, "
                f"or store them with {CLI_NAME} companies create",
            )
        case LogoNotFoundError():
            return Exit.PRECONDITION(
                str(error),
                code=code,
                context={"path": error.path},
                suggestion="pass --company-logo-path with an existing image file",
            )
        case MissingSystemLibrariesError():
            context: dict[str, object] = {"extra": error.extra, "steps": error.steps}
            if error.library:
                context["library"] = error.library
            if error.found_in:
                context["found_in"] = str(error.found_in)
            return Exit.PRECONDITION(
                str(error),
                code=code,
                context=context,
                detail=f"See {WEASYPRINT_INSTALL_DOCS}",
                suggestion="; ".join(error.steps) or None,
            )
        case MissingDependencyError():
            return Exit.PRECONDITION(
                str(error),
                code=code,
                context={"extra": error.extra},
                suggestion=f"pip install 'py-invoices[{error.extra}]'",
            )
        case SummaryUnavailableError():
            return Exit.PRECONDITION(str(error), code=code)
    return Exit.GENERAL_ERROR(str(error), code=code)


@contextmanager
def operation_errors() -> Iterator[None]:
    """End the run with the exit for an OperationError raised inside the block."""
    try:
        yield
    except OperationError as e:
        raise exit_for(e) from e
