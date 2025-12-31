"""In-memory invoice repository implementation."""

from typing import Any

from pydantic_invoices.interfaces import InvoiceRepository  # type: ignore[import-untyped]
from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    Invoice,
    InvoiceCreate,
    InvoiceStatus,
)


class MemoryInvoiceRepository(InvoiceRepository):  # type: ignore[misc]
    """In-memory implementation of InvoiceRepository for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._storage: dict[int, Invoice] = {}
        self._next_id = 1

    def create(self, data: InvoiceCreate) -> Invoice:
        """Create a new invoice."""
        # Import InvoiceLine here to avoid circular import
        from pydantic_invoices.schemas import InvoiceLine

        invoice_id = self._next_id

        # Create line items with IDs
        lines_with_ids = [
            InvoiceLine(id=idx + 1, invoice_id=invoice_id, **line.model_dump())
            for idx, line in enumerate(data.lines)
        ]

        # Create invoice with lines
        invoice_data = data.model_dump(exclude={"lines"})
        invoice = Invoice(id=invoice_id, lines=lines_with_ids, **invoice_data)

        self._storage[self._next_id] = invoice
        self._next_id += 1
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID."""
        return self._storage.get(invoice_id)

    def get_by_number(self, number: str) -> Invoice | None:
        """Get invoice by number."""
        for invoice in self._storage.values():
            if invoice.number == number:
                return invoice
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        """Get all invoices with pagination."""
        invoices = list(self._storage.values())
        return invoices[skip : skip + limit]

    def get_by_client(self, client_id: int) -> list[Invoice]:
        """Get all invoices for a client."""
        return [invoice for invoice in self._storage.values() if invoice.client_id == client_id]

    def get_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        """Get invoices by status."""
        return [invoice for invoice in self._storage.values() if invoice.status == status]

    def get_overdue(self) -> list[Invoice]:
        """Get all overdue invoices."""
        return [invoice for invoice in self._storage.values() if invoice.is_overdue]

    def get_summary(self) -> dict[str, Any]:
        """Get invoice statistics summary."""
        invoices = list(self._storage.values())

        total_count = len(invoices)
        paid_count = len([inv for inv in invoices if inv.status == InvoiceStatus.PAID])
        unpaid_count = len([inv for inv in invoices if inv.status == InvoiceStatus.UNPAID])

        # Calculate overdue count
        overdue_count = len([inv for inv in invoices if inv.is_overdue])

        total_amount = sum(inv.total_amount for inv in invoices)
        total_paid = sum(inv.total_paid for inv in invoices)
        total_due = sum(inv.balance_due for inv in invoices if inv.status != InvoiceStatus.PAID)

        return {
            "total_count": total_count,
            "paid_count": paid_count,
            "unpaid_count": unpaid_count,
            "overdue_count": overdue_count,
            "total_amount": total_amount,
            "total_paid": total_paid,
            "total_due": total_due,
        }

    def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        if invoice.id not in self._storage:
            raise ValueError(f"Invoice {invoice.id} not found")

        self._storage[invoice.id] = invoice
        return invoice

    def delete(self, invoice_id: int) -> bool:
        """Delete invoice."""
        if invoice_id in self._storage:
            del self._storage[invoice_id]
            return True
        return False
