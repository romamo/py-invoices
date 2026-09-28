"""File-based invoice repository."""

from pathlib import Path

from pydantic_invoices.interfaces import InvoiceRepository, PaymentRepository
from pydantic_invoices.schemas import Invoice, InvoiceCreate, InvoiceStatus, InvoiceSummary

from py_invoices.core.summary import summarize_invoices

from .storage import FileStorage


class FileInvoiceRepository(InvoiceRepository):
    """File-based implementation of InvoiceRepository."""

    def __init__(
        self,
        root_dir: str | Path,
        file_format: str = "json",
        payment_repo: PaymentRepository | None = None,
    ) -> None:
        """Initialize file repository; payments are read from payment_repo when given."""
        self._payment_repo = payment_repo
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
            InvoiceLine(id=idx + 1, invoice_id=invoice_id, **dict(line))
            for idx, line in enumerate(data.lines)
        ]

        # Create invoice with lines
        invoice_data = data.model_dump(exclude={"lines"})
        invoice = Invoice(id=invoice_id, lines=lines_with_ids, **invoice_data)

        self.storage.save(invoice, invoice_id)
        return invoice

    def get_by_id(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID."""
        invoice = self.storage.load(invoice_id)
        return self._with_payments(invoice) if invoice else None

    def get_by_number(self, number: str) -> Invoice | None:
        """Get invoice by number."""
        invoices = self.storage.load_all()
        for invoice in invoices:
            if invoice.number == number:
                return self._with_payments(invoice)
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Invoice]:
        """Get all invoices with pagination."""
        invoices = self.storage.load_all()[skip : skip + limit]
        return [self._with_payments(inv) for inv in invoices]

    def get_by_client(self, client_id: int) -> list[Invoice]:
        """Get all invoices for a client."""
        return [
            self._with_payments(inv)
            for inv in self.storage.load_all()
            if inv.client_id == client_id
        ]

    def get_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        """Get invoices by status."""
        return [self._with_payments(inv) for inv in self.storage.load_all() if inv.status == status]

    def get_overdue(self) -> list[Invoice]:
        """Get all overdue invoices."""
        return [self._with_payments(inv) for inv in self.storage.load_all() if inv.is_overdue]

    def get_summary(self) -> InvoiceSummary:
        """Get invoice statistics summary."""
        return summarize_invoices(self._with_payments(inv) for inv in self.storage.load_all())

    def _with_payments(self, invoice: Invoice) -> Invoice:
        """Attach payments recorded in the payment repository, as the SQL backend does."""
        if self._payment_repo is None:
            return invoice
        return invoice.model_copy(
            update={"payments": self._payment_repo.get_by_invoice(invoice.id)}
        )

    def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        existing = self.storage.load(invoice.id)
        if not existing:
            raise ValueError(f"Invoice {invoice.id} not found")

        self.storage.save(invoice.model_copy(update={"payments": []}), invoice.id)
        return self._with_payments(invoice)

    def delete(self, invoice_id: int) -> bool:
        """Delete invoice."""
        return self.storage.delete(invoice_id)
