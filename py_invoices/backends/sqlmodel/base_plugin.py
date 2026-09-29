"""Base SQLModel storage plugin."""

from typing import Any, ClassVar

from pydantic_invoices.interfaces import (
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)
from sqlalchemy import Date, DateTime, Float, Numeric, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import TypeEngine
from sqlmodel import Session, SQLModel, create_engine, text

from ...plugins.base import StoragePlugin
from .audit_repo import SQLModelAuditRepository
from .client_repo import SQLModelClientRepository
from .company_repo import SQLModelCompanyRepository
from .invoice_repo import SQLModelInvoiceRepository
from .payment_note_repo import SQLModelPaymentNoteRepository
from .payment_repo import SQLModelPaymentRepository
from .product_repo import SQLModelProductRepository


class SQLModelBasePlugin(StoragePlugin):
    """Base class for SQLModel-based storage plugins.

    Provides common engine and session management.
    """

    def __init__(self) -> None:
        """Initialize SQLModel plugin."""
        self.engine: Engine | None = None
        self.session: Session | None = None

    default_url: ClassVar[str]
    """Database URL used when the settings do not give one."""

    def initialize(self, **config: Any) -> None:
        """Initialize database connection.

        Args:
            database_url: Database URL
            echo: Enable SQL echo for debugging (default: False)
        """
        database_url = config.get("database_url", self.default_url)
        echo = config.get("echo", False)

        self.engine = create_engine(database_url, echo=echo)
        SQLModel.metadata.create_all(self.engine)
        check_schema(self.engine)
        self.session = Session(self.engine)

    def open_scope(self) -> SQLModelBasePlugin:
        """A plugin sharing this engine with its own session, closed by close_scope()."""
        if self.engine is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        scoped = type(self)()
        scoped.engine = self.engine
        scoped.session = Session(self.engine)
        return scoped

    def close_scope(self) -> None:
        if self.session:
            self.session.close()
            self.session = None

    def create_invoice_repository(self, **config: Any) -> InvoiceRepository:
        """Create invoice repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelInvoiceRepository(self.session)

    def create_client_repository(self, **config: Any) -> ClientRepository:
        """Create client repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelClientRepository(self.session)

    def create_payment_repository(self, **config: Any) -> PaymentRepository:
        """Create payment repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelPaymentRepository(self.session)

    def create_company_repository(self, **config: Any) -> CompanyRepository:
        """Create company repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelCompanyRepository(self.session)

    def create_product_repository(self, **config: Any) -> ProductRepository:
        """Create product repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelProductRepository(self.session)

    def create_payment_note_repository(self, **config: Any) -> PaymentNoteRepository:
        """Create payment note repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelPaymentNoteRepository(self.session)

    def create_audit_repository(self, **config: Any) -> SQLModelAuditRepository:
        """Create audit repository."""
        if self.session is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return SQLModelAuditRepository(self.session)

    def health_check(self) -> bool:
        """Check if database is accessible."""
        if self.session is None:
            return False

        try:
            self.session.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError:
            return False

    def cleanup(self) -> None:
        """Close the session and release the engine's connections."""
        self.close_scope()
        if self.engine is not None:
            self.engine.dispose()
            self.engine = None


def check_schema(engine: Engine) -> None:
    """Fail fast when existing tables predate the current models.

    create_all() only creates missing tables; it never adds or changes columns. Column
    types are compared only where the database enforces them (not SQLite).
    """
    inspector = inspect(engine)
    problems = []
    for table in SQLModel.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"]: c["type"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name not in existing:
                problems.append(f"missing {table.name}.{column.name}")
            elif engine.dialect.name != "sqlite" and _outdated_type(
                column.type, existing[column.name]
            ):
                problems.append(
                    f"{table.name}.{column.name} is {existing[column.name]}, "
                    f"expected {column.type.compile(engine.dialect)}"
                )
    if problems:
        raise RuntimeError(
            f"Database schema at {engine.url!r} is out of date: {'; '.join(problems)}. "
            "Migrate the database (see CHANGELOG) or recreate it."
        )


def _outdated_type(expected: TypeEngine[Any], actual: TypeEngine[Any]) -> bool:
    """Types written by earlier versions: float money and datetime dates."""
    if isinstance(expected, Numeric) and not isinstance(expected, Float):
        return isinstance(actual, Float)
    if isinstance(expected, Date) and not isinstance(expected, DateTime):
        return isinstance(actual, DateTime)
    return False
