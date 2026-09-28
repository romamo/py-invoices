"""SQLModel invoice repository implementation."""

from datetime import date
from decimal import Decimal

from pydantic_invoices.interfaces import InvoiceRepository
from pydantic_invoices.schemas import (
    Invoice,
    InvoiceCreate,
    InvoiceStatus,
    InvoiceSummary,
)
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from py_invoices.core.summary import summarize_invoices

from .models import InvoiceDB, InvoiceLineDB, money_columns

_WITH_CHILDREN = (
    selectinload(InvoiceDB.lines),  # type: ignore[arg-type]
    selectinload(InvoiceDB.payments),  # type: ignore[arg-type]
)


class SQLModelInvoiceRepository(InvoiceRepository):
    """Generic SQLModel implementation for Invoice repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: InvoiceCreate) -> Invoice:
        """Create invoice in database."""
        # Create invoice without lines first
        invoice_data = data.model_dump(exclude={"lines"})
        db_invoice = InvoiceDB(**invoice_data)

        # Add invoice to session and flush to get ID
        self.session.add(db_invoice)
        self.session.flush()  # Get ID without committing

        for line_data in data.lines:
            unit_price, currency = money_columns(line_data.unit_price)
            db_line = InvoiceLineDB(
                invoice_id=db_invoice.id,
                description=line_data.description,
                quantity=line_data.quantity,
                unit_price=unit_price,
                currency=currency,
                tax_rate=Decimal(str(line_data.tax_rate or 0)),
            )
            self.session.add(db_line)

        self.session.commit()
        self.session.refresh(db_invoice)
        return db_invoice.to_schema()

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID."""
        db_invoice = self.session.get(InvoiceDB, invoice_id)
        return db_invoice.to_schema() if db_invoice else None

    def get_by_number(self, number: str) -> Invoice | None:
        """Get invoice by number."""
        stmt = select(InvoiceDB).where(InvoiceDB.number == number)
        db_invoice = self.session.exec(stmt).first()
        return db_invoice.to_schema() if db_invoice else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        """Get all invoices with pagination."""
        stmt = select(InvoiceDB).order_by(col(InvoiceDB.id)).offset(skip).limit(limit)
        db_invoices = self.session.exec(stmt).all()
        return [inv.to_schema() for inv in db_invoices]

    def get_by_client(self, client_id: int) -> list[Invoice]:
        """Get all invoices for a client."""
        stmt = select(InvoiceDB).where(InvoiceDB.client_id == client_id)
        db_invoices = self.session.exec(stmt).all()
        return [inv.to_schema() for inv in db_invoices]

    def get_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        """Get invoices by status."""
        stmt = select(InvoiceDB).where(InvoiceDB.status == status)
        db_invoices = self.session.exec(stmt).all()
        return [inv.to_schema() for inv in db_invoices]

    def get_overdue(self) -> list[Invoice]:
        """Get all overdue invoices."""
        today = date.today()
        # Invoices that are NOT fully paid or settled, and are past due
        closed_statuses = (
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
            InvoiceStatus.CREDITED,
        )
        stmt = select(InvoiceDB).where(
            InvoiceDB.status.notin_(closed_statuses),  # type: ignore[attr-defined]
            InvoiceDB.due_date.is_not(None) & (InvoiceDB.due_date < today),  # type: ignore[union-attr, operator]
        )
        db_invoices = self.session.exec(stmt).all()
        return [inv.to_schema() for inv in db_invoices]

    def get_summary(self) -> InvoiceSummary:
        """Get invoice statistics summary (same rules as every other backend)."""
        stmt = select(InvoiceDB).options(*_WITH_CHILDREN)
        return summarize_invoices(inv.to_schema() for inv in self.session.exec(stmt).all())

    def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        db_invoice = self.session.get(InvoiceDB, invoice.id)
        if not db_invoice:
            raise ValueError(f"Invoice {invoice.id} not found")

        # Update fields (excluding relationships and non-DB fields)
        exclude_fields = {"id", "lines", "payments", "audit_logs"}
        update_data = invoice.model_dump(mode="python", exclude=exclude_fields)

        # Only update fields that exist in the DB model
        db_fields = set(InvoiceDB.model_fields.keys())
        for key, value in update_data.items():
            if key in db_fields:
                setattr(db_invoice, key, value)

        self.session.commit()
        self.session.refresh(db_invoice)
        return db_invoice.to_schema()

    def delete(self, invoice_id: int) -> bool:
        """Delete invoice."""
        db_invoice = self.session.get(InvoiceDB, invoice_id)
        if db_invoice:
            self.session.delete(db_invoice)
            self.session.commit()
            return True
        return False
