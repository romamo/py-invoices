"""Audit logging service.

Provides audit trail functionality for tracking invoice changes.
Note: This is a simplified version. For production use with database persistence,
integrate with your storage backend's audit log repository.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pydantic_invoices.schemas import Invoice, Payment  # type: ignore[import-untyped]


class AuditLogEntry(BaseModel):
    """Audit log entry schema."""

    timestamp: datetime = Field(default_factory=datetime.now)
    invoice_id: int | None = None
    invoice_number: str | None = None
    action: str = Field(..., description="Action performed (e.g., CREATED, UPDATED, PAID)")
    old_value: str | None = None
    new_value: str | None = None
    notes: str | None = None
    user: str | None = None

    model_config = {"extra": "allow"}


class AuditService:
    """Service for logging audit trail entries.

    Provides high-level methods for logging invoice lifecycle events.
    """

    def __init__(self, audit_repo: Any | None = None) -> None:
        """Initialize audit service.

        Args:
            audit_repo: Optional repository for database-backed audit logs.
        """
        self.audit_repo = audit_repo
        self._logs: list[AuditLogEntry] = []

    def log_invoice_created(
        self,
        invoice: "Invoice | int",
        user_id: str | None = None,
        **kwargs: Any,
    ) -> AuditLogEntry:
        """Log invoice creation.

        Args:
            invoice: Invoice object or ID
            user_id: ID of the user who performed the action
            **kwargs: Backward compatibility for raw IDs/numbers/amounts
        """
        if isinstance(invoice, int):
            # Legacy support
            invoice_id = invoice
            invoice_number = kwargs.get("invoice_number", "unknown")
            total_amount = kwargs.get("total_amount", 0.0)
            client_name = kwargs.get("client_name", "unknown")
            user = user_id or kwargs.get("user")
        else:
            invoice_id = invoice.id
            invoice_number = invoice.number
            total_amount = invoice.total_amount
            client_name = invoice.client_name_snapshot or "unknown"
            user = user_id

        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="CREATED",
            new_value=f"Invoice {invoice_number} created for {client_name}",
            notes=f"Total: ${total_amount:.2f}",
            user=user,
        )
        self._logs.append(entry)
        if self.audit_repo:
            self.audit_repo.add(entry)
        return entry

    def log_status_changed(
        self,
        invoice: "Invoice | int",
        new_status: str | None = None,
        old_status: str | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> AuditLogEntry:
        """Log invoice status change."""
        if isinstance(invoice, int):
            invoice_id = invoice
            invoice_number = kwargs.get("invoice_number", "unknown")
            user = user_id or kwargs.get("user")
        else:
            invoice_id = invoice.id
            invoice_number = invoice.number
            old_status = old_status or str(invoice.status)
            user = user_id

        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="STATUS_CHANGED",
            old_value=old_status,
            new_value=new_status,
            user=user,
        )
        self._logs.append(entry)
        if self.audit_repo:
            self.audit_repo.add(entry)
        return entry

    def log_payment_added(
        self,
        invoice: "Invoice | int",
        payment: "Payment | float | None" = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> AuditLogEntry:
        """Log payment addition."""
        if isinstance(invoice, int):
            invoice_id = invoice
            invoice_number = kwargs.get("invoice_number", "unknown")
            payment_amount = payment if isinstance(payment, (int, float)) else 0.0
            old_balance = kwargs.get("old_balance", 0.0)
            new_balance = kwargs.get("new_balance", 0.0)
            payment_method = kwargs.get("payment_method")
            user = user_id or kwargs.get("user")
        else:
            from pydantic_invoices.schemas import Payment

            invoice_id = invoice.id
            invoice_number = invoice.number
            user = user_id

            if isinstance(payment, Payment):
                payment_amount = payment.amount
                payment_method = payment.payment_method
                old_balance = invoice.balance_due + payment_amount
                new_balance = invoice.balance_due
            else:
                payment_amount = payment if isinstance(payment, (int, float)) else 0.0
                old_balance = invoice.balance_due + payment_amount
                new_balance = invoice.balance_due
                payment_method = kwargs.get("payment_method")

        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="PAYMENT_ADDED",
            old_value=f"Balance: ${old_balance:.2f}",
            new_value=f"Payment: ${payment_amount:.2f}, New Balance: ${new_balance:.2f}",
            notes=f"Method: {payment_method}" if payment_method else None,
            user=user,
        )
        self._logs.append(entry)
        if self.audit_repo:
            self.audit_repo.add(entry)
        return entry

    def log_invoice_cloned(
        self,
        invoice_id: int,
        invoice_number: str,
        original_number: str,
        total_amount: float,
        user: str | None = None,
    ) -> AuditLogEntry:
        """Log invoice cloning.

        Args:
            invoice_id: New invoice ID
            invoice_number: New invoice number
            original_number: Original invoice number
            total_amount: Total amount
            user: User who cloned the invoice

        Returns:
            Created audit log entry
        """
        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="CLONED",
            new_value=f"Cloned from {original_number}",
            notes=f"Total: ${total_amount:.2f}",
            user=user,
        )
        self._logs.append(entry)
        if self.audit_repo:
            self.audit_repo.add(entry)
        return entry

    def get_logs(
        self,
        invoice_id: int | None = None,
        invoice_number: str | None = None,
        action: str | None = None,
    ) -> list[AuditLogEntry]:
        """Get audit logs with optional filtering.

        Args:
            invoice_id: Filter by invoice ID
            invoice_number: Filter by invoice number
            action: Filter by action type

        Returns:
            List of matching audit log entries
        """
        if self.audit_repo:
            # If we have a repo, we might want to fetch from it instead of just in-memory
            # For now, we'll merge or just return memory if they are sync
            # To be more robust, we should probably query the repo
            db_logs = (
                self.audit_repo.get_by_invoice(invoice_id)
                if invoice_id
                else self.audit_repo.get_all()
            )
            return cast(list[AuditLogEntry], db_logs)

        logs = self._logs

        if invoice_id is not None:
            logs = [log for log in logs if log.invoice_id == invoice_id]

        if invoice_number is not None:
            logs = [log for log in logs if log.invoice_number == invoice_number]

        if action is not None:
            logs = [log for log in logs if log.action == action]

        return logs

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of audit logs."""
        summary: dict[str, Any] = {
            "total_entries": len(self._logs),
            "actions_count": {},
            "invoices_affected": set(),
        }
        actions_count: dict[str, int] = summary["actions_count"]
        invoices_affected: set[int] = summary["invoices_affected"]

        for entry in self._logs:
            actions_count[entry.action] = actions_count.get(entry.action, 0) + 1
            if entry.invoice_id:
                invoices_affected.add(entry.invoice_id)

        summary["invoices_affected"] = list(invoices_affected)
        return summary

    def clear_logs(self) -> None:
        """Clear all audit logs (useful for testing)."""
        self._logs.clear()
        if self.audit_repo:
            self.audit_repo.clear()
