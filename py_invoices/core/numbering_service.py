import re
import string
from datetime import date
from typing import Any

from pydantic_invoices.interfaces import InvoiceRepository

from py_invoices.core.paging import iter_all

INVOICE_NUMBER_FORMAT = "INV-{year}-{sequence:04d}"
CREDIT_NOTE_NUMBER_FORMAT = "CN-{year}-{sequence:04d}"


class NumberingService:
    """Service for generating sequential document numbers.

    With a repository, the next sequence continues from the highest number already
    issued in the same series (the format with its fixed parts filled in), so each
    series and year counts independently and deleted or custom numbers never cause
    duplicates.
    """

    def __init__(
        self,
        format_template: str = INVOICE_NUMBER_FORMAT,
        invoice_repo: InvoiceRepository | None = None,
    ):
        """Initialize numbering service.

        Args:
            format_template: Format string for numbers. Placeholders:
                - {year}: Year (4 digits); the sequence restarts every year
                - {month}, {day}: Current month and day
                - {sequence}: Sequential number (use :04d for padding)
                - any other name: a value passed to generate_number
            invoice_repo: Optional repository to derive the next sequence from.
        """
        if "{sequence" not in format_template:
            raise ValueError(f"Number format must contain {{sequence}}: {format_template!r}")
        self.format_template = format_template
        self.invoice_repo = invoice_repo

    def generate_number(
        self,
        sequence: int | None = None,
        year: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a number.

        Args:
            sequence: Sequential number. If None, the next one is taken from the repository.
            year: Year to use (defaults to current year)
            **kwargs: Additional format variables

        Example:
            >>> NumberingService().generate_number(42, year=2024)
            'INV-2024-0042'
        """
        today = date.today()
        target_year = year or today.year
        if sequence is None:
            sequence = self.next_sequence(target_year, **kwargs)

        return self.format_template.format(
            year=target_year, month=today.month, day=today.day, sequence=sequence, **kwargs
        )

    def next_sequence(self, year: int, **kwargs: Any) -> int:
        """One more than the highest sequence issued in this series for the year."""
        if self.invoice_repo is None:
            raise ValueError("sequence must be provided if invoice_repo is not set")
        pattern = self._series_pattern(year, kwargs)
        sequences = (
            int(match["sequence"])
            for invoice in iter_all(self.invoice_repo)
            if (match := pattern.fullmatch(invoice.number))
        )
        return max(sequences, default=0) + 1

    def _series_pattern(self, year: int, fixed: dict[str, Any]) -> re.Pattern[str]:
        """Regex matching numbers of this series; month and day may vary within the year."""
        parts = []
        for literal, field, spec, _ in string.Formatter().parse(self.format_template):
            parts.append(re.escape(literal))
            if field is None:
                continue
            if field == "sequence":
                parts.append(r"(?P<sequence>\d+)")
            elif field == "year":
                parts.append(re.escape(format(year, spec or "")))
            elif field in fixed:
                parts.append(re.escape(format(fixed[field], spec or "")))
            else:
                parts.append(r"\d+")
        return re.compile("".join(parts))

    def parse_number(self, invoice_number: str) -> dict[str, Any]:
        """Split a number in the default "PREFIX-YYYY-NNNN" shape into its components."""
        parts = invoice_number.split("-")
        if len(parts) >= 3:
            return {
                "prefix": parts[0],
                "year": int(parts[1]) if parts[1].isdigit() else None,
                "sequence": int(parts[2]) if parts[2].isdigit() else None,
            }
        return {"raw": invoice_number}
