"""In-memory audit repository."""

from py_invoices.core.audit_service import AuditLogEntry
from py_invoices.plugins.base import AuditRepository


class MemoryAuditRepository(AuditRepository):
    """In-memory implementation for Audit repository."""

    def __init__(self) -> None:
        self._logs: list[AuditLogEntry] = []

    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._logs.append(entry)
        return entry

    def get_by_invoice(self, invoice_id: int) -> list[AuditLogEntry]:
        return [log for log in self._logs if log.invoice_id == invoice_id]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AuditLogEntry]:
        return self._logs[skip : skip + limit]

    def clear(self) -> None:
        self._logs.clear()
