
from fastapi import APIRouter, Depends, HTTPException
from pydantic_invoices.schemas import Invoice, InvoiceCreate

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic_invoices.schemas import Invoice, InvoiceCreate

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.core.html_service import HTMLService

router = APIRouter()

@router.get("/overdue", response_model=list[Invoice])
def list_overdue_invoices(
    factory: RepositoryFactory = Depends(get_factory)
) -> list[Invoice]:
    repo = factory.create_invoice_repository()
    return repo.get_overdue()

@router.get("/summary")
def get_invoices_summary(
    factory: RepositoryFactory = Depends(get_factory)
) -> dict:
    repo = factory.create_invoice_repository()
    return repo.get_summary()


@router.get("/", response_model=list[Invoice])
def list_invoices(
    limit: int = 10, offset: int = 0, factory: RepositoryFactory = Depends(get_factory)
) -> list[Invoice]:
    repo = factory.create_invoice_repository()
    # Note: repo.get_all usually takes limit, but offset might depend on impl.
    # We will just pass limit for now if get_all signature is strictly (limit)
    return repo.get_all(limit=limit)

@router.post("/", response_model=Invoice)
def create_invoice(
    invoice_in: InvoiceCreate, factory: RepositoryFactory = Depends(get_factory)
) -> Invoice:
    repo = factory.create_invoice_repository()
    # Numbering service logic should ideally be here if not in repo
    # But for simplicity, we assume invoice_in has what it needs or we'd need a service

    # In basic_usage.py, we saw:
    # numbering = NumberingService(invoice_repo=invoice_repo)
    # invoice_number = numbering.generate_number()
    # Use that pattern here if possible, but for now strict repo create

    return repo.create(invoice_in)

@router.get("/{invoice_number}", response_model=Invoice)
def get_invoice(
    invoice_number: str, factory: RepositoryFactory = Depends(get_factory)
) -> Invoice:
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_number(invoice_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.get("/{invoice_number}/html", response_class=Response)
def get_invoice_html(
    invoice_number: str, factory: RepositoryFactory = Depends(get_factory)
) -> Response:
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_number(invoice_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    company_repo = factory.create_company_repository()
    company = company_repo.get_default()
    if not company:
         # Fallback or error? For now error
         raise HTTPException(status_code=404, detail="Default company not found")
    
    # HTMLService requires company as a dict
    company_dict = company.model_dump()
    
    html_service = HTMLService()
    html_content = html_service.generate_html(invoice=invoice, company=company_dict)
    
    return Response(content=html_content, media_type="text/html")

@router.get("/{invoice_number}/pdf", response_class=Response)
def get_invoice_pdf(
    invoice_number: str, factory: RepositoryFactory = Depends(get_factory)
) -> Response:
    repo = factory.create_invoice_repository()
    invoice = repo.get_by_number(invoice_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    company_repo = factory.create_company_repository()
    company = company_repo.get_default()
    if not company:
        raise HTTPException(status_code=404, detail="Default company not found")

    from py_invoices.core.pdf_service import PDFService
    pdf_service = PDFService()
    try:
        pdf_bytes = pdf_service.generate_pdf_bytes(
            invoice=invoice,
            company=company.model_dump(),
        )
    except ImportError as e:
         raise HTTPException(status_code=501, detail=str(e))
    except RuntimeError as e:
         raise HTTPException(status_code=500, detail=str(e))

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={invoice.number}.pdf"}
    )


