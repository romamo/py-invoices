"""File-based payment repository."""

from pathlib import Path
from datetime import datetime

from pydantic_invoices.interfaces import PaymentRepository
from pydantic_invoices.schemas import Payment, PaymentCreate

from .storage import FileStorage


class FilePaymentRepository(PaymentRepository):
    """File-based implementation of PaymentRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[Payment](
            root_dir, "payments", Payment, default_format=file_format
        )

    def create(self, data: PaymentCreate) -> Payment:
        """Create a new payment."""
        payment_id = self.storage.get_next_id()
        payment = Payment(id=payment_id, **data.model_dump())
        self.storage.save(payment, payment_id)
        return payment

    def get_by_id(self, payment_id: int) -> Payment | None:
        """Get payment by ID."""
        return self.storage.load(payment_id)

    def get_by_invoice(self, invoice_id: int) -> list[Payment]:
        """Get payments for an invoice."""
        payments = self.storage.load_all()
        return [p for p in payments if p.invoice_id == invoice_id]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Payment]:
        """Get all payments with pagination."""
        payments = self.storage.load_all()
        return payments[skip : skip + limit]

    def get_total_for_invoice(self, invoice_id: int) -> float:
        """Get total amount paid for an invoice."""
        payments = self.get_by_invoice(invoice_id)
        return float(sum(p.amount for p in payments))

    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> list[Payment]:
        """Get payments within a date range."""
        return [
            payment
            for payment in self.storage.load_all()
            if start_date <= payment.payment_date <= end_date
        ]

    def update(self, payment: Payment) -> Payment:
        """Update payment."""
        existing = self.storage.load(payment.id)
        if not existing:
            raise ValueError(f"Payment {payment.id} not found")

        self.storage.save(payment, payment.id)
        return payment

    def delete(self, payment_id: int) -> bool:
        """Delete payment."""
        return self.storage.delete(payment_id)
