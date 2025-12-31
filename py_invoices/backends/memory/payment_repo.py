"""In-memory payment repository implementation."""

from datetime import datetime

from pydantic_invoices.interfaces import PaymentRepository  # type: ignore[import-untyped]
from pydantic_invoices.schemas import Payment, PaymentCreate  # type: ignore[import-untyped]


class MemoryPaymentRepository(PaymentRepository):  # type: ignore[misc]
    """In-memory implementation of PaymentRepository for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._storage: dict[int, Payment] = {}
        self._next_id = 1

    def create(self, data: PaymentCreate) -> Payment:
        """Create a new payment."""
        payment = Payment(id=self._next_id, **data.model_dump())
        self._storage[self._next_id] = payment
        self._next_id += 1
        return payment

    def get_by_id(self, payment_id: int) -> Payment | None:
        """Get payment by ID."""
        return self._storage.get(payment_id)

    def get_by_invoice(self, invoice_id: int) -> list[Payment]:
        """Get all payments for an invoice."""
        return [payment for payment in self._storage.values() if payment.invoice_id == invoice_id]

    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> list[Payment]:
        """Get payments within a date range."""
        return [
            payment
            for payment in self._storage.values()
            if start_date <= payment.payment_date <= end_date
        ]

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Payment]:
        """Get all payments with pagination."""
        payments = list(self._storage.values())
        return payments[skip : skip + limit]

    def get_total_for_invoice(self, invoice_id: int) -> float:
        """Get total amount paid for an invoice."""
        return float(sum(p.amount for p in self._storage.values() if p.invoice_id == invoice_id))

    def update(self, payment: Payment) -> Payment:
        """Update payment."""
        if payment.id not in self._storage:
            raise ValueError(f"Payment {payment.id} not found")

        self._storage[payment.id] = payment
        return payment

    def delete(self, payment_id: int) -> bool:
        """Delete payment."""
        if payment_id in self._storage:
            del self._storage[payment_id]
            return True
        return False
