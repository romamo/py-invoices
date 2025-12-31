"""Base plugin interface for storage backends."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic_invoices.interfaces import (  # type: ignore[import-untyped]
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)


class StoragePlugin(ABC):
    """Base class for storage backend plugins.

    All storage backends must implement this interface to be compatible
    with the plugin system.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier (e.g., 'sqlite', 'postgres', 'memory')."""
        pass

    @abstractmethod
    def create_invoice_repository(self, **config: Any) -> InvoiceRepository:
        """Create and return an invoice repository instance.

        Args:
            **config: Backend-specific configuration options

        Returns:
            InvoiceRepository implementation
        """
        pass

    @abstractmethod
    def create_client_repository(self, **config: Any) -> ClientRepository:
        """Create and return a client repository instance.

        Args:
            **config: Backend-specific configuration options

        Returns:
            ClientRepository implementation
        """
        pass

    @abstractmethod
    def create_payment_repository(self, **config: Any) -> PaymentRepository:
        """Create and return a payment repository instance."""
        pass

    @abstractmethod
    def create_company_repository(self, **config: Any) -> CompanyRepository:
        """Create and return a company repository instance."""
        pass

    @abstractmethod
    def create_product_repository(self, **config: Any) -> ProductRepository:
        """Create and return a product repository instance."""
        pass

    @abstractmethod
    def create_payment_note_repository(self, **config: Any) -> PaymentNoteRepository:
        """Create and return a payment note repository instance."""
        pass

    @abstractmethod
    def create_audit_repository(self, **config: Any) -> Any:
        """Create and return an audit repository instance."""
        pass

    @abstractmethod
    def initialize(self, **config: Any) -> None:
        """Initialize the storage backend.

        This method should handle:
        - Database connection setup
        - Table/schema creation
        - Migrations (if applicable)

        Args:
            **config: Backend-specific configuration options
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if the storage backend is accessible and healthy.

        Returns:
            True if backend is healthy, False otherwise
        """
        pass

    def cleanup(self) -> None:
        """Optional cleanup method called when plugin is no longer needed.

        Override this method to implement cleanup logic like:
        - Closing database connections
        - Releasing resources
        """
        pass
