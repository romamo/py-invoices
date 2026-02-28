from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic_invoices.interfaces import InvoiceRepository


class NumberingService:
    """Service for generating sequential invoice numbers.

    This service provides sequential numbering, optionally integrated
    with an InvoiceRepository to automatically determine the next sequence.
    """

    def __init__(
        self,
        format_template: str = "INV-{year}-{sequence:04d}",
        invoice_repo: "InvoiceRepository | None" = None,
    ):
        """Initialize numbering service.

        Args:
            format_template: Format string for invoice numbers.
                Available placeholders:
                - {year}: Current year (4 digits)
                - {month}: Current month (2 digits)
                - {day}: Current day (2 digits)
                - {sequence}: Sequential number (use :04d for padding)
            invoice_repo: Optional repository to fetch the last sequence from.
        """
        self.format_template = format_template
        self.invoice_repo = invoice_repo

    def generate_number(
        self,
        sequence: int | None = None,
        year: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate an invoice number.

        Args:
            sequence: Sequential number. If None and invoice_repo is set,
                it will be determined automatically from the repository.
            year: Year to use (defaults to current year)
            **kwargs: Additional format variables

        Returns:
            Formatted invoice number

        Example:
            >>> service = NumberingService("INV-{year}-{sequence:04d}")
            >>> service.generate_number(1)
            'INV-2025-0001'
            >>> service.generate_number(42, year=2024)
            'INV-2024-0042'
        """
        now = datetime.now()
        target_year = year or now.year

        # Handle auto-sequencing
        if sequence is None:
            if self.invoice_repo:
                summary = self.invoice_repo.get_summary()
                sequence = summary.total_count + 1
            else:
                raise ValueError("sequence must be provided if invoice_repo is not set")

        format_vars = {
            "year": target_year,
            "month": now.month,
            "day": now.day,
            "sequence": sequence,
            **kwargs,
        }

        return self.format_template.format(**format_vars)

    def parse_number(self, invoice_number: str) -> dict[str, Any]:
        """Parse an invoice number to extract components.

        This is a basic implementation that works with the default format.
        Override this method for custom parsing logic.

        Args:
            invoice_number: Invoice number to parse

        Returns:
            Dictionary with extracted components
        """
        # Basic parsing for default format "INV-YYYY-NNNN"
        parts = invoice_number.split("-")
        if len(parts) >= 3:
            return {
                "prefix": parts[0],
                "year": int(parts[1]) if parts[1].isdigit() else None,
                "sequence": int(parts[2]) if parts[2].isdigit() else None,
            }
        return {"raw": invoice_number}
