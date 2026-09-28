"""SQLModel audit repository implementation."""

from sqlalchemy import delete
from sqlmodel import Session, col, select

from py_invoices.core.audit_service import AuditLogEntry
from py_invoices.plugins.base import AuditRepository

from .models import AuditLogDB


class SQLModelAuditRepository(AuditRepository):
    """Generic SQLModel implementation for Audit repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Add audit log entry to database."""
        db_entry = AuditLogDB(**entry.model_dump(include=set(AuditLogDB.model_fields)))
        self.session.add(db_entry)
        self.session.commit()
        self.session.refresh(db_entry)
        return db_entry.to_schema()

    def get_by_invoice(self, invoice_id: int) -> list[AuditLogEntry]:
        """Get audit logs for a specific invoice."""
        stmt = (
            select(AuditLogDB)
            .where(AuditLogDB.invoice_id == invoice_id)
            .order_by(col(AuditLogDB.id))
        )
        db_entries = self.session.exec(stmt).all()
        return [e.to_schema() for e in db_entries]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AuditLogEntry]:
        """Get all audit logs with pagination."""
        # Oldest first, like the other backends; the id order also keeps paging stable
        stmt = select(AuditLogDB).order_by(col(AuditLogDB.id)).offset(skip).limit(limit)
        db_entries = self.session.exec(stmt).all()
        return [e.to_schema() for e in db_entries]

    def clear(self) -> None:
        """Clear all audit logs."""
        self.session.exec(delete(AuditLogDB))
        self.session.commit()
