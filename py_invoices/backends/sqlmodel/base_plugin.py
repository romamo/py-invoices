"""Base SQLModel storage plugin."""

from abc import abstractmethod
from typing import Any

from pydantic_invoices.interfaces import (
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)
from sqlalchemy.exc import SQLAlchemyError
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
        self.engine: Any | None = None
        self.session: Session | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name must be implemented by subclasses."""
        pass

    @property
    @abstractmethod
    def default_url(self) -> str:
        """Default database URL must be implemented by subclasses."""
        pass

    def initialize(self, **config: Any) -> None:
        """Initialize database connection.

        Args:
            database_url: Database URL
            echo: Enable SQL echo for debugging (default: False)
        """
        database_url = config.get("database_url", self.default_url)
        echo = config.get("echo", False)

        # Create engine
        self.engine = create_engine(database_url, echo=echo)

        # Create tables
        SQLModel.metadata.create_all(self.engine)

        # Create session
        self.session = Session(self.engine)

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
        """Clean up database connection."""
        if self.session:
            self.session.close()
            self.session = None
