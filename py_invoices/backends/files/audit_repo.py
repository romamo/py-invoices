"""File-based audit repository."""

from pathlib import Path

from py_invoices.core.audit_service import AuditLogEntry
from py_invoices.plugins.base import AuditRepository

from .storage import FileStorage


class FileAuditRepository(AuditRepository):
    """File-based implementation of Audit repository, one file per entry."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        self.storage = FileStorage[AuditLogEntry](
            root_dir, "audit_logs", AuditLogEntry, default_format=file_format
        )

    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        entry_id = self.storage.get_next_id()
        stored = entry.model_copy(update={"id": entry_id})
        self.storage.save(stored, entry_id)
        return stored

    def get_by_invoice(self, invoice_id: int) -> list[AuditLogEntry]:
        return [log for log in self.storage.load_all() if log.invoice_id == invoice_id]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AuditLogEntry]:
        return self.storage.load_all()[skip : skip + limit]
