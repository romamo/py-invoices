from fastapi import APIRouter, Depends, Query
from pydantic_invoices.schemas import Payment

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()


@router.get("/", response_model=list[Payment])
def list_payments(
    invoice_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Payment]:
    repo = factory.create_payment_repository()
    if invoice_id is not None:
        return repo.get_by_invoice(invoice_id)[offset : offset + limit]
    return repo.get_all(skip=offset, limit=limit)
