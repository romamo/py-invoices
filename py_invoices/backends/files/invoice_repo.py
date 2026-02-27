"""File-based invoice repository."""

from pathlib import Path
from typing import Any

from pydantic_invoices.interfaces import InvoiceRepository
from pydantic_invoices.schemas import Invoice, InvoiceCreate, InvoiceStatus

from .storage import FileStorage


class FileInvoiceRepository(InvoiceRepository):
    """File-based implementation of InvoiceRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[Invoice](
            root_dir, "invoices", Invoice, default_format=file_format
        )

    def create(self, data: InvoiceCreate) -> Invoice:
        """Create a new invoice."""
        # Import InvoiceLine here to avoid circular import
        from pydantic_invoices.schemas import InvoiceLine

        invoice_id = self.storage.get_next_id()

        # Create line items with IDs
        lines_with_ids = [
            InvoiceLine(id=idx + 1, invoice_id=invoice_id, **line.model_dump())
            for idx, line in enumerate(data.lines)
        ]

        # Create invoice with lines
        invoice_data = data.model_dump(exclude={"lines"})
        invoice = Invoice(id=invoice_id, lines=lines_with_ids, **invoice_data)

        self.storage.save(invoice, invoice_id)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID."""
        return self.storage.load(invoice_id)

    def get_by_number(self, number: str) -> Invoice | None:
        """Get invoice by number."""
        invoices = self.storage.load_all()
        for invoice in invoices:
            if invoice.number == number:
                return invoice
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        """Get all invoices with pagination."""
        invoices = self.storage.load_all()
        return invoices[skip : skip + limit]

    def get_by_client(self, client_id: int) -> list[Invoice]:
        """Get all invoices for a client."""
        return [inv for inv in self.storage.load_all() if inv.client_id == client_id]

    def get_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        """Get invoices by status."""
        return [inv for inv in self.storage.load_all() if inv.status == status]

    def get_overdue(self) -> list[Invoice]:
        """Get all overdue invoices."""
        return [inv for inv in self.storage.load_all() if inv.is_overdue]

    def get_summary(self) -> dict[str, Any]:
        """Get invoice statistics summary."""
        invoices = self.storage.load_all()

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
        existing = self.storage.load(invoice.id)
        if not existing:
            raise ValueError(f"Invoice {invoice.id} not found")

        self.storage.save(invoice, invoice.id)
        return invoice

    def delete(self, invoice_id: int) -> bool:
        """Delete invoice."""
        return self.storage.delete(invoice_id)
