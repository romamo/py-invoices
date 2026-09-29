"""SQLModel database models for py-invoices.

These models provide database persistence using SQLModel/SQLAlchemy.
They integrate with pydantic-invoices schemas via conversion methods.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic_invoices.schemas import (
    Client,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
)
from pydantic_invoices.schemas.company import Company
from pydantic_invoices.schemas.payment_note import PaymentNote
from pydantic_invoices.schemas.product import Product
from pydantic_invoices.vo import Money
from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from py_invoices.core.totals import as_money

if TYPE_CHECKING:
    from py_invoices.core.audit_service import AuditLogEntry


MONEY_DIGITS = 18
MONEY_PLACES = 4


def money_columns(value: Money.Input) -> tuple[Decimal, str]:
    """Split a schema money value into the (amount, currency) stored in the database."""
    money = as_money(value)
    return money.amount, money.currency


class ClientDB(SQLModel, table=True):
    """Client database model."""

    __tablename__ = "clients"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    address: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, max_length=2)
    tax_id: str | None = Field(None, max_length=50, index=True)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    preferred_template: str | None = Field(None, max_length=255)

    # Relationships
    invoices: list["InvoiceDB"] = Relationship(back_populates="client")

    def to_schema(self) -> Client:
        """Convert to pydantic-invoices Client schema."""
        from pydantic_invoices.schemas import Client

        if self.id is None:
            raise ValueError("ClientDB id cannot be None")
        return Client(
            id=self.id,
            name=self.name,
            address=self.address,
            city=self.city,
            postal_code=self.postal_code,
            country=self.country,
            tax_id=self.tax_id,
            email=self.email,
            phone=self.phone,
            preferred_template=self.preferred_template,
        )


class InvoiceLineDB(SQLModel, table=True):
    """Invoice line item database model."""

    __tablename__ = "invoice_lines"

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    description: str = Field(max_length=500)
    quantity: int = Field(default=1)
    unit_price: Decimal = Field(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    currency: str = Field(default="USD", max_length=3)
    tax_rate: Decimal = Field(default=Decimal(0), max_digits=5, decimal_places=2)

    # Relationship
    invoice: "InvoiceDB" = Relationship(back_populates="lines")

    def to_schema(self) -> InvoiceLine:
        """Convert to pydantic-invoices InvoiceLine schema."""
        from pydantic_invoices.schemas import InvoiceLine

        if self.id is None:
            raise ValueError("InvoiceLineDB id cannot be None")
        return InvoiceLine(
            id=self.id,
            invoice_id=self.invoice_id,
            description=self.description,
            quantity=self.quantity,
            unit_price=Money(self.unit_price, self.currency),
            tax_rate=float(self.tax_rate),
        )


class InvoiceDB(SQLModel, table=True):
    """Invoice database model."""

    __tablename__ = "invoices"

    id: int | None = Field(default=None, primary_key=True)
    number: str = Field(unique=True, index=True, max_length=50)
    issue_date: date

    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT, max_length=20)
    type: str = Field(
        default="STANDARD", max_length=20
    )  # Verify if I can use Enum here directly or string
    due_date: date | None = None
    payment_terms: str | None = None
    company_id: int = Field(default=1)

    # linking
    original_invoice_id: int | None = Field(default=None, foreign_key="invoices.id")
    reason: str | None = Field(default=None, max_length=500)

    # Client reference
    client_id: int = Field(foreign_key="clients.id", index=True)

    # Client snapshots (immutable at invoice creation)
    client_name_snapshot: str | None = None
    client_address_snapshot: str | None = None
    client_tax_id_snapshot: str | None = None
    client_city_snapshot: str | None = Field(None, max_length=100)
    client_postal_code_snapshot: str | None = Field(None, max_length=20)
    client_country_snapshot: str | None = Field(None, max_length=2)

    # Company snapshots (immutable at invoice creation)
    company_name_snapshot: str | None = None
    company_address_snapshot: str | None = None
    company_tax_id_snapshot: str | None = None

    template_name: str | None = Field(None, max_length=255)
    payment_note_ids: list[int] = Field(default_factory=list, sa_column=Column(JSON))

    # Relationships
    client: ClientDB = Relationship(back_populates="invoices")
    lines: list[InvoiceLineDB] = Relationship(
        back_populates="invoice", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    payments: list["PaymentDB"] = Relationship(
        back_populates="invoice", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    # self-referential relationship for credit notes
    original_invoice: "InvoiceDB" = Relationship(
        sa_relationship_kwargs={"remote_side": "InvoiceDB.id"}
    )

    def to_schema(self) -> Invoice:
        """Convert to pydantic-invoices Invoice schema."""
        from pydantic_invoices.schemas import Invoice, InvoiceType

        if self.id is None:
            raise ValueError("InvoiceDB id cannot be None")
        return Invoice(
            id=self.id,
            number=self.number,
            issue_date=self.issue_date,
            status=self.status,
            type=InvoiceType(self.type),
            original_invoice_id=self.original_invoice_id,
            reason=self.reason,
            due_date=self.due_date,
            payment_terms=self.payment_terms or "",
            company_id=self.company_id,
            client_id=self.client_id,
            client_name_snapshot=self.client_name_snapshot,
            client_address_snapshot=self.client_address_snapshot,
            client_tax_id_snapshot=self.client_tax_id_snapshot,
            client_city_snapshot=self.client_city_snapshot,
            client_postal_code_snapshot=self.client_postal_code_snapshot,
            client_country_snapshot=self.client_country_snapshot,
            company_name_snapshot=self.company_name_snapshot,
            company_address_snapshot=self.company_address_snapshot,
            company_tax_id_snapshot=self.company_tax_id_snapshot,
            template_name=self.template_name,
            payment_note_ids=list(self.payment_note_ids or []),
            lines=[line.to_schema() for line in self.lines],
            payments=[payment.to_schema() for payment in self.payments],
        )


class PaymentDB(SQLModel, table=True):
    """Payment database model."""

    __tablename__ = "payments"

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    amount: Decimal = Field(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    currency: str = Field(default="USD", max_length=3)
    payment_date: datetime
    payment_method: str | None = None
    reference: str | None = None
    notes: str | None = None

    # Relationship
    invoice: InvoiceDB = Relationship(back_populates="payments")

    def to_schema(self) -> Payment:
        """Convert to pydantic-invoices Payment schema."""
        from pydantic_invoices.schemas import Payment

        if self.id is None:
            raise ValueError("PaymentDB id cannot be None")
        return Payment(
            id=self.id,
            invoice_id=self.invoice_id,
            amount=Money(self.amount, self.currency),
            payment_date=self.payment_date,
            payment_method=self.payment_method or "Unknown",
            reference=self.reference,
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

    def to_schema(self) -> "AuditLogEntry":
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

    def to_schema(self) -> Company:
        """Convert to pydantic-invoices Company schema."""

        if self.id is None:
            raise ValueError("CompanyDB id cannot be None")
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
    unit_price: Decimal = Field(max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    currency: str = Field(default="USD", max_length=10)
    tax_rate: Decimal = Field(default=Decimal(0), max_digits=5, decimal_places=2)
    unit: str = Field(default="unit", max_length=50)
    is_active: bool = Field(default=True)
    category: str | None = Field(default=None, max_length=100)
    preferred_template: str | None = Field(None, max_length=255)

    def to_schema(self) -> Product:
        """Convert to pydantic-invoices Product schema."""

        if self.id is None:
            raise ValueError("ProductDB id cannot be None")
        return Product(
            id=self.id,
            code=self.code or "",
            name=self.name,
            description=self.description,
            unit_price=Money(self.unit_price, self.currency),
            currency=self.currency,
            tax_rate=float(self.tax_rate),
            unit=self.unit,
            is_active=self.is_active,
            category=self.category,
            preferred_template=self.preferred_template,
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

    def to_schema(self) -> PaymentNote:
        """Convert to pydantic-invoices PaymentNote schema."""

        if self.id is None:
            raise ValueError("PaymentNoteDB id cannot be None")
        return PaymentNote(
            id=self.id,
            title=self.title,
            content=self.content,
            company_id=self.company_id,
            is_active=self.is_active,
            is_default=self.is_default,
            display_order=self.display_order,
        )
