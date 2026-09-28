"""Invoice operations: return domain objects, raise OperationError, never print."""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any

from pydantic_invoices.schemas import (
    Client,
    ClientCreate,
    Invoice,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceSummary,
    InvoiceType,
)
from pydantic_invoices.schemas.company import Company
from pydantic_invoices.vo import Money

from py_invoices.config import get_settings
from py_invoices.core import AuditService, HTMLService, NumberingService, PDFService, UBLService
from py_invoices.core.html_service import PACKAGE_TEMPLATES_DIR, is_safe_file_name, output_path
from py_invoices.core.paging import iter_all
from py_invoices.core.pdf_service import PdfSystemLibrariesError
from py_invoices.core.summary import MixedCurrencyError
from py_invoices.operations.errors import (
    ClientNotFoundError,
    ClientNotSpecifiedError,
    CompanyDetailsUnresolvedError,
    DuplicateInvoiceNumberError,
    InvalidAmountError,
    InvalidInvoiceNumberError,
    InvoiceNotFoundError,
    LogoNotFoundError,
    MissingDependencyError,
    MissingSystemLibrariesError,
    OperationError,
    PaymentNoteNotFoundError,
    PaymentTermsError,
    SummaryUnavailableError,
    UnknownExportFormatError,
)
from py_invoices.plugins.factory import RepositoryFactory
from py_invoices.utils.image import file_to_base64_data_uri

RENDERED_FORMATS = frozenset({"pdf", "html", "ubl"})
EXPORT_FORMATS = ("pdf", "html", "ubl", "json")

_NET_TERMS = re.compile(r"net\s*(\d+)(\s*days?)?", re.IGNORECASE)
_IMMEDIATE_TERMS = {"due on receipt", "due upon receipt", "immediate", "net 0"}


@dataclass(frozen=True, slots=True)
class CompanyOverrides:
    """Company details given explicitly by the caller; unset fields fall back to stored data."""

    name: str | None = None
    address: str | None = None
    tax_id: str | None = None
    email: str | None = None
    logo_path: str | None = None


@dataclass(frozen=True, slots=True)
class ResolvedCompany:
    details: dict[str, Any]
    logo: str | None


class DocumentKind(str, Enum):
    PDF = "pdf"
    HTML = "html"


@dataclass(frozen=True, slots=True)
class RenderedDocument:
    invoice: Invoice
    path: str


@dataclass(frozen=True, slots=True)
class NewInvoice:
    amount: Money
    description: str
    client_id: int | None = None
    client_name: str | None = None
    client_address: str | None = None
    client_tax_id: str | None = None
    client_email: str | None = None
    client_phone: str | None = None
    invoice_number: str | None = None
    payment_terms: str = "Due on Receipt"
    due_date: date | None = None
    company: CompanyOverrides = CompanyOverrides()
    template: str | None = None


@dataclass(frozen=True, slots=True)
class CreatedInvoice:
    invoice: Invoice
    created_client: Client | None


@dataclass(frozen=True, slots=True)
class ClonedInvoice:
    original: Invoice
    invoice: Invoice


@dataclass(frozen=True, slots=True)
class ExportOutcome:
    format: str
    path: str


def package_template_dir() -> str:
    return PACKAGE_TEMPLATES_DIR


def template_dir() -> str:
    """Configured template directory, else the bundled templates."""
    return get_settings().template_dir or PACKAGE_TEMPLATES_DIR


def find_invoice(factory: RepositoryFactory, identifier: str) -> Invoice:
    """Find an invoice by number first, then, for all-digit identifiers, by ID."""
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_number(identifier)
    if invoice is None and identifier.isdigit():
        invoice = repo.get_by_id(int(identifier))
    if invoice is None:
        raise InvoiceNotFoundError(identifier)
    return invoice


def list_invoices(factory: RepositoryFactory, limit: int) -> list[Invoice]:
    return factory.create_invoice_repository().get_all(limit=limit)


def list_overdue_invoices(factory: RepositoryFactory) -> list[Invoice]:
    return factory.create_invoice_repository().get_overdue()


def invoice_summary(factory: RepositoryFactory) -> InvoiceSummary:
    try:
        return factory.create_invoice_repository().get_summary()
    except MixedCurrencyError as e:
        raise SummaryUnavailableError(str(e)) from e


def due_date_for_terms(terms: str, issue_date: date) -> date:
    """Due date for "Net N" or "Due on Receipt" style terms."""
    normalized = " ".join(terms.lower().split())
    if normalized in _IMMEDIATE_TERMS:
        return issue_date
    match = _NET_TERMS.fullmatch(normalized)
    if match is None:
        raise PaymentTermsError(terms)
    return issue_date + timedelta(days=int(match[1]))


def parse_amount(value: str, currency: str) -> Money:
    """A positive money amount from user input."""
    try:
        amount = Money(value, currency)
    except ValueError as e:
        raise InvalidAmountError(value) from e
    if amount.amount <= 0:
        raise InvalidAmountError(value)
    return amount


def _logo_uri(path: str | None) -> str | None:
    try:
        return file_to_base64_data_uri(path)
    except FileNotFoundError as e:
        raise LogoNotFoundError(str(path)) from e


def _country_code(company: Company) -> str | None:
    country = (company.country or "").strip()
    return country.upper() if len(country) == 2 and country.isalpha() else None


def resolve_company_details(
    factory: RepositoryFactory, invoice: Invoice, overrides: CompanyOverrides
) -> ResolvedCompany:
    """Resolve company details from overrides, then invoice snapshots, then the company record."""
    record = factory.create_company_repository().get_by_id(invoice.company_id)
    name = overrides.name or invoice.company_name_snapshot or (record.name if record else None)
    address = (
        overrides.address
        or invoice.company_address_snapshot
        or (record.address if record else None)
    )
    if not name or not address:
        raise CompanyDetailsUnresolvedError()

    details: dict[str, Any] = {
        "name": name,
        "address": address,
        "tax_id": overrides.tax_id
        or invoice.company_tax_id_snapshot
        or (record.tax_id if record else None),
        "email": overrides.email or (record.email if record else None),
        "city": record.city if record else None,
        "postal_code": record.postal_code if record else None,
        "country_code": _country_code(record) if record else None,
    }
    logo_path = overrides.logo_path or (record.logo_path if record else None)
    return ResolvedCompany(details=details, logo=_logo_uri(logo_path))


def _document_template(
    factory: RepositoryFactory, invoice: Invoice, template: str | None
) -> str | None:
    """Pick the explicit template, then the invoice's, then the client's preferred one."""
    chosen = template or invoice.template_name
    if not chosen:
        client = factory.create_client_repository().get_by_id(invoice.client_id)
        if client and client.preferred_template:
            chosen = client.preferred_template
    return chosen


def _stored_payment_notes(factory: RepositoryFactory, invoice: Invoice) -> list[Any]:
    repo = factory.create_payment_note_repository()
    notes = []
    for note_id in invoice.payment_note_ids:
        note = repo.get_by_id(note_id)
        if note is None:
            raise PaymentNoteNotFoundError(note_id)
        notes.append(note)
    return notes


def _render_context(
    factory: RepositoryFactory, invoice: Invoice, company: CompanyOverrides
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(company details, extra template context) for rendering a stored invoice."""
    resolved = resolve_company_details(factory, invoice, company)
    context: dict[str, Any] = {"logo": resolved.logo}
    payment_notes = _stored_payment_notes(factory, invoice)
    if payment_notes:
        context["payment_notes"] = payment_notes
    return resolved.details, context


def render_invoice_html(factory: RepositoryFactory, invoice: Invoice) -> str:
    """HTML for a stored invoice, rendered exactly as the CLI renders it."""
    details, context = _render_context(factory, invoice, CompanyOverrides())
    return HTMLService(template_dir=template_dir()).generate_html(
        invoice=invoice,
        company=details,
        template_name=_document_template(factory, invoice, None),
        **context,
    )


def render_invoice_pdf(factory: RepositoryFactory, invoice: Invoice) -> bytes:
    """PDF bytes for a stored invoice, rendered exactly as the CLI renders it."""
    details, context = _render_context(factory, invoice, CompanyOverrides())
    try:
        return PDFService(template_dir=template_dir()).generate_pdf_bytes(
            invoice=invoice,
            company=details,
            template_name=_document_template(factory, invoice, None),
            **context,
        )
    except ImportError as e:
        raise _pdf_unavailable(e) from e


def render_invoice_document(
    factory: RepositoryFactory,
    identifier: str,
    kind: DocumentKind,
    output_dir: str,
    company: CompanyOverrides,
    template: str | None,
) -> RenderedDocument:
    """Render a stored invoice to a PDF or HTML file in output_dir."""
    invoice = find_invoice(factory, identifier)
    details, context = _render_context(factory, invoice, company)
    template_name = _document_template(factory, invoice, template)

    if kind is DocumentKind.HTML:
        path = HTMLService(template_dir=template_dir(), output_dir=output_dir).save_html(
            invoice=invoice, company=details, template_name=template_name, **context
        )
        return RenderedDocument(invoice=invoice, path=path)

    try:
        path = PDFService(template_dir=template_dir(), output_dir=output_dir).generate_pdf(
            invoice=invoice, company=details, template_name=template_name, **context
        )
    except ImportError as e:
        raise _pdf_unavailable(e) from e
    return RenderedDocument(invoice=invoice, path=path)


def _resolve_client(factory: RepositoryFactory, request: NewInvoice) -> tuple[Client, bool]:
    """Return the invoice's client and whether it was created for this invoice."""
    repo = factory.create_client_repository()
    if request.client_id:
        client = repo.get_by_id(request.client_id)
        if client is None:
            raise ClientNotFoundError(str(request.client_id), by_id=True)
        return client, False
    if not request.client_name:
        raise ClientNotSpecifiedError()

    wanted = request.client_name.lower()
    existing = next((c for c in iter_all(repo) if c.name.lower() == wanted), None)
    if existing is not None:
        return existing, False
    created = repo.create(
        ClientCreate(
            name=request.client_name,
            address=request.client_address,
            tax_id=request.client_tax_id,
            email=request.client_email,
            phone=request.client_phone,
            preferred_template=None,
        )
    )
    return created, True


def _issuing_company(factory: RepositoryFactory) -> Company | None:
    """The default company, falling back to company #1 (the schema's default company_id)."""
    repo = factory.create_company_repository()
    return repo.get_default() or repo.get_by_id(1)


def create_invoice(factory: RepositoryFactory, request: NewInvoice) -> CreatedInvoice:
    """Create a single-line invoice, creating the client by name if it does not exist.

    Company details are snapshotted from the overrides and the issuing company, so the
    invoice keeps showing them even if the company record changes later.
    """
    if request.amount.amount <= 0:
        raise InvalidAmountError(str(request.amount.amount))
    if request.invoice_number and not is_safe_file_name(request.invoice_number):
        raise InvalidInvoiceNumberError(request.invoice_number)
    invoice_repo = factory.create_invoice_repository()
    if request.invoice_number and invoice_repo.get_by_number(request.invoice_number):
        raise DuplicateInvoiceNumberError(request.invoice_number)

    issue_date = date.today()
    due_date = request.due_date or due_date_for_terms(request.payment_terms, issue_date)
    client, client_created = _resolve_client(factory, request)
    company = _issuing_company(factory)
    number = request.invoice_number or NumberingService(invoice_repo=invoice_repo).generate_number()

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=number,
            issue_date=issue_date,
            status=InvoiceStatus.UNPAID,
            due_date=due_date,
            payment_terms=request.payment_terms,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=str(client.tax_id) if client.tax_id else None,
            company_id=company.id if company else 1,
            company_name_snapshot=request.company.name or (company.name if company else None),
            company_address_snapshot=request.company.address
            or (company.address if company else None),
            company_tax_id_snapshot=request.company.tax_id or (company.tax_id if company else None),
            template_name=request.template or client.preferred_template,
            lines=[
                InvoiceLineCreate(
                    description=request.description, quantity=1, unit_price=request.amount
                )
            ],
        )
    )
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_created(invoice)
    return CreatedInvoice(invoice=invoice, created_client=client if client_created else None)


def clone_invoice(factory: RepositoryFactory, identifier: str, issue_date: date) -> ClonedInvoice:
    """Copy an invoice under the next number, keeping its payment period, and audit it."""
    original = find_invoice(factory, identifier)
    if original.type is not InvoiceType.STANDARD:
        raise InvoiceNotFoundError(identifier)
    invoice_repo = factory.create_invoice_repository()
    number = NumberingService(invoice_repo=invoice_repo).generate_number(year=issue_date.year)

    if original.due_date:
        due_date = issue_date + (original.due_date - original.issue_date)
    else:
        due_date = due_date_for_terms(original.payment_terms, issue_date)

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=number,
            issue_date=issue_date,
            status=InvoiceStatus.UNPAID,
            due_date=due_date,
            payment_terms=original.payment_terms,
            client_id=original.client_id,
            client_name_snapshot=original.client_name_snapshot,
            client_address_snapshot=original.client_address_snapshot,
            client_tax_id_snapshot=original.client_tax_id_snapshot,
            company_id=original.company_id,
            company_name_snapshot=original.company_name_snapshot,
            company_address_snapshot=original.company_address_snapshot,
            company_tax_id_snapshot=original.company_tax_id_snapshot,
            payment_note_ids=original.payment_note_ids,
            template_name=_document_template(factory, original, None),
            lines=[
                InvoiceLineCreate(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    tax_rate=line.tax_rate,
                )
                for line in original.lines
            ],
            original_invoice_id=None,
            reason=None,
        )
    )

    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_cloned(
        invoice_id=invoice.id,
        invoice_number=invoice.number,
        original_number=original.number,
        total_amount=invoice.total_amount,
    )
    return ClonedInvoice(original=original, invoice=invoice)


def validate_export_formats(formats: list[str]) -> list[str]:
    """Normalize requested formats, rejecting unknown ones before anything is created."""
    normalized = [f.lower() for f in formats]
    unknown = [f for f in normalized if f not in EXPORT_FORMATS]
    if unknown:
        raise UnknownExportFormatError(unknown, list(EXPORT_FORMATS))
    return normalized


def _pdf_unavailable(error: ImportError) -> OperationError:
    """Map a WeasyPrint import failure to a missing package or missing system libraries."""
    if isinstance(error, PdfSystemLibrariesError):
        return MissingSystemLibrariesError(
            "pdf", error.library, error.steps, error.found_in, str(error)
        )
    return MissingDependencyError("pdf", str(error))


def _require_pdf_support(formats: list[str]) -> None:
    if "pdf" in formats:
        try:
            PDFService._get_weasyprint_modules()
        except ImportError as e:
            raise _pdf_unavailable(e) from e


def check_new_invoice_export(
    factory: RepositoryFactory, formats: list[str], company: CompanyOverrides
) -> list[str]:
    """Check everything export_invoice needs before a new invoice is saved.

    Returns the normalized formats.
    """
    formats = validate_export_formats(formats)
    if RENDERED_FORMATS.intersection(formats):
        issuing = _issuing_company(factory)
        if not (company.name or (issuing and issuing.name)) or not (
            company.address or (issuing and issuing.address)
        ):
            raise CompanyDetailsUnresolvedError()
        _logo_uri(company.logo_path or (issuing.logo_path if issuing else None))
    _require_pdf_support(formats)
    return formats


def check_invoice_export(
    factory: RepositoryFactory, invoice: Invoice, formats: list[str], company: CompanyOverrides
) -> list[str]:
    """Check everything export_invoice needs for a copy of `invoice` before it is saved.

    Returns the normalized formats.
    """
    formats = validate_export_formats(formats)
    if RENDERED_FORMATS.intersection(formats):
        resolve_company_details(factory, invoice, company)
    _require_pdf_support(formats)
    return formats


def export_payment_notes(
    payment_terms: str | None, bank_account: str | None
) -> list[dict[str, str]]:
    notes = []
    if payment_terms:
        notes.append({"title": "Payment Terms", "content": payment_terms})
    if bank_account:
        notes.append({"title": "Bank Account", "content": bank_account})
    return notes


def export_invoice(
    factory: RepositoryFactory,
    invoice: Invoice,
    formats: list[str],
    output_dir: str,
    company: CompanyOverrides,
    payment_notes: list[dict[str, str]],
) -> list[ExportOutcome]:
    """Write the invoice in each requested format, one outcome per format in order.

    Raises:
        UnknownExportFormatError: For a format outside EXPORT_FORMATS
        MissingDependencyError: If PDF output is requested without the pdf extra
    """
    formats = validate_export_formats(formats)
    template_name = _document_template(factory, invoice, None)
    resolved = (
        resolve_company_details(factory, invoice, company)
        if RENDERED_FORMATS.intersection(formats)
        else None
    )

    outcomes = []
    for fmt in formats:
        if fmt == "json":
            path = output_path(output_dir, f"{invoice.number}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(invoice.model_dump_json(indent=2))
            outcomes.append(ExportOutcome(fmt, path))
            continue

        if resolved is None:
            raise CompanyDetailsUnresolvedError()
        if fmt == "pdf":
            try:
                path = PDFService(template_dir=template_dir(), output_dir=output_dir).generate_pdf(
                    invoice=invoice,
                    company=resolved.details,
                    template_name=template_name,
                    logo=resolved.logo,
                    payment_notes=payment_notes,
                )
            except ImportError as e:
                raise _pdf_unavailable(e) from e
        elif fmt == "html":
            path = HTMLService(template_dir=template_dir(), output_dir=output_dir).save_html(
                invoice=invoice,
                company=resolved.details,
                template_name=template_name,
                logo=resolved.logo,
                payment_notes=payment_notes,
            )
        else:
            path = UBLService(template_dir=template_dir(), output_dir=output_dir).save_ubl(
                invoice=invoice, company=resolved.details
            )
        outcomes.append(ExportOutcome(fmt, path))
    return outcomes
