"""SQLModel database models for py-invoices.

These models provide database persistence using SQLModel/SQLAlchemy.
They integrate with pydantic-invoices schemas via conversion methods.
"""

from datetime import date, datetime
from typing import Any

from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    Client,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
)
from sqlmodel import Field, Relationship, SQLModel


class ClientDB(SQLModel, table=True):
    """Client database model."""

    __tablename__ = "clients"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    address: str | None = Field(None, max_length=500)
    tax_id: str | None = Field(None, max_length=50, index=True)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)

    # Relationships
    invoices: list["InvoiceDB"] = Relationship(back_populates="client")

    def to_schema(self) -> Client:
        """Convert to pydantic-invoices Client schema."""
        from pydantic_invoices.schemas import Client

        return Client(
            id=self.id,
            name=self.name,
            address=self.address,
            tax_id=self.tax_id,
            email=self.email,
            phone=self.phone,
        )


class InvoiceLineDB(SQLModel, table=True):
    """Invoice line item database model."""

    __tablename__ = "invoice_lines"

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    description: str = Field(max_length=500)
    quantity: int = Field(default=1)
    unit_price: float

    # Relationship
    invoice: "InvoiceDB" = Relationship(back_populates="lines")

    @property
    def total(self) -> float:
        """Calculate line total."""
        return self.quantity * self.unit_price

    def to_schema(self) -> InvoiceLine:
        """Convert to pydantic-invoices InvoiceLine schema."""
        from pydantic_invoices.schemas import InvoiceLine

        return InvoiceLine(
            id=self.id,
            invoice_id=self.invoice_id,
            description=self.description,
            quantity=self.quantity,
            unit_price=self.unit_price,
        )


class InvoiceDB(SQLModel, table=True):
    """Invoice database model."""

    __tablename__ = "invoices"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(unique=True, index=True, max_length=50)
    issue_date: datetime
    status: InvoiceStatus = Field(default=InvoiceStatus.UNPAID, max_length=20)
    due_date: date | None = None
    payment_terms: str | None = None
    company_id: int = Field(default=1)

    # Client reference
    client_id: int = Field(foreign_key="clients.id", index=True)

    # Client snapshots (immutable at invoice creation)
    client_name_snapshot: str | None = None
    client_address_snapshot: str | None = None
    client_tax_id_snapshot: str | None = None

    # Relationships
    client: ClientDB = Relationship(back_populates="invoices")
    lines: list[InvoiceLineDB] = Relationship(
        back_populates="invoice", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    payments: list["PaymentDB"] = Relationship(
        back_populates="invoice", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    @property
    def total_amount(self) -> float:
        """Calculate total from all line items."""
        return sum(line.total for line in self.lines)

    @property
    def total_paid(self) -> float:
        """Calculate total amount paid."""
        return sum(payment.amount for payment in self.payments)

    @property
    def balance_due(self) -> float:
        """Calculate remaining balance."""
        return self.total_amount - self.total_paid

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if self.status == InvoiceStatus.PAID:
            return False
        if self.due_date:
            return date.today() > self.due_date
        return False

    def to_schema(self) -> Invoice:
        """Convert to pydantic-invoices Invoice schema."""
        from pydantic_invoices.schemas import Invoice

        return Invoice(
            id=self.id,
            number=self.number,
            issue_date=self.issue_date,
            status=self.status,
            due_date=self.due_date,
            payment_terms=self.payment_terms,
            company_id=self.company_id,
            client_id=self.client_id,
            client_name_snapshot=self.client_name_snapshot,
            client_address_snapshot=self.client_address_snapshot,
            client_tax_id_snapshot=self.client_tax_id_snapshot,
            lines=[line.to_schema() for line in self.lines],
            payments=[payment.to_schema() for payment in self.payments],
        )

class PaymentDB(SQLModel, table=True):
    """Payment database model."""

    __tablename__ = "payments"

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    amount: float
    payment_date: datetime
    payment_method: str | None = None
    reference: str | None = None
    notes: str | None = None

    # Relationship
    invoice: InvoiceDB = Relationship(back_populates="payments")

    def to_schema(self) -> Payment:
        """Convert to pydantic-invoices Payment schema."""
        from pydantic_invoices.schemas import Payment

        return Payment(
            id=self.id,
            invoice_id=self.invoice_id,
            amount=self.amount,
            payment_date=self.payment_date,
            payment_method=self.payment_method,
            reference=self.reference,
            notes=self.notes,
        )


class AuditLogDB(SQLModel, table=True):
    """Audit log database model."""

    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    invoice_id: int | None = Field(default=None, index=True)
    invoice_number: str | None = Field(default=None, index=True, max_length=50)
    action: str = Field(max_length=50, index=True)
    old_value: str | None = Field(default=None)
    new_value: str | None = Field(default=None)
    notes: str | None = Field(default=None)
    user: str | None = Field(default=None, max_length=100)

    def to_schema(self) -> Any:
        """Convert to AuditLogEntry schema."""
        from py_invoices.core.audit_service import AuditLogEntry

        return AuditLogEntry(
            timestamp=self.timestamp,
            invoice_id=self.invoice_id,
            invoice_number=self.invoice_number,
            action=self.action,
            old_value=self.old_value,
            new_value=self.new_value,
            notes=self.notes,
            user=self.user,
        )


class CompanyDB(SQLModel, table=True):
    """Company database model."""

    __tablename__ = "companies"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=100, index=True)
    registration_number: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    website: str | None = Field(default=None, max_length=255)
    logo_path: str | None = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)
    is_default: bool = Field(default=False)

    def to_schema(self) -> Any:
        """Convert to pydantic-invoices Company schema."""
        from pydantic_invoices.schemas.company import Company  # type: ignore[import-untyped]

        return Company(
            id=self.id,
            name=self.name,
            legal_name=self.legal_name,
            tax_id=self.tax_id,
            registration_number=self.registration_number,
            address=self.address,
            city=self.city,
            postal_code=self.postal_code,
            country=self.country,
            email=self.email,
            phone=self.phone,
            website=self.website,
            logo_path=self.logo_path,
            is_active=self.is_active,
            is_default=self.is_default,
        )


class ProductDB(SQLModel, table=True):
    """Product database model."""

    __tablename__ = "products"

    id: int | None = Field(default=None, primary_key=True)
    code: str | None = Field(default=None, max_length=50, index=True)
    name: str = Field(max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    unit_price: float
    currency: str = Field(default="USD", max_length=10)
    tax_rate: float = Field(default=0.0)
    unit: str = Field(default="unit", max_length=50)
    is_active: bool = Field(default=True)
    category: str | None = Field(default=None, max_length=100)

    def to_schema(self) -> Any:
        """Convert to pydantic-invoices Product schema."""
        from pydantic_invoices.schemas.product import Product  # type: ignore[import-untyped]

        return Product(
            id=self.id,
            code=self.code,
            name=self.name,
            description=self.description,
            unit_price=self.unit_price,
            currency=self.currency,
            tax_rate=self.tax_rate,
            unit=self.unit,
            is_active=self.is_active,
            category=self.category,
        )


class PaymentNoteDB(SQLModel, table=True):
    """Payment note database model."""

    __tablename__ = "payment_notes"

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=255)
    content: str = Field(max_length=1000)
    company_id: int | None = Field(default=None, index=True)
    is_active: bool = Field(default=True)
    is_default: bool = Field(default=False)
    display_order: int = Field(default=0)

    def to_schema(self) -> Any:
        """Convert to pydantic-invoices PaymentNote schema."""
        from pydantic_invoices.schemas.payment_note import (  # type: ignore[import-untyped]
            PaymentNote,
        )

        return PaymentNote(
            id=self.id,
            title=self.title,
            content=self.content,
            company_id=self.company_id,
            is_active=self.is_active,
            is_default=self.is_default,
            display_order=self.display_order,
        )
