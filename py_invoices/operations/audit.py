"""Audit log operations."""

from typing import Any

from py_invoices.core.audit_service import AuditLogEntry, AuditService
from py_invoices.plugins.factory import RepositoryFactory


def list_audit_logs(
    factory: RepositoryFactory,
    invoice_id: int | None,
    invoice_number: str | None,
    action: str | None,
    limit: int,
) -> list[AuditLogEntry]:
    """Matching log entries, keeping only the most recent `limit` of them."""
    service = AuditService(audit_repo=factory.create_audit_repository())
    logs = service.get_logs(invoice_id=invoice_id, invoice_number=invoice_number, action=action)
    return logs[-limit:] if limit and len(logs) > limit else logs


def audit_summary(factory: RepositoryFactory) -> dict[str, Any]:
    return AuditService(audit_repo=factory.create_audit_repository()).get_summary()


def entry_details(entry: AuditLogEntry) -> str:
    """One-line description of what an entry changed."""
    details = []
    if entry.old_value:
        details.append(f"Old: {entry.old_value}")
    if entry.new_value:
        details.append(f"New: {entry.new_value}")
    if entry.notes:
        details.append(f"Note: {entry.notes}")
    return "; ".join(details)
