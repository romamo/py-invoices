"""Domain errors raised by operations. Presentation layers map them to messages and exit codes."""


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


class CompanyNotFoundError(OperationError):
    def __init__(self, company_id: int) -> None:
        super().__init__(f"Company with ID {company_id} not found")
        self.company_id = company_id


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
