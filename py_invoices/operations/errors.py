"""Domain errors raised by operations. Presentation layers map them to messages and exit codes."""

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
