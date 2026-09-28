from fastapi import APIRouter, Depends, Query

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.core.audit_service import AuditLogEntry
from py_invoices.operations import audit as ops

router = APIRouter()


@router.get("/", response_model=list[AuditLogEntry])
def list_audit_logs(
    invoice_id: int | None = None,
    invoice_number: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    factory: RepositoryFactory = Depends(get_factory),
) -> list[AuditLogEntry]:
    """Matching entries, keeping the most recent `limit`."""
    return ops.list_audit_logs(factory, invoice_id, invoice_number, action, limit)
