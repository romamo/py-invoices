
from fastapi import APIRouter, Depends

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.core.audit_service import AuditLogEntry, AuditService

router = APIRouter()

@router.get("/", response_model=list[AuditLogEntry])
def list_audit_logs(
    invoice_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    factory: RepositoryFactory = Depends(get_factory),
) -> list[AuditLogEntry]:
    # We need to instantiate the service with the repository from the factory
    repo = factory.create_audit_repository()
    service = AuditService(audit_repo=repo)

    # get_logs signature: (invoice_id, invoice_number, action)
    # It doesn't seem to support limit in the service method directly,
    # but the repo might. The service just calls repo.get_all() or by_invoice.
    # We will fetch and slice for now if the service doesn't support limit.
    logs = service.get_logs(invoice_id=invoice_id, action=action)

    # Simple slicing for limit
    return logs[:limit]
