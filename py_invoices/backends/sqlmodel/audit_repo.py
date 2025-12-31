"""SQLModel audit repository implementation."""

from typing import Any

from sqlalchemy import desc
from sqlmodel import Session, select

from .models import AuditLogDB


class SQLModelAuditRepository:
    """Generic SQLModel implementation for Audit repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def add(self, data: Any) -> Any:
        """Add audit log entry to database.

        Args:
            data: AuditLogEntry schema or dict
        """
        if hasattr(data, "model_dump"):
            dump = data.model_dump()
        else:
            dump = data

        db_entry = AuditLogDB(**dump)
        self.session.add(db_entry)
        self.session.commit()
        self.session.refresh(db_entry)
        return db_entry.to_schema()

    def get_by_invoice(self, invoice_id: int) -> list[Any]:
        """Get audit logs for a specific invoice."""
        stmt = (
            select(AuditLogDB)
            .where(AuditLogDB.invoice_id == invoice_id)
            .order_by(desc(AuditLogDB.timestamp))  # type: ignore[arg-type]
        )
        db_entries = self.session.exec(stmt).all()
        return [e.to_schema() for e in db_entries]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Any]:
        """Get all audit logs with pagination."""
        stmt = (
            select(AuditLogDB)
            .offset(skip)
            .limit(limit)
            .order_by(desc(AuditLogDB.timestamp))  # type: ignore[arg-type]
        )
        db_entries = self.session.exec(stmt).all()
        return [e.to_schema() for e in db_entries]

    def clear(self) -> None:
        """Clear all audit logs."""
        stmt = select(AuditLogDB)
        db_entries = self.session.exec(stmt).all()
        for entry in db_entries:
            self.session.delete(entry)
        self.session.commit()
