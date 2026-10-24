import datetime as dt
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from pydantic_invoices.schemas import Client, Invoice, InvoiceStatus, InvoiceSummary, InvoiceType
from pydantic_invoices.vo import CountryCode, Money, TaxId
from rich.console import Console
from rich.table import Table
from treaty import Arg, Ctx, Flag, Format, Out, ParseError

from py_invoices.cli.app import (
    Amount,
    Common,
    Store,
    app,
    exit_for,
    operation_errors,
    show_money,
)
from py_invoices.constants import CLI_NAME
from py_invoices.core.html_service import is_safe_file_name
from py_invoices.operations import invoices as ops
from py_invoices.operations.errors import OperationError, PaymentTermsError
from py_invoices.operations.invoices import (
    CompanyOverrides,
    DocumentKind,
    ExportOutcome,
    NewInvoice,
)

invoices = app.group("invoices", description="Manage invoices")

type ExportFormat = Literal["pdf", "html", "ubl", "json"]


# Arguments


@dataclass(frozen=True, slots=True, kw_only=True)
class CompanyFlags(Common):
    company_name: str | None = Flag(default=None, description="Company name")
    company_address: str | None = Flag(default=None, description="Company address")
    company_tax_id: TaxId | None = Flag(default=None, description="Company tax ID")
    company_email: str | None = Flag(default=None, description="Company email")
    company_logo_path: Path | None = Flag(default=None, description="Company logo image file")

    def company(self) -> CompanyOverrides:
        return CompanyOverrides(
            name=self.company_name,
            address=self.company_address,
            tax_id=str(self.company_tax_id) if self.company_tax_id else None,
            email=self.company_email,
            logo_path=str(self.company_logo_path) if self.company_logo_path else None,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentArgs(CompanyFlags):
    invoice: str = Arg(description="Invoice number or ID")
    output_dir: Path = Flag(default=Path("output"), description="Directory for the file")
    template: str | None = Flag(default=None, description="Template name, such as invoice.html.j2")


@dataclass(frozen=True, slots=True, kw_only=True)
class ShowArgs(Common):
    invoice: str = Arg(description="Invoice number or ID")


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateArgs(CompanyFlags):
    amount: Decimal = Flag(description="Invoice amount, an exact decimal such as 1234.50")
    currency: str = Flag(
        default="USD", pattern="[A-Za-z]{3}", description="ISO 4217 currency of the amount"
    )
    description: str = Flag(description="Line item description")
    client_id: int | None = Flag(default=None, description="ID of an existing client")
    client_name: str | None = Flag(
        default=None, description="Client name; a client of that name is created if none exists"
    )
    client_address: str | None = Flag(default=None, description="Address of a new client")
    client_tax_id: TaxId | None = Flag(default=None, description="Tax ID of a new client")
    client_email: str | None = Flag(default=None, description="Email of a new client")
    client_phone: str | None = Flag(default=None, description="Phone of a new client")
    client_city: str | None = Flag(default=None, description="City of a new client")
    client_postal_code: str | None = Flag(default=None, description="Postal code of a new client")
    client_country: CountryCode | None = Flag(
        default=None, description="ISO 3166-1 alpha-2 country of a new client, such as DE"
    )
    invoice_number: str | None = Flag(
        default=None, description="Invoice number instead of the next generated one"
    )
    payment_terms: str = Flag(
        default=ops.DEFAULT_PAYMENT_TERMS,
        description="Payment terms; 'Net <days>' also sets the due date",
    )
    due_date: dt.date | None = Flag(
        default=None, description="Due date (YYYY-MM-DD); overrides the one from payment terms"
    )
    bank_account: str | None = Flag(
        default=None, description="Bank account details printed on exported files"
    )
    export: tuple[ExportFormat, ...] = Flag(
        default=(), short="e", description="File formats to export the new invoice to"
    )
    output_dir: Path = Flag(default=Path("output"), description="Directory for exported files")
    template: str | None = Flag(default=None, description="Template name for exported files")

    def __post_init__(self) -> None:
        errors = []
        if self.amount <= 0:
            errors.append(
                ParseError(
                    f"--amount must be a positive number, got {self.amount}",
                    context={"field": "amount"},
                )
            )
        if self.client_id is None and self.client_name is None:
            errors.append(
                ParseError(
                    "--client-id or --client-name is required",
                    context={"field": "client_name"},
                    suggestion=f"{CLI_NAME} clients list shows client IDs",
                )
            )
        if self.invoice_number is not None and not is_safe_file_name(self.invoice_number):
            errors.append(
                ParseError(
                    f"--invoice-number {self.invoice_number!r} cannot contain '/', '\\' "
                    "or start with '.'",
                    context={"field": "invoice_number"},
                )
            )
        if self.due_date is None:
            try:
                ops.due_date_for_terms(self.payment_terms, dt.date.today())
            except PaymentTermsError as e:
                errors.append(
                    ParseError(
                        str(e),
                        context={"field": "payment_terms"},
                        suggestion="pass --due-date YYYY-MM-DD",
                    )
                )
        if errors:
            raise ParseError.combine(errors)


@dataclass(frozen=True, slots=True, kw_only=True)
class CloneArgs(CompanyFlags):
    invoice: str = Arg(description="Invoice number or ID to clone")
    date: dt.date | None = Flag(default=None, description="Issue date (YYYY-MM-DD); default today")
    export: tuple[ExportFormat, ...] = Flag(
        default=(), short="e", description="File formats to export the clone to"
    )
    output_dir: Path = Flag(default=Path("output"), description="Directory for exported files")


# Results


@dataclass(frozen=True, slots=True)
class InvoiceRow:
    id: int
    number: str
    issue_date: dt.date
    due_date: dt.date | None
    client: str | None
    status: InvoiceStatus
    total: Amount

    @classmethod
    def of(cls, invoice: Invoice) -> InvoiceRow:
        return cls(
            id=invoice.id,
            number=invoice.number,
            issue_date=invoice.issue_date,
            due_date=invoice.due_date,
            client=invoice.client_name_snapshot,
            status=invoice.status,
            total=Amount.of(invoice.total_amount),
        )


@dataclass(frozen=True, slots=True)
class Line:
    description: str
    quantity: int
    unit_price: Amount
    total: Amount


@dataclass(frozen=True, slots=True)
class InvoiceDetails:
    id: int
    number: str
    type: InvoiceType
    status: InvoiceStatus
    issue_date: dt.date
    due_date: dt.date | None
    payment_terms: str
    client: str | None
    total: Amount
    lines: list[Line] = Out(ordered=True)


@dataclass(frozen=True, slots=True)
class Summary:
    total_count: int
    paid_count: int
    unpaid_count: int
    overdue_count: int
    total_amount: Amount
    total_paid: Amount
    total_due: Amount

    @classmethod
    def of(cls, summary: InvoiceSummary) -> Summary:
        return cls(
            total_count=summary.total_count,
            paid_count=summary.paid_count,
            unpaid_count=summary.unpaid_count,
            overdue_count=summary.overdue_count,
            total_amount=Amount.of(summary.total_amount),
            total_paid=Amount.of(summary.total_paid),
            total_due=Amount.of(summary.total_due),
        )


@dataclass(frozen=True, slots=True)
class Document:
    effect: Literal["created"]
    invoice: str
    format: Literal["pdf", "html"]
    path: Path


@dataclass(frozen=True, slots=True)
class Export:
    format: ExportFormat
    path: Path

    @classmethod
    def of(cls, outcome: ExportOutcome) -> Export:
        return cls(cast(ExportFormat, outcome.format), Path(outcome.path))


@dataclass(frozen=True, slots=True)
class ClientRef:
    id: int
    name: str

    @classmethod
    def of(cls, client: Client) -> ClientRef:
        return cls(client.id, client.name)


@dataclass(frozen=True, slots=True)
class Created:
    effect: Literal["created"]
    invoice: InvoiceRow
    created_client: ClientRef | None
    exports: list[Export] = Out(ordered=True)


@dataclass(frozen=True, slots=True)
class Cloned:
    effect: Literal["created"]
    original: str
    invoice: InvoiceRow
    exports: list[Export] = Out(ordered=True)


# Plain renderers: `data` arrives as JSON values


def _table(table: Table) -> str:
    out = io.StringIO()
    Console(file=out, width=120, color_system=None).print(table)
    return out.getvalue()


def render_rows(data: Sequence[Mapping[str, Any]]) -> str:
    if not data:
        return "No invoices found.\n"
    table = Table(title="Invoices")
    for column in ("Number", "Date", "Due", "Client", "Total", "Status"):
        table.add_column(column, justify="right" if column == "Total" else "left")
    for row in data:
        table.add_row(
            row["number"],
            row["issue_date"],
            row["due_date"] or "",
            row["client"] or "",
            show_money(row["total"]),
            row["status"],
        )
    return _table(table)


def render_details(data: Mapping[str, Any]) -> str:
    table = Table(title="Line Items")
    table.add_column("Description")
    for column in ("Qty", "Price", "Total"):
        table.add_column(column, justify="right")
    for line in data["lines"]:
        table.add_row(
            line["description"],
            str(line["quantity"]),
            show_money(line["unit_price"]),
            show_money(line["total"]),
        )
    return (
        f"Invoice: {data['number']}\n"
        f"Date: {data['issue_date']}\n"
        f"Status: {data['status']}\n"
        f"Client: {data['client'] or ''}\n"
        f"Type: {data['type']}\n"
        f"{_table(table)}"
        f"Total: {show_money(data['total'])}\n"
    )


def render_summary(data: Mapping[str, Any]) -> str:
    return (
        "Invoice Summary\n"
        f"Total Count:    {data['total_count']}\n"
        f"Paid Count:     {data['paid_count']}\n"
        f"Unpaid Count:   {data['unpaid_count']}\n"
        f"Overdue Count:  {data['overdue_count']}\n"
        f"Total Amount:   {show_money(data['total_amount'])}\n"
        f"Total Paid:     {show_money(data['total_paid'])}\n"
        f"Total Due:      {show_money(data['total_due'])}\n"
    )


def render_stats(data: Mapping[str, Any]) -> str:
    return (
        "INVOICE STATISTICS\n"
        f"Total Invoices:  {data['total_count']}\n"
        f"Total Amount:    {show_money(data['total_amount'])}\n"
        f"Total Paid:      {show_money(data['total_paid'])}\n"
        f"Total Due:       {show_money(data['total_due'])}\n"
        f"Overdue:         {data['overdue_count']}\n"
    )


def render_document(data: Mapping[str, Any]) -> str:
    kind = data["format"].upper()
    return f"Generated {kind} for Invoice {data['invoice']}\n  Path: {data['path']}\n"


def _render_exports(exports: Sequence[Mapping[str, Any]]) -> str:
    return "".join(f"  -> Generated {e['format'].upper()}: {e['path']}\n" for e in exports)


def render_created(data: Mapping[str, Any]) -> str:
    invoice = data["invoice"]
    client = data["created_client"]
    created_client = f"Created Client {client['name']} (ID: {client['id']})\n" if client else ""
    return (
        f"{created_client}Created Invoice {invoice['number']}\n"
        f"  Client: {invoice['client'] or ''}\n"
        f"  Total:  {show_money(invoice['total'])}\n"
        f"{_render_exports(data['exports'])}"
    )


def render_cloned(data: Mapping[str, Any]) -> str:
    invoice = data["invoice"]
    return (
        f"Cloned Invoice {data['original']} -> {invoice['number']}\n"
        f"  Total:  {show_money(invoice['total'])}\n"
        f"{_render_exports(data['exports'])}"
    )


# Commands


def _document(kind: DocumentKind, args: DocumentArgs, store: Store) -> Document:
    with operation_errors():
        document = ops.render_invoice_document(
            store.factory, args.invoice, kind, str(args.output_dir), args.company(), args.template
        )
    return Document("created", document.invoice.number, kind.value, Path(document.path))


@invoices.command(
    "pdf",
    description="Render an invoice to a PDF file",
    danger_level="mutating",
    exit_codes=["NOT_FOUND"],
    renderers={Format.PLAIN: render_document},
    examples=[("Render invoice INV-2026-0001 to PDF", f"{CLI_NAME} invoices pdf INV-2026-0001")],
)
def generate_pdf(args: DocumentArgs, ctx: Ctx, store: Store) -> Document:
    return _document(DocumentKind.PDF, args, store)


@invoices.command(
    "html",
    description="Render an invoice to an HTML file",
    danger_level="mutating",
    exit_codes=["NOT_FOUND"],
    renderers={Format.PLAIN: render_document},
    examples=[("Render invoice INV-2026-0001 to HTML", f"{CLI_NAME} invoices html INV-2026-0001")],
)
def generate_html(args: DocumentArgs, ctx: Ctx, store: Store) -> Document:
    return _document(DocumentKind.HTML, args, store)


@invoices.command(
    "list",
    description="List invoices",
    danger_level="safe",
    exit_codes=[],
    sort_key="id",
    default_limit=10,
    renderers={Format.PLAIN: render_rows},
    examples=[("List every invoice", f"{CLI_NAME} invoices list --limit 0")],
)
def list_invoices(args: Common, ctx: Ctx, store: Store) -> list[InvoiceRow]:
    return [InvoiceRow.of(invoice) for invoice in ops.list_invoices(store.factory)]


@invoices.command(
    "details",
    description="Show an invoice with its lines",
    danger_level="safe",
    exit_codes=["NOT_FOUND"],
    renderers={Format.PLAIN: render_details},
    examples=[("Show invoice INV-2026-0001", f"{CLI_NAME} invoices details INV-2026-0001")],
)
def get_invoice_details(args: ShowArgs, ctx: Ctx, store: Store) -> InvoiceDetails:
    with operation_errors():
        invoice = ops.find_invoice(store.factory, args.invoice)
    return InvoiceDetails(
        id=invoice.id,
        number=invoice.number,
        type=invoice.type,
        status=invoice.status,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        payment_terms=invoice.payment_terms,
        client=invoice.client_name_snapshot,
        total=Amount.of(invoice.total_amount),
        lines=[
            Line(
                description=line.description,
                quantity=line.quantity,
                unit_price=Amount.of(line.unit_price),
                total=Amount.of(line.total),
            )
            for line in invoice.lines
        ],
    )


@invoices.command(
    "overdue",
    description="List overdue invoices",
    danger_level="safe",
    exit_codes=[],
    sort_key="id",
    renderers={Format.PLAIN: render_rows},
    examples=[("List overdue invoices", f"{CLI_NAME} invoices overdue")],
)
def list_overdue(args: Common, ctx: Ctx, store: Store) -> list[InvoiceRow]:
    return [InvoiceRow.of(invoice) for invoice in ops.list_overdue_invoices(store.factory)]


def _summary(store: Store) -> Summary:
    with operation_errors():
        return Summary.of(ops.invoice_summary(store.factory))


@invoices.command(
    "summary",
    description="Count and total invoices by payment state",
    danger_level="safe",
    exit_codes=[],
    renderers={Format.PLAIN: render_summary},
    examples=[("Show invoice totals", f"{CLI_NAME} invoices summary")],
)
def show_summary(args: Common, ctx: Ctx, store: Store) -> Summary:
    return _summary(store)


@invoices.command(
    "stats",
    description="Count and total invoices, the short form of summary",
    danger_level="safe",
    exit_codes=[],
    renderers={Format.PLAIN: render_stats},
    examples=[("Show invoice statistics", f"{CLI_NAME} invoices stats")],
)
def stats(args: Common, ctx: Ctx, store: Store) -> Summary:
    return _summary(store)


def _export(
    store: Store,
    invoice: Invoice,
    formats: list[str],
    output_dir: Path,
    company: CompanyOverrides,
    notes: list[dict[str, str]],
    result: Created | Cloned,
) -> list[Export]:
    """Export a saved invoice; a failure carries `result`, so the caller learns it was saved."""
    try:
        outcomes = ops.export_invoice(
            store.factory, invoice, formats, str(output_dir), company, notes
        )
    except OperationError as e:
        failed = exit_for(e)
        failed.data = result
        raise failed from e
    return [Export.of(outcome) for outcome in outcomes]


def _warn_if_memory(ctx: Ctx, store: Store) -> None:
    if store.factory.plugin.name == "memory":
        ctx.warn(
            "MEMORY_BACKEND",
            "The invoice is stored in memory and is gone when the run ends",
            suggestion="set INVOICES_BACKEND or pass --backend to keep it",
        )


@invoices.command(
    "create",
    description="Create a one-line invoice, creating the client by name if it does not exist",
    danger_level="mutating",
    exit_codes=["NOT_FOUND", "CONFLICT"],
    renderers={Format.PLAIN: render_created},
    examples=[
        (
            "Invoice a new client and export PDF and HTML",
            f'{CLI_NAME} invoices create --client-name "Acme GmbH" --client-address "Main St 1" '
            '--amount 1234.50 --currency EUR --description "Consulting" --payment-terms "Net 30" '
            '--company-name "Me Ltd" --company-address "Road 1" -e pdf -e html',
        )
    ],
)
def create_invoice(args: CreateArgs, ctx: Ctx, store: Store) -> Created:
    company = args.company()
    request = NewInvoice(
        amount=Money(args.amount, args.currency),
        description=args.description,
        client_id=args.client_id,
        client_name=args.client_name,
        client_address=args.client_address,
        client_tax_id=str(args.client_tax_id) if args.client_tax_id else None,
        client_email=args.client_email,
        client_phone=args.client_phone,
        client_city=args.client_city,
        client_postal_code=args.client_postal_code,
        client_country=args.client_country,
        invoice_number=args.invoice_number,
        payment_terms=args.payment_terms,
        due_date=args.due_date,
        company=company,
        template=args.template,
    )
    with operation_errors():
        formats = ops.check_new_invoice_export(store.factory, list(args.export), company)
        created = ops.create_invoice(store.factory, request)
    _warn_if_memory(ctx, store)
    client = ClientRef.of(created.created_client) if created.created_client else None
    result = Created("created", InvoiceRow.of(created.invoice), client, [])
    if not formats:
        return result
    notes = ops.export_payment_notes(args.payment_terms, args.bank_account)
    exports = _export(store, created.invoice, formats, args.output_dir, company, notes, result)
    return Created("created", result.invoice, client, exports)


@invoices.command(
    "clone",
    description="Copy an invoice under the next number, keeping its payment period",
    danger_level="mutating",
    exit_codes=["NOT_FOUND"],
    renderers={Format.PLAIN: render_cloned},
    examples=[
        (
            "Clone invoice INV-2026-0001 dated 2026-10-01",
            f"{CLI_NAME} invoices clone INV-2026-0001 --date 2026-10-01",
        )
    ],
)
def clone_invoice(args: CloneArgs, ctx: Ctx, store: Store) -> Cloned:
    company = args.company()
    with operation_errors():
        original = ops.find_invoice(store.factory, args.invoice)
        formats = ops.check_invoice_export(store.factory, original, list(args.export), company)
        cloned = ops.clone_invoice(store.factory, args.invoice, args.date or dt.date.today())
    _warn_if_memory(ctx, store)
    result = Cloned("created", cloned.original.number, InvoiceRow.of(cloned.invoice), [])
    if not formats:
        return result
    notes = ops.export_payment_notes(cloned.invoice.payment_terms, None)
    exports = _export(store, cloned.invoice, formats, args.output_dir, company, notes, result)
    return Cloned("created", result.original, result.invoice, exports)
