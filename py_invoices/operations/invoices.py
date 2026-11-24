"""Invoice operations: return domain objects, raise OperationError, never print."""

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic_invoices.schemas import (
    Client,
    ClientCreate,
    Invoice,
    InvoiceCreate,
    InvoiceLine,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceSummary,
    InvoiceType,
)
from pydantic_invoices.schemas.company import Company
from pydantic_invoices.schemas.payment_note import PaymentNote, PaymentNoteSnapshot
from pydantic_invoices.vo import CountryCode, Money

from py_invoices.config import InvoiceSettings, get_settings
from py_invoices.core import AuditService, HTMLService, NumberingService, PDFService, UBLService
from py_invoices.core.audit_service import AuditEntity
from py_invoices.core.html_service import PACKAGE_TEMPLATES_DIR, is_safe_file_name, output_path
from py_invoices.core.lifecycle import DRAFT_NUMBER_PREFIX, content_hash, draft_number, is_draft
from py_invoices.core.numbering_service import (
    CREDIT_NOTE_NUMBER_FORMAT,
    INVOICE_NUMBER_FORMAT,
    NumberTakenError,
    series_format,
)
from py_invoices.core.paging import iter_all
from py_invoices.core.pdf_service import PdfSystemLibrariesError
from py_invoices.core.summary import MixedCurrencyError
from py_invoices.operations.errors import (
    ClientNotFoundError,
    ClientNotSpecifiedError,
    CompanyDetailsUnresolvedError,
    CompanyInactiveError,
    CompanyNotFoundError,
    DuplicateInvoiceNumberError,
    InvalidAmountError,
    InvalidDueDateError,
    InvalidInvoiceNumberError,
    InvoiceNotDraftError,
    InvoiceNotFoundError,
    LineSelectionError,
    LogoNotFoundError,
    MissingDependencyError,
    MissingSystemLibrariesError,
    OperationError,
    OutputExistsError,
    PaymentNoteMissingError,
    PaymentNoteNotFoundError,
    PaymentNoteUnusableError,
    PaymentTermsError,
    SeriesNumberTakenError,
    SummaryUnavailableError,
    UnknownExportFormatError,
)
from py_invoices.plugins.factory import RepositoryFactory
from py_invoices.utils.image import PASSTHROUGH_SCHEMES, file_to_base64_data_uri

logger = logging.getLogger(__name__)

RENDERED_FORMATS = frozenset({"pdf", "html", "ubl"})
EXPORT_FORMATS = ("pdf", "html", "ubl", "json")
FILE_EXTENSIONS = {"pdf": "pdf", "html": "html", "ubl": "xml", "json": "json"}
DEFAULT_PAYMENT_TERMS = "Net 30"

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


class DocumentKind(StrEnum):
    PDF = "pdf"
    HTML = "html"


@dataclass(frozen=True, slots=True)
class RenderedDocument:
    invoice: Invoice
    path: str
    overwritten: bool


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
    client_city: str | None = None
    client_postal_code: str | None = None
    client_country: CountryCode | None = None
    invoice_number: str | None = None
    payment_terms: str = DEFAULT_PAYMENT_TERMS
    due_date: date | None = None
    company: CompanyOverrides = CompanyOverrides()
    template: str | None = None
    company_id: int | None = None
    """The issuing company; default the default company, then company #1."""
    payment_note_ids: tuple[int, ...] = ()
    """Stored payment notes to print; with no notes and no bank account, the default note."""
    bank_account: str | None = None
    """Stored as a "Bank Account" payment note, printed on every rendering of the invoice."""
    issue: bool = False
    """Issue at once instead of leaving a draft."""


@dataclass(frozen=True, slots=True)
class LineChange:
    """New values for one line of a draft; unset fields keep the line's own."""

    description: str | None = None
    quantity: int | None = None
    unit_price: Decimal | None = None
    """In the line's currency"""

    def is_empty(self) -> bool:
        return (self.description, self.quantity, self.unit_price) == (None, None, None)


NO_LINE_CHANGE = LineChange()


@dataclass(frozen=True, slots=True)
class DraftChanges:
    """Edits to a draft: one line (`line`, required when it has several) and its dates."""

    line_change: LineChange = NO_LINE_CHANGE
    line: int | None = None
    issue_date: date | None = None
    due_date: date | None = None
    payment_terms: str | None = None


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
    overwritten: bool


def package_template_dir() -> str:
    return PACKAGE_TEMPLATES_DIR


@dataclass(frozen=True, slots=True)
class RenderPaths:
    """Where rendering finds templates, and what a stored relative path is relative to.

    A company's logo_path is stored as given, so "./data/assets/logo.png" resolves against
    `base`, the run's working directory (the CLI's --cwd), not the process's.
    """

    template_dir: str
    base: Path

    @classmethod
    def of(cls, settings: InvoiceSettings, base: Path) -> RenderPaths:
        """The configured template directory, else the bundled templates."""
        return cls(settings.template_dir or PACKAGE_TEMPLATES_DIR, base)

    @classmethod
    def current(cls) -> RenderPaths:
        """Paths of the process: the environment's settings and working directory."""
        return cls.of(get_settings(), Path.cwd())

    def logo_uri(self, path: str | None) -> str | None:
        """The logo as a data URI; a relative local path is read under `base`.

        Raises:
            LogoNotFoundError: If a local path does not point to a file
        """
        if path and not path.startswith(PASSTHROUGH_SCHEMES):
            path = str(self.base / path)
        try:
            return file_to_base64_data_uri(path)
        except FileNotFoundError as e:
            raise LogoNotFoundError(str(path)) from e


def find_invoice(factory: RepositoryFactory, identifier: str) -> Invoice:
    """Find an invoice by number first, then, for all-digit identifiers, by ID."""
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_number(identifier)
    if invoice is None and identifier.isdigit():
        invoice = repo.get_by_id(int(identifier))
    if invoice is None:
        raise InvoiceNotFoundError(identifier)
    return invoice


def list_invoices(factory: RepositoryFactory) -> list[Invoice]:
    """Every invoice, newest first: by issue date, then by ID."""
    return sorted(
        iter_all(factory.create_invoice_repository()),
        key=lambda invoice: (invoice.issue_date, invoice.id),
        reverse=True,
    )


def list_overdue_invoices(factory: RepositoryFactory) -> list[Invoice]:
    """Issued invoices past their due date; a draft is owed nothing yet."""
    return [i for i in factory.create_invoice_repository().get_overdue() if not is_draft(i)]


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


def _country_code(company: Company) -> str | None:
    country = (company.country or "").strip()
    return country.upper() if len(country) == 2 and country.isalpha() else None


def resolve_company_details(
    factory: RepositoryFactory, invoice: Invoice, overrides: CompanyOverrides, paths: RenderPaths
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
        or (str(record.tax_id) if record and record.tax_id else None),
        "email": overrides.email or (record.email if record else None),
        "registration_number": record.registration_number if record else None,
        "city": record.city if record else None,
        "postal_code": record.postal_code if record else None,
        "country_code": _country_code(record) if record else None,
    }
    logo_path = overrides.logo_path or (record.logo_path if record else None)
    return ResolvedCompany(details=details, logo=paths.logo_uri(logo_path))


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


def _snapshot_payment_notes(
    factory: RepositoryFactory, note_ids: list[int]
) -> list[PaymentNoteSnapshot]:
    """The current text of the payment notes, frozen for a new invoice."""
    repo = factory.create_payment_note_repository()
    snapshots = []
    for note_id in note_ids:
        note = repo.get_by_id(note_id)
        if note is None:
            raise PaymentNoteNotFoundError(note_id)
        snapshots.append(PaymentNoteSnapshot(title=note.title, content=note.content))
    return snapshots


def _stored_payment_notes(
    factory: RepositoryFactory, invoice: Invoice
) -> list[PaymentNoteSnapshot]:
    """The payment notes as issued; a live lookup only for invoices stored before snapshots."""
    if invoice.payment_notes_snapshot is not None:
        return invoice.payment_notes_snapshot
    if invoice.payment_note_ids:
        logger.warning(
            "Invoice %s has no payment notes snapshot; rendering the current payment notes %s",
            invoice.number,
            invoice.payment_note_ids,
        )
    return _snapshot_payment_notes(factory, invoice.payment_note_ids)


def _render_context(
    factory: RepositoryFactory, invoice: Invoice, company: CompanyOverrides, paths: RenderPaths
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(company details, extra template context) for rendering a stored invoice."""
    resolved = resolve_company_details(factory, invoice, company, paths)
    context: dict[str, Any] = {"logo": resolved.logo}
    payment_notes = printed_payment_notes(factory, invoice)
    if payment_notes:
        context["payment_notes"] = payment_notes
    if invoice.original_invoice_id is not None:
        context["original_invoice_number"] = _invoice_number(factory, invoice.original_invoice_id)
    return resolved.details, context


def _invoice_number(factory: RepositoryFactory, invoice_id: int) -> str:
    """The number of a stored invoice, such as the one a credit note credits."""
    invoice = factory.create_invoice_repository().get_by_id(invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError(str(invoice_id))
    return invoice.number


def render_invoice_html(factory: RepositoryFactory, invoice: Invoice) -> str:
    """HTML for a stored invoice, rendered exactly as the CLI renders it."""
    paths = RenderPaths.current()
    details, context = _render_context(factory, invoice, CompanyOverrides(), paths)
    return HTMLService(template_dir=paths.template_dir).generate_html(
        invoice=invoice,
        company=details,
        template_name=_document_template(factory, invoice, None),
        **context,
    )


def render_invoice_pdf(factory: RepositoryFactory, invoice: Invoice) -> bytes:
    """PDF bytes for a stored invoice, rendered exactly as the CLI renders it."""
    paths = RenderPaths.current()
    details, context = _render_context(factory, invoice, CompanyOverrides(), paths)
    try:
        return PDFService(template_dir=paths.template_dir).generate_pdf_bytes(
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
    paths: RenderPaths,
    *,
    overwrite: bool,
) -> RenderedDocument:
    """Render a stored invoice to a PDF or HTML file in output_dir.

    Raises:
        OutputExistsError: If the file exists and `overwrite` is false
    """
    invoice = find_invoice(factory, identifier)
    target = _OutputTarget.of(output_dir, invoice, kind.value, overwrite=overwrite)
    details, context = _render_context(factory, invoice, company, paths)
    template_name = _document_template(factory, invoice, template)

    if kind is DocumentKind.HTML:
        path = HTMLService(template_dir=paths.template_dir, output_dir=output_dir).save_html(
            invoice=invoice,
            company=details,
            output_filename=target.filename,
            template_name=template_name,
            **context,
        )
        return RenderedDocument(invoice=invoice, path=path, overwritten=target.exists)

    try:
        path = PDFService(template_dir=paths.template_dir, output_dir=output_dir).generate_pdf(
            invoice=invoice,
            company=details,
            output_filename=target.filename,
            template_name=template_name,
            **context,
        )
    except ImportError as e:
        raise _pdf_unavailable(e) from e
    return RenderedDocument(invoice=invoice, path=path, overwritten=target.exists)


@dataclass(frozen=True, slots=True)
class _OutputTarget:
    """The file a format of an invoice is written to, and whether it is there already."""

    filename: str
    exists: bool

    @classmethod
    def of(cls, output_dir: str, invoice: Invoice, fmt: str, *, overwrite: bool) -> _OutputTarget:
        """Raises OutputExistsError if the file exists and `overwrite` is false.

        A rendered file of an issued invoice may be the copy sent to the client, so it is
        replaced only on request.
        """
        filename = f"{invoice.number}.{FILE_EXTENSIONS[fmt]}"
        path = output_path(output_dir, filename)
        exists = os.path.lexists(path)
        if exists and not overwrite:
            raise OutputExistsError(path)
        return cls(filename, exists)


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
            city=request.client_city,
            postal_code=request.client_postal_code,
            country=request.client_country,
            preferred_template=None,
        )
    )
    AuditService(audit_repo=factory.create_audit_repository()).log_record_event(
        AuditEntity.CLIENT, created.id, "CREATED", new_value=created.name
    )
    return created, True


def _issuing_company(factory: RepositoryFactory, company_id: int | None) -> Company | None:
    """The chosen company, else the default one, falling back to company #1.

    Raises:
        CompanyNotFoundError: If the chosen company does not exist
        CompanyInactiveError: If the chosen company is inactive
    """
    repo = factory.create_company_repository()
    if company_id is None:
        return repo.get_default() or repo.get_by_id(1)
    company = repo.get_by_id(company_id)
    if company is None:
        raise CompanyNotFoundError(company_id)
    if not company.is_active:
        raise CompanyInactiveError(company_id)
    return company


def _chosen_payment_notes(
    factory: RepositoryFactory, note_ids: tuple[int, ...], company_id: int
) -> list[PaymentNote]:
    """The notes picked for a new invoice: each must exist, be active and be the
    issuing company's or global.

    Raises:
        PaymentNoteMissingError: If a note does not exist
        PaymentNoteUnusableError: If a note is inactive or another company's
    """
    repo = factory.create_payment_note_repository()
    notes = []
    for note_id in note_ids:
        note = repo.get_by_id(note_id)
        if note is None:
            raise PaymentNoteMissingError(note_id)
        if not note.is_active:
            raise PaymentNoteUnusableError(note_id, "it is inactive")
        if note.company_id is not None and note.company_id != company_id:
            raise PaymentNoteUnusableError(
                note_id, f"it belongs to company {note.company_id}, not company {company_id}"
            )
        notes.append(note)
    return notes


def _default_payment_note(factory: RepositoryFactory, company_id: int) -> PaymentNote | None:
    """The issuing company's default note, else the global default (no company)."""
    repo = factory.create_payment_note_repository()
    own = repo.get_default(company_id)
    if own is not None:
        return own
    return next(
        (n for n in repo.get_active() if n.is_default and n.company_id is None),
        None,
    )


def _new_invoice_notes(
    factory: RepositoryFactory, request: NewInvoice, company_id: int
) -> tuple[list[int], list[PaymentNoteSnapshot]]:
    """(payment_note_ids, payment_notes_snapshot) of a new invoice.

    The chosen notes come first, then the typed bank account; with neither, the default note.
    """
    if request.payment_note_ids:
        notes = _chosen_payment_notes(factory, request.payment_note_ids, company_id)
    elif request.bank_account is None:
        default = _default_payment_note(factory, company_id)
        notes = [default] if default is not None else []
    else:
        notes = []
    snapshot = [PaymentNoteSnapshot(title=n.title, content=n.content) for n in notes]
    if request.bank_account:
        snapshot.append(PaymentNoteSnapshot(title="Bank Account", content=request.bank_account))
    return [n.id for n in notes], snapshot


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
    company = _issuing_company(factory, request.company_id)
    company_id = company.id if company else 1
    note_ids, notes_snapshot = _new_invoice_notes(factory, request, company_id)
    client, client_created = _resolve_client(factory, request)
    number = request.invoice_number or _pending_draft_number()

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=number,
            issue_date=issue_date,
            status=InvoiceStatus.DRAFT,
            due_date=due_date,
            payment_terms=request.payment_terms,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=str(client.tax_id) if client.tax_id else None,
            client_city_snapshot=client.city,
            client_postal_code_snapshot=client.postal_code,
            client_country_snapshot=client.country,
            company_id=company_id,
            company_name_snapshot=request.company.name or (company.name if company else None),
            company_address_snapshot=request.company.address
            or (company.address if company else None),
            company_tax_id_snapshot=request.company.tax_id
            or (str(company.tax_id) if company and company.tax_id else None),
            template_name=request.template or client.preferred_template,
            payment_note_ids=note_ids,
            payment_notes_snapshot=notes_snapshot,
            lines=[
                InvoiceLineCreate(
                    description=request.description, quantity=1, unit_price=request.amount
                )
            ],
        )
    )
    invoice = _number_draft(factory, invoice)
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_created(invoice)
    if request.issue:
        invoice = issue_invoice(factory, invoice.number)
    return CreatedInvoice(invoice=invoice, created_client=client if client_created else None)


def clone_invoice(
    factory: RepositoryFactory,
    identifier: str,
    issue_date: date,
    line_change: LineChange = NO_LINE_CHANGE,
    due_date: date | None = None,
    issue: bool = False,
) -> ClonedInvoice:
    """Copy an invoice as a draft, keeping its payment period, and audit it.

    `line_change` edits the copy's line; an original with several lines is edited
    after cloning with update_invoice instead. With `issue`, the copy is issued at once.

    Raises:
        LineSelectionError: For a line change on an original with several lines
    """
    original = find_invoice(factory, identifier)
    if original.type is not InvoiceType.STANDARD:
        raise InvoiceNotFoundError(identifier)
    if not line_change.is_empty() and len(original.lines) != 1:
        raise LineSelectionError(original.number, len(original.lines), None)
    invoice_repo = factory.create_invoice_repository()

    if due_date is None:
        if original.due_date:
            due_date = issue_date + (original.due_date - original.issue_date)
        else:
            due_date = due_date_for_terms(original.payment_terms, issue_date)
    lines = [
        InvoiceLineCreate(
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
        )
        for line in original.lines
    ]
    if not line_change.is_empty():
        lines = [_changed_line(lines[0], line_change)]

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=_pending_draft_number(),
            issue_date=issue_date,
            status=InvoiceStatus.DRAFT,
            due_date=due_date,
            payment_terms=original.payment_terms,
            client_id=original.client_id,
            client_name_snapshot=original.client_name_snapshot,
            client_address_snapshot=original.client_address_snapshot,
            client_tax_id_snapshot=original.client_tax_id_snapshot,
            client_city_snapshot=original.client_city_snapshot,
            client_postal_code_snapshot=original.client_postal_code_snapshot,
            client_country_snapshot=original.client_country_snapshot,
            company_id=original.company_id,
            company_name_snapshot=original.company_name_snapshot,
            company_address_snapshot=original.company_address_snapshot,
            company_tax_id_snapshot=original.company_tax_id_snapshot,
            payment_note_ids=original.payment_note_ids,
            payment_notes_snapshot=_snapshot_payment_notes(factory, original.payment_note_ids),
            template_name=_document_template(factory, original, None),
            lines=lines,
            original_invoice_id=None,
            reason=None,
        )
    )

    invoice = _number_draft(factory, invoice)
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_cloned(
        invoice_id=invoice.id,
        invoice_number=invoice.number,
        original_number=original.number,
        total_amount=invoice.total_amount,
    )
    if issue:
        invoice = issue_invoice(factory, invoice.number)
    return ClonedInvoice(original=original, invoice=invoice)


def _pending_draft_number() -> str:
    """A unique placeholder until the draft has an ID to be numbered by."""
    return f"{DRAFT_NUMBER_PREFIX}new-{uuid.uuid4().hex}"


def _number_draft(factory: RepositoryFactory, invoice: Invoice) -> Invoice:
    """Give a new draft its provisional number DRAFT-<id> (custom numbers are kept)."""
    if not invoice.number.startswith(f"{DRAFT_NUMBER_PREFIX}new-"):
        return invoice
    return factory.create_invoice_repository().update(
        invoice.model_copy(update={"number": draft_number(invoice.id)})
    )


def _changed_line[L: (InvoiceLine, InvoiceLineCreate)](line: L, change: LineChange) -> L:
    if change.unit_price is not None and change.unit_price <= 0:
        raise InvalidAmountError(str(change.unit_price))
    updates: dict[str, Any] = {}
    if change.description is not None:
        updates["description"] = change.description
    if change.quantity is not None:
        updates["quantity"] = change.quantity
    if change.unit_price is not None:
        current = line.unit_price
        if not isinstance(current, Money):
            raise TypeError(f"Line unit price {current!r} is not Money")
        updates["unit_price"] = Money(change.unit_price, current.currency)
    # model_copy keeps Money intact; a model_dump round trip would drop the currency
    return line.model_copy(update=updates)


def _check_dates(number: str, issue_date: date, due_date: date | None) -> None:
    if due_date is not None and due_date < issue_date:
        raise InvalidDueDateError(number, issue_date, due_date)


def _require_draft(invoice: Invoice) -> None:
    if not is_draft(invoice):
        raise InvoiceNotDraftError(invoice.number, invoice.status.value)


def update_invoice(factory: RepositoryFactory, identifier: str, changes: DraftChanges) -> Invoice:
    """Edit a draft: one of its lines, its dates or its payment terms.

    Raises:
        InvoiceNotDraftError: If the invoice is issued
        LineSelectionError: If the line is missing or ambiguous
    """
    draft = find_invoice(factory, identifier)
    _require_draft(draft)
    updates: dict[str, Any] = {}
    if not changes.line_change.is_empty():
        index = changes.line
        if index is None and len(draft.lines) == 1:
            index = 0
        if index is None or not 0 <= index < len(draft.lines):
            raise LineSelectionError(draft.number, len(draft.lines), changes.line)
        lines = list(draft.lines)
        lines[index] = _changed_line(lines[index], changes.line_change)
        updates["lines"] = lines
    if changes.issue_date is not None:
        updates["issue_date"] = changes.issue_date
    if changes.due_date is not None:
        updates["due_date"] = changes.due_date
    if changes.payment_terms is not None:
        updates["payment_terms"] = changes.payment_terms
    updated = draft.model_copy(update=updates)
    _check_dates(draft.number, updated.issue_date, updated.due_date)
    saved = factory.create_invoice_repository().update(updated)
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_updated(
        saved, sorted(updates)
    )
    return saved


def _next_number(factory: RepositoryFactory, draft: Invoice, year: int) -> str:
    """The next number of the issuing company's series for the draft's document type."""
    base = (
        CREDIT_NOTE_NUMBER_FORMAT
        if draft.type is InvoiceType.CREDIT_NOTE
        else INVOICE_NUMBER_FORMAT
    )
    # Invoices of a company that is not stored (company_id 1 without companies) keep
    # the unprefixed series
    company = factory.create_company_repository().get_by_id(draft.company_id)
    numbering = NumberingService(
        series_format(base, company.number_prefix if company else None),
        invoice_repo=factory.create_invoice_repository(),
    )
    try:
        return numbering.generate_number(year=year, company_id=draft.company_id)
    except NumberTakenError as e:
        raise SeriesNumberTakenError(str(e), e.number, e.company_id) from e


def issue_invoice(
    factory: RepositoryFactory, identifier: str, issue_date: date | None = None
) -> Invoice:
    """Issue a draft: give it its final number, lock its content with a hash, mark it SENT.

    A draft numbered DRAFT-<id> gets the next number of its series for the issue year,
    so numbers follow the order of issue without gaps. `issue_date` replaces the draft's
    date and moves the due date with it.

    Raises:
        InvoiceNotDraftError: If the invoice is already issued
    """
    draft = find_invoice(factory, identifier)
    _require_draft(draft)
    repo = factory.create_invoice_repository()
    issue_date = issue_date or draft.issue_date
    due_date = draft.due_date
    if due_date is not None and issue_date != draft.issue_date:
        due_date = issue_date + (due_date - draft.issue_date)
    number = draft.number
    if number.startswith(DRAFT_NUMBER_PREFIX):
        number = _next_number(factory, draft, issue_date.year)
    _check_dates(draft.number, issue_date, due_date)
    notes = draft.payment_notes_snapshot
    if notes is None:  # a draft stored without one, such as through the API
        notes = _snapshot_payment_notes(factory, draft.payment_note_ids)
    issued = draft.model_copy(
        update={
            "number": number,
            "issue_date": issue_date,
            "due_date": due_date,
            "status": InvoiceStatus.SENT,
            "payment_notes_snapshot": notes,
        }
    )
    saved = repo.update(issued.model_copy(update={"content_hash": content_hash(issued)}))
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_issued(
        saved, draft.number
    )
    return saved


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
    factory: RepositoryFactory,
    formats: list[str],
    company: CompanyOverrides,
    paths: RenderPaths,
    *,
    company_id: int | None,
) -> list[str]:
    """Check everything export_invoice needs before a new invoice is saved.

    `company_id` is the issuing company chosen for the invoice, if any.
    Returns the normalized formats.
    """
    formats = validate_export_formats(formats)
    if RENDERED_FORMATS.intersection(formats):
        issuing = _issuing_company(factory, company_id)
        if not (company.name or (issuing and issuing.name)) or not (
            company.address or (issuing and issuing.address)
        ):
            raise CompanyDetailsUnresolvedError()
        paths.logo_uri(company.logo_path or (issuing.logo_path if issuing else None))
    _require_pdf_support(formats)
    return formats


def check_invoice_export(
    factory: RepositoryFactory,
    invoice: Invoice,
    formats: list[str],
    company: CompanyOverrides,
    paths: RenderPaths,
) -> list[str]:
    """Check everything export_invoice needs for a copy of `invoice` before it is saved.

    Returns the normalized formats.
    """
    formats = validate_export_formats(formats)
    if RENDERED_FORMATS.intersection(formats):
        resolve_company_details(factory, invoice, company, paths)
    _require_pdf_support(formats)
    return formats


def printed_payment_notes(factory: RepositoryFactory, invoice: Invoice) -> list[dict[str, str]]:
    """The payment notes every rendering of the invoice prints, exported or rendered later.

    A standard invoice's payment terms come first, read from `payment_terms` so a draft's
    edited terms show; then the notes stored on the invoice.
    """
    notes = []
    if invoice.type is InvoiceType.STANDARD and invoice.payment_terms:
        notes.append({"title": "Payment Terms", "content": invoice.payment_terms})
    notes.extend(note.model_dump() for note in _stored_payment_notes(factory, invoice))
    return notes


def export_invoice(
    factory: RepositoryFactory,
    invoice: Invoice,
    formats: list[str],
    output_dir: str,
    company: CompanyOverrides,
    payment_notes: list[dict[str, str]],
    paths: RenderPaths,
    *,
    overwrite: bool,
) -> list[ExportOutcome]:
    """Write the invoice in each requested format, one outcome per format in order.

    Raises:
        UnknownExportFormatError: For a format outside EXPORT_FORMATS
        MissingDependencyError: If PDF output is requested without the pdf extra
        OutputExistsError: If a file exists and `overwrite` is false; nothing is written
    """
    formats = validate_export_formats(formats)
    targets = {
        fmt: _OutputTarget.of(output_dir, invoice, fmt, overwrite=overwrite) for fmt in formats
    }
    template_name = _document_template(factory, invoice, None)
    resolved = (
        resolve_company_details(factory, invoice, company, paths)
        if RENDERED_FORMATS.intersection(formats)
        else None
    )

    outcomes = []
    for fmt in formats:
        target = targets[fmt]
        if fmt == "json":
            path = output_path(output_dir, target.filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(invoice.model_dump_json(indent=2))
            outcomes.append(ExportOutcome(fmt, path, target.exists))
            continue

        if resolved is None:
            raise CompanyDetailsUnresolvedError()
        if fmt == "pdf":
            try:
                path = PDFService(
                    template_dir=paths.template_dir, output_dir=output_dir
                ).generate_pdf(
                    invoice=invoice,
                    company=resolved.details,
                    output_filename=target.filename,
                    template_name=template_name,
                    logo=resolved.logo,
                    payment_notes=payment_notes,
                )
            except ImportError as e:
                raise _pdf_unavailable(e) from e
        elif fmt == "html":
            path = HTMLService(template_dir=paths.template_dir, output_dir=output_dir).save_html(
                invoice=invoice,
                company=resolved.details,
                output_filename=target.filename,
                template_name=template_name,
                logo=resolved.logo,
                payment_notes=payment_notes,
            )
        else:
            path = UBLService(template_dir=paths.template_dir, output_dir=output_dir).save_ubl(
                invoice=invoice, company=resolved.details, output_filename=target.filename
            )
        outcomes.append(ExportOutcome(fmt, path, target.exists))
    return outcomes
