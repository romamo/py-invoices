"""Domain errors raised by operations. Presentation layers map them to messages and exit codes."""

from datetime import date
from pathlib import Path


class OperationError(Exception):
    """Base class for expected, user-facing operation failures."""


class InvoiceNotFoundError(OperationError):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"Invoice '{identifier}' not found")
        self.identifier = identifier


class ClientNotFoundError(OperationError):
    def __init__(self, identifier: str, *, by_id: bool) -> None:
        super().__init__(f"Client '{identifier}' not found")
        self.identifier = identifier
        self.by_id = by_id


class ClientNotSpecifiedError(OperationError):
    def __init__(self) -> None:
        super().__init__("Either a client ID or a client name is required")


class CompanyDetailsUnresolvedError(OperationError):
    """Company name and address are missing from overrides, snapshots, and the company record."""

    def __init__(self) -> None:
        super().__init__("Company name and address could not be resolved")


class CompanyDetailsRequiredError(OperationError):
    """Rendering export formats needs a company name and address."""

    def __init__(self, *, lookup_attempted: bool) -> None:
        super().__init__("Company name and address are required to render invoice files")
        self.lookup_attempted = lookup_attempted


class MissingDependencyError(OperationError):
    """An optional extra needed by the operation is not installed."""

    def __init__(self, extra: str, detail: str) -> None:
        super().__init__(detail)
        self.extra = extra


class MissingSystemLibrariesError(OperationError):
    """An installed extra cannot load the system libraries it needs."""

    def __init__(
        self, extra: str, library: str | None, steps: list[str], found_in: Path | None, detail: str
    ) -> None:
        super().__init__(detail)
        self.extra = extra
        self.library = library
        self.steps = steps
        self.found_in = found_in


class ProductNotFoundError(OperationError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Product '{code}' not found")
        self.code = code


class CreditNoteNotFoundError(OperationError):
    def __init__(self, number: str) -> None:
        super().__init__(f"Credit Note '{number}' not found")
        self.number = number


class CreditNoteRejectedError(OperationError):
    """The credit service refused to credit the invoice."""


class DuplicateInvoiceNumberError(OperationError):
    def __init__(self, number: str) -> None:
        super().__init__(f"Invoice number '{number}' is already used")
        self.number = number


class CompanyNotFoundError(OperationError):
    def __init__(self, company_id: int) -> None:
        super().__init__(f"Company {company_id} not found")
        self.company_id = company_id


class NumberPrefixError(OperationError):
    """A number prefix that is malformed or already gives another company its series."""

    def __init__(self, message: str, number_prefix: str) -> None:
        super().__init__(message)
        self.number_prefix = number_prefix


class SeriesNumberTakenError(OperationError):
    """The next number of a company's series is held by another company's invoice."""

    def __init__(self, message: str, number: str, company_id: int) -> None:
        super().__init__(message)
        self.number = number
        self.company_id = company_id


class InvalidAmountError(OperationError):
    def __init__(self, amount: str) -> None:
        super().__init__(f"Amount must be a positive number, got '{amount}'")
        self.amount = amount


class PaymentTermsError(OperationError):
    """The due date cannot be derived from free-form payment terms."""

    def __init__(self, terms: str) -> None:
        super().__init__(
            f"Cannot derive a due date from payment terms '{terms}'; "
            "use 'Net <days>', 'Due on Receipt', or give the due date explicitly"
        )
        self.terms = terms


class UnknownExportFormatError(OperationError):
    def __init__(self, formats: list[str], supported: list[str]) -> None:
        super().__init__(
            f"Unknown format(s): {', '.join(formats)}. Supported: {', '.join(supported)}"
        )
        self.formats = formats


class LogoNotFoundError(OperationError):
    def __init__(self, path: str) -> None:
        super().__init__(f"Company logo not found: {path}")
        self.path = path


class OutputExistsError(OperationError):
    """A file to be written exists; replacing it needs an explicit overwrite."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Output file already exists: {path}")
        self.path = path


class PaymentNoteNotFoundError(OperationError):
    def __init__(self, note_id: int) -> None:
        super().__init__(f"Payment note {note_id} referenced by the invoice does not exist")
        self.note_id = note_id


class SummaryUnavailableError(OperationError):
    """The stored invoices cannot be summarized (e.g. they use several currencies)."""


class InvalidInvoiceNumberError(OperationError):
    """Invoice numbers become file names, so they cannot contain path parts."""

    def __init__(self, number: str) -> None:
        super().__init__(f"Invoice number {number!r} cannot contain '/', '\\' or start with '.'")
        self.number = number


class InvoiceNotDraftError(OperationError):
    """Only a draft can be edited or issued; an issued invoice is corrected by a credit note."""

    def __init__(self, number: str, status: str) -> None:
        super().__init__(
            f"Invoice {number} is {status}, not a draft; only drafts can be edited or issued"
        )
        self.number = number
        self.status = status


class LineSelectionError(OperationError):
    """A line change names no line, or one the invoice does not have."""

    def __init__(self, number: str, line_count: int, line: int | None) -> None:
        if line is None:
            message = (
                f"Invoice {number} has {line_count} lines; choose one with --line "
                f"(0-{line_count - 1})"
            )
        else:
            message = f"Invoice {number} has no line {line}; lines are 0-{line_count - 1}"
        super().__init__(message)
        self.number = number
        self.line_count = line_count
        self.line = line


class InvalidDueDateError(OperationError):
    def __init__(self, number: str, issue_date: date, due_date: date) -> None:
        super().__init__(
            f"Invoice {number}: due date {due_date} is before the issue date {issue_date}"
        )
        self.number = number


class PaymentNoteMissingError(OperationError):
    def __init__(self, note_id: int) -> None:
        super().__init__(f"Payment note {note_id} not found")
        self.note_id = note_id


class PaymentNoteStateError(OperationError):
    """A payment note is in the wrong state for the change (inactive, or the default)."""
