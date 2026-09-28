"""In-memory invoice repository implementation."""

from pydantic_invoices.interfaces import InvoiceRepository, PaymentRepository
from pydantic_invoices.schemas import (
    Invoice,
    InvoiceCreate,
    InvoiceStatus,
    InvoiceSummary,
)

from py_invoices.core.summary import summarize_invoices

from .ids import IdSequence


class MemoryInvoiceRepository(InvoiceRepository):
    """In-memory implementation of InvoiceRepository for testing."""

    def __init__(self, payment_repo: PaymentRepository | None = None) -> None:
        """Initialize in-memory storage; payments are read from payment_repo when given."""
        self._payment_repo = payment_repo
        self._storage: dict[int, Invoice] = {}
        self._ids = IdSequence()

    def create(self, data: InvoiceCreate) -> Invoice:
        """Create a new invoice."""
        # Import InvoiceLine here to avoid circular import
        from pydantic_invoices.schemas import InvoiceLine

        invoice_id = self._ids.next()

        # Create line items with IDs
        lines_with_ids = [
            InvoiceLine(id=idx + 1, invoice_id=invoice_id, **dict(line))
            for idx, line in enumerate(data.lines)
        ]

        # Create invoice with lines
        invoice_data = data.model_dump(exclude={"lines"})
        invoice = Invoice(id=invoice_id, lines=lines_with_ids, **invoice_data)

        self._storage[invoice_id] = invoice
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID."""
        invoice = self._storage.get(invoice_id)
        return self._with_payments(invoice) if invoice else None

    def get_by_number(self, number: str) -> Invoice | None:
        """Get invoice by number."""
        for invoice in self._storage.values():
            if invoice.number == number:
                return self._with_payments(invoice)
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        """Get all invoices with pagination."""
        invoices = list(self._storage.values())[skip : skip + limit]
        return [self._with_payments(inv) for inv in invoices]

    def get_by_client(self, client_id: int) -> list[Invoice]:
        """Get all invoices for a client."""
        return [
            self._with_payments(inv) for inv in self._storage.values() if inv.client_id == client_id
        ]

    def get_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        """Get invoices by status."""
        return [self._with_payments(inv) for inv in self._storage.values() if inv.status == status]

    def get_overdue(self) -> list[Invoice]:
        """Get all overdue invoices."""
        return [self._with_payments(inv) for inv in self._storage.values() if inv.is_overdue]

    def get_summary(self) -> InvoiceSummary:
        """Get invoice statistics summary."""
        return summarize_invoices(self._with_payments(inv) for inv in self._storage.values())

    def _with_payments(self, invoice: Invoice) -> Invoice:
        """Attach payments recorded in the payment repository, as the SQL backend does."""
        if self._payment_repo is None:
            return invoice
        return invoice.model_copy(
            update={"payments": self._payment_repo.get_by_invoice(invoice.id)}
        )

    def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        if invoice.id not in self._storage:
            raise ValueError(f"Invoice {invoice.id} not found")

        self._storage[invoice.id] = invoice.model_copy(update={"payments": []})
        return self._with_payments(invoice)

    def delete(self, invoice_id: int) -> bool:
        """Delete invoice."""
        if invoice_id in self._storage:
            del self._storage[invoice_id]
            return True
        return False
