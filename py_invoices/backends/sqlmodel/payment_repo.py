"""SQLModel payment repository implementation."""

from datetime import datetime

from pydantic_invoices.interfaces import PaymentRepository
from pydantic_invoices.schemas import (
    Payment,
    PaymentCreate,
)
from sqlalchemy import func
from sqlmodel import Session, select

from .models import PaymentDB


class SQLModelPaymentRepository(PaymentRepository):
    """Generic SQLModel implementation for Payment repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: PaymentCreate) -> Payment:
        """Create payment in database."""
        db_payment = PaymentDB(**data.model_dump())
        self.session.add(db_payment)
        self.session.commit()
        self.session.refresh(db_payment)
        return db_payment.to_schema()

    def get_by_id(self, payment_id: int) -> Payment | None:
        """Get payment by ID."""
        db_payment = self.session.get(PaymentDB, payment_id)
        return db_payment.to_schema() if db_payment else None

    def get_by_invoice(self, invoice_id: int) -> list[Payment]:
        """Get all payments for an invoice."""
        stmt = select(PaymentDB).where(PaymentDB.invoice_id == invoice_id)
        db_payments = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_payments]

    def get_total_for_invoice(self, invoice_id: int) -> float:
        """Get total amount paid for an invoice using SQL aggregation."""
        stmt = select(func.sum(PaymentDB.amount)).where(PaymentDB.invoice_id == invoice_id)
        result = self.session.exec(stmt).one()
        return float(result or 0.0)

    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> list[Payment]:
        """Get payments within a date range."""
        stmt = select(PaymentDB).where(
            PaymentDB.payment_date >= start_date,
            PaymentDB.payment_date <= end_date,
        )
        db_payments = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_payments]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Payment]:
        """Get all payments with pagination."""
        stmt = select(PaymentDB).offset(skip).limit(limit)
        db_payments = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_payments]

    def update(self, payment: Payment) -> Payment:
        """Update payment."""
        db_payment = self.session.get(PaymentDB, payment.id)
        if not db_payment:
            raise ValueError(f"Payment {payment.id} not found")

        for key, value in payment.model_dump(exclude={"id"}).items():
            setattr(db_payment, key, value)

        self.session.commit()
        self.session.refresh(db_payment)
        return db_payment.to_schema()

    def delete(self, payment_id: int) -> bool:
        """Delete payment."""
        db_payment = self.session.get(PaymentDB, payment_id)
        if db_payment:
            self.session.delete(db_payment)
            self.session.commit()
            return True
        return False
