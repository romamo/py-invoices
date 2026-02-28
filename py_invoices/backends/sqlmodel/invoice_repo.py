"""SQLModel invoice repository implementation."""

from datetime import date

from pydantic_invoices.interfaces import InvoiceRepository
from pydantic_invoices.schemas import (
    Invoice,
    InvoiceCreate,
    InvoiceStatus,
    InvoiceSummary,
)
from pydantic_invoices.vo import Money
from sqlalchemy import func
from sqlmodel import Session, select

from .models import InvoiceDB, InvoiceLineDB, PaymentDB


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

        # Create line items
        for line_data in data.lines:
            db_line = InvoiceLineDB(invoice_id=db_invoice.id, **line_data.model_dump())
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
        stmt = select(InvoiceDB).offset(skip).limit(limit)
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
        """Get invoice statistics summary using SQL aggregation."""
        # Counts
        total_count = self.session.exec(select(func.count(InvoiceDB.id))).one()  # type: ignore[arg-type]
        paid_count = self.session.exec(
            select(func.count(InvoiceDB.id)).where(InvoiceDB.status == InvoiceStatus.PAID)  # type: ignore[arg-type]
        ).one()
        unpaid_count = self.session.exec(
            select(func.count(InvoiceDB.id)).where(InvoiceDB.status == InvoiceStatus.UNPAID)  # type: ignore[arg-type]
        ).one()

        today = date.today()
        closed_statuses = (
            InvoiceStatus.PAID,
            InvoiceStatus.CANCELLED,
            InvoiceStatus.REFUNDED,
            InvoiceStatus.CREDITED,
        )
        overdue_count = self.session.exec(
            select(func.count(InvoiceDB.id)).where(  # type: ignore[arg-type]
                InvoiceDB.status.notin_(closed_statuses),  # type: ignore[attr-defined]
                InvoiceDB.due_date.is_not(None) & (InvoiceDB.due_date < today),  # type: ignore[union-attr, operator]
            )
        ).one()

        # Amounts — SQL aggregation returns raw float/Decimal; wrap in Money
        stmt_amount = select(func.sum(InvoiceLineDB.quantity * InvoiceLineDB.unit_price))
        raw_amount = self.session.exec(stmt_amount).one() or 0
        raw_paid = self.session.exec(select(func.sum(PaymentDB.amount))).one() or 0
        raw_due = float(raw_amount) - float(raw_paid)

        return InvoiceSummary(
            total_count=total_count,
            paid_count=paid_count,
            unpaid_count=unpaid_count,
            overdue_count=overdue_count,
            total_amount=Money(raw_amount),
            total_paid=Money(raw_paid),
            total_due=Money(raw_due),
        )

    def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        db_invoice = self.session.get(InvoiceDB, invoice.id)
        if not db_invoice:
            raise ValueError(f"Invoice {invoice.id} not found")

        # Update fields (excluding relationships and non-DB fields)
        exclude_fields = {"id", "lines", "payments", "audit_logs", "payment_note_ids"}
        update_data = invoice.model_dump(exclude=exclude_fields)

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
