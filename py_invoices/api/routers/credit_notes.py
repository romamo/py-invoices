from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pydantic_invoices.schemas import Invoice, InvoiceLineCreate

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.core.credit_service import CreditService
from py_invoices.core.numbering_service import NumberingService

router = APIRouter()


class CreditNoteRequest(BaseModel):
    """Request body for creating a credit note."""

    original_invoice_id: int
    reason: str | None = None
    lines: list[InvoiceLineCreate] | None = None
    refund_lines_indices: list[int] | None = None


@router.post("/", response_model=Invoice, status_code=status.HTTP_201_CREATED)
def create_credit_note(
    request: CreditNoteRequest,
    factory: RepositoryFactory = Depends(get_factory),
) -> Invoice:
    """Create a credit note for an existing invoice."""
    invoice_repo = factory.create_invoice_repository()

    # 1. Fetch original invoice
    original_invoice = invoice_repo.get_by_id(request.original_invoice_id)
    if not original_invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {request.original_invoice_id} not found",
        )

    # 2. Setup services
    numbering_service = NumberingService(invoice_repo=invoice_repo)
    credit_service = CreditService(invoice_repo, numbering_service)

    # 3. Create Credit Note
    try:
        credit_note = credit_service.create_credit_note(
            original_invoice=original_invoice,
            reason=request.reason,
            lines=request.lines,
            refund_lines_indices=request.refund_lines_indices,
        )
        return credit_note
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{credit_note_number}", response_model=Invoice)
def get_credit_note(
    credit_note_number: str,
    factory: RepositoryFactory = Depends(get_factory),
) -> Invoice:
    """Get a credit note by its number (e.g. CN-2023-001)."""
    invoice_repo = factory.create_invoice_repository()
    invoice = invoice_repo.get_by_number(credit_note_number)
    if not invoice:
        raise HTTPException(status_code=404, detail="Credit Note not found")

    # Verify it is actually a credit note?
    # The requirement didn't strictly say we must hide normal invoices here,
    # but strictly speaking `get_by_number` returns any invoice.
    # We could check invoice.type if it exists or status to differentiate.

    return invoice
