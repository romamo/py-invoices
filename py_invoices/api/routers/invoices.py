from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic_invoices.schemas import Invoice, InvoiceCreate, InvoiceSummary, InvoiceType

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.core.audit_service import AuditService
from py_invoices.core.html_service import is_safe_file_name
from py_invoices.core.summary import MixedCurrencyError
from py_invoices.operations import invoices as ops
from py_invoices.operations.errors import (
    CompanyDetailsUnresolvedError,
    LogoNotFoundError,
    MissingDependencyError,
    MissingSystemLibrariesError,
    OperationError,
    PaymentNoteNotFoundError,
)

router = APIRouter()


def _find(factory: RepositoryFactory, invoice_number: str) -> Invoice:
    invoice = factory.create_invoice_repository().get_by_number(invoice_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def _render_error(error: OperationError) -> HTTPException:
    match error:
        case MissingDependencyError() | MissingSystemLibrariesError():
            return HTTPException(status_code=501, detail=str(error))
        case CompanyDetailsUnresolvedError() | LogoNotFoundError() | PaymentNoteNotFoundError():
            return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


@router.get("/overdue", response_model=list[Invoice])
def list_overdue_invoices(factory: RepositoryFactory = Depends(get_factory)) -> list[Invoice]:
    return factory.create_invoice_repository().get_overdue()


@router.get("/summary", response_model=InvoiceSummary)
def get_invoices_summary(factory: RepositoryFactory = Depends(get_factory)) -> InvoiceSummary:
    try:
        return factory.create_invoice_repository().get_summary()
    except MixedCurrencyError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e


@router.get("/", response_model=list[Invoice])
def list_invoices(
    limit: int = Query(10, ge=1, le=500),
    offset: int = Query(0, ge=0),
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Invoice]:
    return factory.create_invoice_repository().get_all(skip=offset, limit=limit)


@router.post("/", response_model=Invoice)
def create_invoice(
    invoice_in: InvoiceCreate, factory: RepositoryFactory = Depends(get_factory)
) -> Invoice:
    """Store a standard invoice as given; its number must not be in use yet.

    Credit notes go through POST /credit-notes, which enforces the credit limits.
    """
    if invoice_in.type is not InvoiceType.STANDARD or invoice_in.original_invoice_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only standard invoices can be created here; use POST /credit-notes",
        )
    if not is_safe_file_name(invoice_in.number):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invoice number cannot contain '/', '\\' or start with '.'",
        )
    repo = factory.create_invoice_repository()
    if repo.get_by_number(invoice_in.number):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice number '{invoice_in.number}' is already used",
        )
    invoice = repo.create(invoice_in)
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_created(invoice)
    return invoice


@router.get("/{invoice_number}", response_model=Invoice)
def get_invoice(invoice_number: str, factory: RepositoryFactory = Depends(get_factory)) -> Invoice:
    return _find(factory, invoice_number)


@router.get("/{invoice_number}/html", response_class=Response)
def get_invoice_html(
    invoice_number: str, factory: RepositoryFactory = Depends(get_factory)
) -> Response:
    invoice = _find(factory, invoice_number)
    try:
        html_content = ops.render_invoice_html(factory, invoice)
    except OperationError as e:
        raise _render_error(e) from e
    return Response(content=html_content, media_type="text/html")


@router.get("/{invoice_number}/pdf", response_class=Response)
def get_invoice_pdf(
    invoice_number: str, factory: RepositoryFactory = Depends(get_factory)
) -> Response:
    invoice = _find(factory, invoice_number)
    try:
        pdf_bytes = ops.render_invoice_pdf(factory, invoice)
    except OperationError as e:
        raise _render_error(e) from e

    filename = f"{invoice.number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )
