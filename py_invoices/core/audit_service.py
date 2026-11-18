"""Audit logging service.

Provides audit trail functionality for tracking invoice changes.
Note: This is a simplified version. For production use with database persistence,
integrate with your storage backend's audit log repository.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Self

from pydantic import BaseModel, Field, model_validator
from pydantic_invoices.schemas import Invoice, Payment
from pydantic_invoices.vo import Money

from py_invoices.core.totals import format_money

if TYPE_CHECKING:
    from py_invoices.plugins.base import AuditRepository

_PAGE_SIZE = 500


class AuditEntity(StrEnum):
    """Kind of record an audit entry is about."""

    INVOICE = "invoice"
    PAYMENT_NOTE = "payment_note"
    CLIENT = "client"
    COMPANY = "company"


class AuditLogEntry(BaseModel):
    """Audit log entry schema.

    The log is append-only: an entry is never edited or deleted, and a correction is a
    new entry whose `corrects_id` names the entry it corrects. `entity_type` and
    `entity_id` name the record; invoice entries also carry `invoice_id` and
    `invoice_number`. Entries written before 6.0.0 have only `invoice_id` and read as
    invoice entries.
    """

    id: int | None = Field(None, description="Assigned by the repository when stored")
    timestamp: datetime = Field(default_factory=datetime.now)
    entity_type: AuditEntity = AuditEntity.INVOICE
    entity_id: int | None = None
    invoice_id: int | None = None
    invoice_number: str | None = None
    action: str = Field(..., description="Action performed (e.g., CREATED, ISSUED, PAID)")
    old_value: str | None = None
    new_value: str | None = None
    notes: str | None = None
    user: str | None = None
    corrects_id: int | None = Field(None, description="ID of the entry this one corrects")

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def invoice_entries_name_the_invoice(self) -> Self:
        if self.entity_type is AuditEntity.INVOICE:
            if self.entity_id is None:
                self.entity_id = self.invoice_id
            elif self.invoice_id is None:
                self.invoice_id = self.entity_id
            elif self.invoice_id != self.entity_id:
                raise ValueError(
                    f"invoice_id {self.invoice_id} differs from entity_id {self.entity_id}"
                )
        elif self.invoice_id is not None:
            raise ValueError(f"A {self.entity_type.value} entry has no invoice_id")
        return self


class AuditService:
    """Service for logging audit trail entries.

    Provides high-level methods for logging invoice lifecycle events.
    """

    def __init__(self, audit_repo: AuditRepository | None = None) -> None:
        """Initialize audit service.

        Args:
            audit_repo: Optional repository for database-backed audit logs.
        """
        self.audit_repo = audit_repo
        self._logs: list[AuditLogEntry] = []

    def log_invoice_created(
        self,
        invoice: Invoice | int,
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
            if isinstance(total_amount, Money):
                total_amount = total_amount.amount
            client_name = kwargs.get("client_name", "unknown")
            user = user_id or kwargs.get("user")
        else:
            invoice_id = invoice.id
            invoice_number = invoice.number
            total_amount = invoice.total_amount
            if isinstance(total_amount, Money):
                total_amount = total_amount.amount
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
        return self._record(entry)

    def log_status_changed(
        self,
        invoice: Invoice | int,
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
        return self._record(entry)

    def log_payment_added(
        self,
        invoice: Invoice | int,
        payment: Payment | Money | float | None = None,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> AuditLogEntry:
        """Log payment addition."""
        if isinstance(invoice, int):
            invoice_id = invoice
            invoice_number = kwargs.get("invoice_number", "unknown")
            payment_amount: Money | Decimal | float = (
                payment if isinstance(payment, (int, float)) else 0.0
            )
            old_balance: Money | Decimal | float = kwargs.get("old_balance", 0.0)
            new_balance: Money | Decimal | float = kwargs.get("new_balance", 0.0)
            payment_method = kwargs.get("payment_method")
            user = user_id or kwargs.get("user")
        else:
            from pydantic_invoices.schemas import Payment

            invoice_id = invoice.id
            invoice_number = invoice.number
            user = user_id

            if isinstance(payment, Payment):
                pmnt_amt: Money | Decimal | float = payment.amount
                if isinstance(pmnt_amt, Money):
                    pmnt_amt = pmnt_amt.amount
                payment_amount = pmnt_amt
                payment_method = payment.payment_method
                old_balance = invoice.balance_due + payment_amount
                new_balance = invoice.balance_due
            else:
                pmnt_amt_raw: Money | Decimal | float = (
                    payment if isinstance(payment, (int, float, Money)) else 0.0
                )
                if isinstance(pmnt_amt_raw, Money):
                    pmnt_amt_raw = pmnt_amt_raw.amount
                payment_amount = pmnt_amt_raw
                old_balance = invoice.balance_due + payment_amount
                new_balance = invoice.balance_due
                payment_method = kwargs.get("payment_method")

        if isinstance(old_balance, Money):
            old_balance = old_balance.amount
        if isinstance(new_balance, Money):
            new_balance = new_balance.amount
        if isinstance(payment_amount, Money):
            payment_amount = payment_amount.amount

        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="PAYMENT_ADDED",
            old_value=f"Balance: ${old_balance:.2f}",
            new_value=f"Payment: ${payment_amount:.2f}, New Balance: ${new_balance:.2f}",
            notes=f"Method: {payment_method}" if payment_method else None,
            user=user,
        )
        return self._record(entry)

    def log_invoice_cloned(
        self,
        invoice_id: int,
        invoice_number: str,
        original_number: str,
        total_amount: float | Money,
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
        amt = total_amount.amount if isinstance(total_amount, Money) else total_amount
        entry = AuditLogEntry(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            action="CLONED",
            new_value=f"Cloned from {original_number}",
            notes=f"Total: ${amt:.2f}",
            user=user,
        )
        return self._record(entry)

    def log_credit_note_created(
        self,
        credit_note: Invoice,
        original: Invoice,
        user: str | None = None,
    ) -> AuditLogEntry:
        """Log a credit note issued against an invoice."""
        entry = AuditLogEntry(
            invoice_id=credit_note.id,
            invoice_number=credit_note.number,
            action="CREDIT_NOTE_CREATED",
            new_value=f"Credits {original.number}",
            notes=f"Total: {format_money(credit_note.total_amount)}",
            user=user,
        )
        return self._record(entry)

    def log_invoice_issued(
        self, invoice: Invoice, draft_number: str, user: str | None = None
    ) -> AuditLogEntry:
        """Log a draft being issued under its final number."""
        entry = AuditLogEntry(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            action="ISSUED",
            old_value=draft_number,
            new_value=f"Issued as {invoice.number}, {invoice.status.value}",
            notes=f"Total: {format_money(invoice.total_amount)}; hash {invoice.content_hash}",
            user=user,
        )
        return self._record(entry)

    def log_invoice_updated(
        self, invoice: Invoice, fields: list[str], user: str | None = None
    ) -> AuditLogEntry:
        """Log an edit of a draft."""
        entry = AuditLogEntry(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            action="UPDATED",
            new_value=f"Changed {', '.join(fields)}",
            notes=f"Total: {format_money(invoice.total_amount)}",
            user=user,
        )
        return self._record(entry)

    def log_invoice_sealed(self, invoice: Invoice, user: str | None = None) -> AuditLogEntry:
        """Log a content hash recorded for an invoice issued before hashing existed."""
        entry = AuditLogEntry(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            action="SEALED",
            new_value=invoice.content_hash,
            notes="Hash of the content as stored when sealed, not as issued",
            user=user,
        )
        return self._record(entry)

    def log_record_event(
        self,
        entity_type: AuditEntity,
        entity_id: int,
        action: str,
        new_value: str | None = None,
        old_value: str | None = None,
        user: str | None = None,
    ) -> AuditLogEntry:
        """Log a change to master data: a payment note, client or company."""
        if entity_type is AuditEntity.INVOICE:
            raise ValueError("Invoice events have their own log_invoice_* methods")
        entry = AuditLogEntry(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            user=user,
        )
        return self._record(entry)

    def _record(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._logs.append(entry)
        if self.audit_repo:
            self.audit_repo.add(entry)
        return entry

    def _all_entries(self) -> list[AuditLogEntry]:
        if self.audit_repo is None:
            return list(self._logs)
        entries: list[AuditLogEntry] = []
        while True:
            page = self.audit_repo.get_all(skip=len(entries), limit=_PAGE_SIZE)
            entries.extend(page)
            if len(page) < _PAGE_SIZE:
                return entries

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
        logs = self._all_entries()

        if invoice_id is not None:
            logs = [log for log in logs if log.invoice_id == invoice_id]

        if invoice_number is not None:
            logs = [log for log in logs if log.invoice_number == invoice_number]

        if action is not None:
            logs = [log for log in logs if log.action == action]

        return logs

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of audit logs (from the repository when one is set)."""
        entries = self._all_entries()
        summary: dict[str, Any] = {
            "total_entries": len(entries),
            "actions_count": {},
            "invoices_affected": set(),
        }
        actions_count: dict[str, int] = summary["actions_count"]
        invoices_affected: set[int] = summary["invoices_affected"]

        for entry in entries:
            actions_count[entry.action] = actions_count.get(entry.action, 0) + 1
            if entry.invoice_id:
                invoices_affected.add(entry.invoice_id)

        summary["invoices_affected"] = list(invoices_affected)
        return summary
