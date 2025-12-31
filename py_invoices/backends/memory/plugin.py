"""In-memory storage plugin for testing."""

from typing import Any

from pydantic_invoices.interfaces import (  # type: ignore[import-untyped]
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)

from ...plugins.base import StoragePlugin
from ...plugins.registry import PluginRegistry
from .audit_repo import MemoryAuditRepository
from .client_repo import MemoryClientRepository
from .company_repo import MemoryCompanyRepository
from .invoice_repo import MemoryInvoiceRepository
from .payment_note_repo import MemoryPaymentNoteRepository
from .payment_repo import MemoryPaymentRepository
from .product_repo import MemoryProductRepository


class MemoryPlugin(StoragePlugin):
    """In-memory storage backend plugin for testing and development.

    This plugin provides a simple in-memory storage implementation that
    doesn't require any external dependencies. Perfect for:
    - Unit testing
    - Development without database setup
    - Demos and examples
    """

    def __init__(self) -> None:
        """Initialize memory plugin."""
        self._invoice_repo: MemoryInvoiceRepository | None = None
        self._client_repo: MemoryClientRepository | None = None
        self._payment_repo: MemoryPaymentRepository | None = None
        self._company_repo: MemoryCompanyRepository | None = None
        self._product_repo: MemoryProductRepository | None = None
        self._payment_note_repo: MemoryPaymentNoteRepository | None = None
        self._audit_repo: MemoryAuditRepository | None = None

    @property
    def name(self) -> str:
        """Plugin name."""
        return "memory"

    def initialize(self, **config: Any) -> None:
        """Initialize in-memory storage.

        No configuration needed for memory backend.
        """
        # Create repository instances
        self._invoice_repo = MemoryInvoiceRepository()
        self._client_repo = MemoryClientRepository()
        self._payment_repo = MemoryPaymentRepository()
        self._company_repo = MemoryCompanyRepository()
        self._product_repo = MemoryProductRepository()
        self._payment_note_repo = MemoryPaymentNoteRepository()
        self._audit_repo = MemoryAuditRepository()

    def create_invoice_repository(self, **config: Any) -> InvoiceRepository:
        """Create invoice repository."""
        if self._invoice_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._invoice_repo

    def create_client_repository(self, **config: Any) -> ClientRepository:
        """Create client repository."""
        if self._client_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._client_repo

    def create_payment_repository(self, **config: Any) -> PaymentRepository:
        """Create payment repository."""
        if self._payment_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._payment_repo

    def create_company_repository(self, **config: Any) -> CompanyRepository:
        """Create company repository."""
        if self._company_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._company_repo

    def create_product_repository(self, **config: Any) -> ProductRepository:
        """Create product repository."""
        if self._product_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._product_repo

    def create_payment_note_repository(self, **config: Any) -> PaymentNoteRepository:
        """Create payment note repository."""
        if self._payment_note_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._payment_note_repo

    def create_audit_repository(self, **config: Any) -> Any:
        """Create audit repository."""
        if self._audit_repo is None:
            raise RuntimeError("Plugin not initialized. Call initialize() first.")
        return self._audit_repo

    def health_check(self) -> bool:
        """Check if memory backend is healthy.

        Memory backend is always healthy if initialized.
        """
        return (
            self._invoice_repo is not None
            and self._client_repo is not None
            and self._payment_repo is not None
        )

    def cleanup(self) -> None:
        """Clean up memory storage.

        Clears all data from memory.
        """
        if self._invoice_repo:
            self._invoice_repo._storage.clear()
        if self._client_repo:
            self._client_repo._storage.clear()
        if self._payment_repo:
            self._payment_repo._storage.clear()
        if self._company_repo:
            self._company_repo._storage.clear()
        if self._product_repo:
            self._product_repo._storage.clear()
        if self._payment_note_repo:
            self._payment_note_repo._storage.clear()
        if self._audit_repo:
            self._audit_repo._logs.clear()


# Auto-register the memory plugin
PluginRegistry.register(MemoryPlugin)
