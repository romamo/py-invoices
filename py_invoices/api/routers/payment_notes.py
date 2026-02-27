from fastapi import APIRouter, Depends, HTTPException
from pydantic_invoices.schemas.payment_note import PaymentNote

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()

@router.get("/default", response_model=PaymentNote)
def get_default_payment_note(
    factory: RepositoryFactory = Depends(get_factory),
) -> PaymentNote:
    repo = factory.create_payment_note_repository()
    note = repo.get_default()
    if not note:
        raise HTTPException(status_code=404, detail="Default payment note not found")
    return note
