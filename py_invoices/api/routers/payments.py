
from fastapi import APIRouter, Depends
from pydantic_invoices.schemas import Payment

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()

@router.get("/", response_model=list[Payment])
def list_payments(
    invoice_id: int | None = None,
    limit: int = 100,
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Payment]:
    repo = factory.create_payment_repository()
    if invoice_id is not None:
        return repo.get_by_invoice(invoice_id)
    return repo.get_all(limit=limit)
