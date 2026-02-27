"""File-based audit repository."""

from pathlib import Path
from typing import Any

from py_invoices.core.audit_service import AuditLogEntry

from .storage import FileStorage


class FileAuditRepository:
    """File-based implementation of Audit repository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[AuditLogEntry](
            root_dir, "audit_logs", AuditLogEntry, default_format=file_format
        )

    def add(self, entry: Any) -> Any:
        """Add audit log entry."""
        if hasattr(entry, "model_dump"):
            data = entry.model_dump()
        else:
            data = entry

        # Ensure it's an AuditLogEntry
        if not isinstance(entry, AuditLogEntry):
            entry = AuditLogEntry(**data)

        # For audit logs, we might want a simple incrementing ID
        log_id = self.storage.get_next_id()
        # AuditLogEntry doesn't technically have 'id' field in the schema I saw,
        # but FileStorage expects one if we want retrievability by ID.
        # But wait, AuditLogEntry in core/audit_service.py does NOT have 'id'.
        # It has invoice_id, etc.
        # FileStorage.save expects entity to have .model_dump() but it takes entity_id separate.
        # But it doesn't enforce entity.id exists.

        self.storage.save(entry, log_id)
        return entry

    def get_by_invoice(self, invoice_id: int) -> list[Any]:
        """Get logs for an invoice."""
        return [log for log in self.storage.load_all() if log.invoice_id == invoice_id]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Any]:
        """Get all logs."""
        logs = self.storage.load_all()
        return logs[skip : skip + limit]

    def clear(self) -> None:
        """Clear all logs."""
        # This scans all files and deletes them. Expensive but matches 'clear'.
        # Or just delete the directory?
        # FileStorage doesn't expose 'clear' or 'delete_all'.
        # Let's iterate.
        for log in self.storage.load_all():
            # We need ID to delete. load_all returns entities, logic loses generic generic ID.
            # Wait, storage.load_all() returns entities.
            # I should probably expose clearing in FileStorage or loop files directly.
            pass

        # Pragmatic approach: recreate storage or delete dir
        import shutil

        if self.storage.entity_dir.exists():
            shutil.rmtree(self.storage.entity_dir)
            self.storage.entity_dir.mkdir()
            self.storage._next_id = 1
            self.storage._save_meta()
