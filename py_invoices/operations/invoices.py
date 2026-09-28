"""Invoice operations: return domain objects, raise OperationError, never print."""

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
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
)

import py_invoices
from py_invoices.config import get_settings
from py_invoices.core import AuditService, HTMLService, NumberingService, PDFService
from py_invoices.operations.errors import (
    ClientNotFoundError,
    ClientNotSpecifiedError,
    CompanyDetailsRequiredError,
    CompanyDetailsUnresolvedError,
    CompanyNotFoundError,
    InvoiceNotFoundError,
    MissingDependencyError,
)
from py_invoices.plugins.factory import RepositoryFactory
from py_invoices.utils.image import file_to_base64_data_uri

RENDERED_FORMATS = frozenset({"pdf", "html", "ubl"})


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
    amount: float
    description: str
    client_id: int | None = None
    client_name: str | None = None
    client_address: str | None = None
    client_tax_id: str | None = None
    client_email: str | None = None
    client_phone: str | None = None
    invoice_number: str | None = None
    payment_terms: str = "Due on Receipt"
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


class ExportStatus(str, Enum):
    GENERATED = "generated"
    UNKNOWN_FORMAT = "unknown_format"
    MISSING_DEPENDENCIES = "missing_dependencies"


@dataclass(frozen=True, slots=True)
class ExportOutcome:
    format: str
    status: ExportStatus
    path: str | None = None


def package_template_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(py_invoices.__file__)), "templates")


def find_invoice(factory: RepositoryFactory, identifier: str) -> Invoice:
    """Find an invoice by numeric ID first, then by invoice number."""
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_id(int(identifier)) if identifier.isdigit() else None
    if invoice is None:
        invoice = repo.get_by_number(identifier)
    if invoice is None:
        raise InvoiceNotFoundError(identifier)
    return invoice


def list_invoices(factory: RepositoryFactory, limit: int) -> list[Invoice]:
    return factory.create_invoice_repository().get_all(limit=limit)


def list_overdue_invoices(factory: RepositoryFactory) -> list[Invoice]:
    return factory.create_invoice_repository().get_overdue()


def invoice_summary(factory: RepositoryFactory) -> InvoiceSummary:
    return factory.create_invoice_repository().get_summary()


def resolve_company_details(
    factory: RepositoryFactory, invoice: Invoice, overrides: CompanyOverrides
) -> ResolvedCompany:
    """Resolve company details from overrides, then invoice snapshots, then the company record."""
    name = overrides.name or invoice.company_name_snapshot
    address = overrides.address or invoice.company_address_snapshot
    tax_id = overrides.tax_id or invoice.company_tax_id_snapshot
    email = overrides.email or getattr(invoice, "company_email_snapshot", None)
    logo_path = overrides.logo_path or getattr(invoice, "company_logo_path_snapshot", None)

    if (not name or not address or not tax_id or not logo_path) and invoice.company_id:
        company = factory.create_company_repository().get_by_id(invoice.company_id)
        if company is None:
            raise CompanyNotFoundError(invoice.company_id)
        name = name or company.name
        address = address or company.address
        tax_id = tax_id or getattr(company, "tax_id", None)
        email = email or getattr(company, "email", None)
        logo_path = logo_path or getattr(company, "logo_path", None)

    if not name or not address:
        raise CompanyDetailsUnresolvedError()

    details = {"name": name, "address": address, "email": email, "tax_id": tax_id}
    return ResolvedCompany(details=details, logo=file_to_base64_data_uri(logo_path))


def _document_template(
    factory: RepositoryFactory, invoice: Invoice, template: str | None
) -> str | None:
    """Pick the explicit template, then the invoice's, then the client's preferred one."""
    chosen = template or getattr(invoice, "template_name", None)
    if not chosen and invoice.client_id:
        client = factory.create_client_repository().get_by_id(invoice.client_id)
        if client and getattr(client, "preferred_template", None):
            chosen = client.preferred_template
    return chosen


def _stored_payment_notes(factory: RepositoryFactory, invoice: Invoice) -> list[Any]:
    if not invoice.payment_note_ids:
        return []
    repo = factory.create_payment_note_repository()
    notes = (repo.get_by_id(note_id) for note_id in invoice.payment_note_ids)
    return [note for note in notes if note]


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
    resolved = resolve_company_details(factory, invoice, company)
    template_dir = get_settings().template_dir or package_template_dir()

    context: dict[str, Any] = {"logo": resolved.logo}
    payment_notes = _stored_payment_notes(factory, invoice)
    if payment_notes:
        context["payment_notes"] = payment_notes

    if kind is DocumentKind.HTML:
        html_service = HTMLService(template_dir=template_dir, output_dir=output_dir)
        os.makedirs(output_dir, exist_ok=True)
        path = html_service.save_html(
            invoice=invoice,
            company=resolved.details,
            template_name=_document_template(factory, invoice, template),
            **context,
        )
        return RenderedDocument(invoice=invoice, path=path)

    try:
        pdf_service = PDFService(template_dir=template_dir, output_dir=output_dir)
        os.makedirs(output_dir, exist_ok=True)
        path = pdf_service.generate_pdf(
            invoice=invoice,
            company=resolved.details,
            template_name=_document_template(factory, invoice, template),
            **context,
        )
    except ImportError as e:
        raise MissingDependencyError("pdf", str(e)) from e
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
    existing = next((c for c in repo.get_all() if c.name.lower() == wanted), None)
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


def create_invoice(factory: RepositoryFactory, request: NewInvoice) -> CreatedInvoice:
    """Create a single-line invoice, creating the client by name if it does not exist."""
    client, client_created = _resolve_client(factory, request)
    invoice_repo = factory.create_invoice_repository()
    number = request.invoice_number or NumberingService(invoice_repo=invoice_repo).generate_number()

    preferred = getattr(client, "preferred_template", None)
    invoice = invoice_repo.create(
        InvoiceCreate(
            number=number,
            issue_date=datetime.now().date(),
            status=InvoiceStatus.UNPAID,
            due_date=date.today(),
            payment_terms=request.payment_terms,
            original_invoice_id=None,
            reason=None,
            client_id=client.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=str(client.tax_id) if client.tax_id else None,
            company_id=1,
            company_name_snapshot=request.company.name,
            company_address_snapshot=request.company.address,
            company_tax_id_snapshot=request.company.tax_id,
            template_name=(
                request.template
                if request.template is not None
                else preferred
                if isinstance(preferred, str)
                else None
            ),
            lines=[
                InvoiceLineCreate(
                    description=request.description, quantity=1, unit_price=request.amount
                )
            ],
        )
    )
    return CreatedInvoice(invoice=invoice, created_client=client if client_created else None)


def clone_invoice(factory: RepositoryFactory, identifier: str, issue_date: date) -> ClonedInvoice:
    """Copy an invoice under the next number, due Net 30 from issue_date, and audit it."""
    original = find_invoice(factory, identifier)
    invoice_repo = factory.create_invoice_repository()
    number = NumberingService(invoice_repo=invoice_repo).generate_number()

    template_name = getattr(original, "template_name", None)
    if not template_name:
        client = factory.create_client_repository().get_by_id(original.client_id)
        if client:
            template_name = getattr(client, "preferred_template", None)

    invoice = invoice_repo.create(
        InvoiceCreate(
            number=number,
            issue_date=issue_date,
            status=InvoiceStatus.UNPAID,
            due_date=issue_date + timedelta(days=30),
            payment_terms=original.payment_terms,
            client_id=original.client_id,
            client_name_snapshot=original.client_name_snapshot,
            client_address_snapshot=original.client_address_snapshot,
            client_tax_id_snapshot=original.client_tax_id_snapshot,
            company_id=original.company_id,
            payment_note_ids=original.payment_note_ids,
            template_name=template_name,
            lines=[
                InvoiceLineCreate(
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
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


def resolve_export_company(
    factory: RepositoryFactory,
    invoice: Invoice,
    overrides: CompanyOverrides,
    formats: list[str],
    *,
    lookup: bool,
) -> dict[str, Any]:
    """Company details for export_invoice.

    Rendered formats need a name and address; with lookup, missing ones come from the
    company record. Other formats get placeholders.
    """
    needs_company = any(f.lower() in RENDERED_FORMATS for f in formats)
    if needs_company and lookup:
        name, address = overrides.name, overrides.address
        tax_id, email, logo_path = overrides.tax_id, overrides.email, overrides.logo_path
        if not name or not address:
            company = factory.create_company_repository().get_by_id(invoice.company_id or 1)
            if company:
                name = name or company.name
                address = address or company.address
                tax_id = tax_id or getattr(company, "tax_id", None)
                email = email or getattr(company, "email", None)
                logo_path = logo_path or getattr(company, "logo_path", None)
        if not name or not address:
            raise CompanyDetailsRequiredError(lookup_attempted=True)
        return {
            "name": name,
            "address": address,
            "email": email,
            "tax_id": tax_id,
            "logo_path": logo_path,
        }

    if needs_company and (not overrides.name or not overrides.address):
        raise CompanyDetailsRequiredError(lookup_attempted=False)
    return {
        "name": overrides.name or "Unknown Company",
        "address": overrides.address or "Unknown Address",
        "email": overrides.email,
        "tax_id": overrides.tax_id,
        "logo_path": overrides.logo_path,
    }


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
    invoice: Invoice,
    formats: list[str],
    output_dir: str,
    company: dict[str, Any],
    payment_notes: list[dict[str, str]],
) -> list[ExportOutcome]:
    """Write the invoice in each requested format, one outcome per format in order."""
    # Resolved at call time: tests substitute these services on py_invoices.core
    from py_invoices.core import HTMLService, PDFService, UBLService

    template_dir = package_template_dir()
    os.makedirs(output_dir, exist_ok=True)
    logo = file_to_base64_data_uri(company.get("logo_path"))

    outcomes = []
    for fmt in (f.lower() for f in formats):
        try:
            if fmt == "pdf":
                path = PDFService(template_dir=template_dir, output_dir=output_dir).generate_pdf(
                    invoice=invoice, company=company, logo=logo, payment_notes=payment_notes
                )
            elif fmt == "html":
                path = HTMLService(template_dir=template_dir, output_dir=output_dir).save_html(
                    invoice=invoice, company=company, logo=logo, payment_notes=payment_notes
                )
            elif fmt == "ubl":
                path = UBLService(template_dir=template_dir, output_dir=output_dir).save_ubl(
                    invoice=invoice, company=company
                )
            elif fmt == "json":
                path = os.path.join(output_dir, f"{invoice.number}.json")
                with open(path, "w") as f:
                    f.write(invoice.model_dump_json(indent=2))
            else:
                outcomes.append(ExportOutcome(fmt, ExportStatus.UNKNOWN_FORMAT))
                continue
        except ImportError:
            outcomes.append(ExportOutcome(fmt, ExportStatus.MISSING_DEPENDENCIES))
            continue
        outcomes.append(ExportOutcome(fmt, ExportStatus.GENERATED, path))
    return outcomes
