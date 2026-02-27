"""Credit Note Service.

Provides functionality for creating and managing credit notes.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_invoices.schemas import (
    Invoice,
    InvoiceCreate,
    InvoiceLineCreate,
    InvoiceStatus,
    InvoiceType,
)

if TYPE_CHECKING:
    from pydantic_invoices.interfaces import InvoiceRepository

    from py_invoices.core.numbering_service import NumberingService


class CreditService:
    """Service for handling Credit Notes."""

    def __init__(
        self,
        invoice_repo: "InvoiceRepository",
        numbering_service: "NumberingService",
    ):
        """Initialize Credit Service.

        Args:
            invoice_repo: Repository for invoices
            numbering_service: Service for generating numbers
        """
        self.invoice_repo = invoice_repo
        self.numbering_service = numbering_service

    def create_credit_note(
        self,
        original_invoice: "Invoice",
        reason: str | None = None,
        lines: list[InvoiceLineCreate] | None = None,
        refund_lines_indices: list[int] | None = None,
    ) -> Invoice:
        """Create a Credit Note for a given invoice.

        Args:
            original_invoice: The source invoice to credit.
            reason: Reason for the credit note.
            lines: Optional list of lines for partial credit.
                   If None provided, defaults to full credit (all lines duplicated).
            refund_lines_indices: Optional list of indices from original lines to refund.
                                  Used if `lines` is None to credit specific lines.

        Returns:
            The created Credit Note (Invoice object).

        Raises:
            ValueError: If original invoice is not in a valid state.
        """
        if original_invoice.status == InvoiceStatus.DRAFT:
            raise ValueError("Cannot bug credit note for a DRAFT invoice. Just delete or edit it.")

        # Prepare Credit Note Lines
        cn_lines: list[InvoiceLineCreate] = []

        if lines:
            # explicit lines provided
            cn_lines = lines
        elif refund_lines_indices:
            # credit specific lines from original
            for idx in refund_lines_indices:
                 if 0 <= idx < len(original_invoice.lines):
                     orig_line = original_invoice.lines[idx]
                     cn_lines.append(
                        InvoiceLineCreate(
                            description=f"Refund: {orig_line.description}",
                            quantity=orig_line.quantity,
                            # Usually negative? Or keep positive?
                            # Standard practice: Credit Note usually has positive amounts that
                            # reduce balance
                            # But visuals are negative.
                            # Let's stick to positive quantities and amounts for now,
                            # and let the "InvoiceType=CREDIT_NOTE" handle the accounting logic
                            # (subtraction).
                            unit_price=orig_line.unit_price
                        )
                     )
        else:
            # Full Credit
            for line in original_invoice.lines:
                cn_lines.append(
                    InvoiceLineCreate(
                        description=line.description,
                        quantity=line.quantity,
                        unit_price=line.unit_price,
                    )
                )


        # Generate Number
        # Use a specific series prefix for CN? e.g. CN-2025-0001
        # For simplicity, we use the standard numbering but users can configure prefix
        # in NumberingService
        # Here we just generate next number and force CN prefix if standard.
        inv_number = self.numbering_service.generate_number()
        cn_number = inv_number.replace("INV-", "CN-")
        if cn_number == inv_number:
             # If custom format didn't have INV-, prepend CN-
             cn_number = f"CN-{inv_number}"

        cn_data = InvoiceCreate(
            number=cn_number,
            issue_date=datetime.now(),
            status=InvoiceStatus.DRAFT, # Start as draft
            type=InvoiceType.CREDIT_NOTE,
            original_invoice_id=original_invoice.id,
            reason=reason,
            client_id=original_invoice.client_id,
            company_id=original_invoice.company_id,
            lines=cn_lines,
            due_date=original_invoice.due_date, # Or immediate?
            payment_terms="Immediate",
            # Snapshots handled by repo or manually?
            # Ideally repo handles snapshotting on creation if not provided,
            # but for CN we want to match original exactly usually.
            client_name_snapshot=original_invoice.client_name_snapshot,
            client_address_snapshot=original_invoice.client_address_snapshot,
            client_tax_id_snapshot=original_invoice.client_tax_id_snapshot,
            template_name=original_invoice.template_name,
        )

        return self.invoice_repo.create(cn_data)
