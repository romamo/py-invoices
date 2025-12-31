"""In-memory audit repository."""

from typing import Any


class MemoryAuditRepository:
    """In-memory implementation for Audit repository."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._logs: list[Any] = []

    def add(self, entry: Any) -> Any:
        """Add audit log entry."""
        if hasattr(entry, "model_dump"):
            dump = entry.model_dump()
        else:
            dump = entry
        # In a real app we'd convert to schema, but for memory we just store
        self._logs.append(dump)
        return entry

    def get_by_invoice(self, invoice_id: int) -> list[Any]:
        """Get logs for an invoice."""
        return [log for log in self._logs if log.get("invoice_id") == invoice_id]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Any]:
        """Get all logs."""
        return self._logs[skip : skip + limit]

    def clear(self) -> None:
        """Clear all logs."""
        self._logs.clear()
