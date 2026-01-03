"""Files storage plugin."""

from pathlib import Path
from typing import Any

from pydantic_invoices.interfaces import (
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)

from ...plugins.base import StoragePlugin
from ...plugins.registry import PluginRegistry
from .audit_repo import FileAuditRepository
from .client_repo import FileClientRepository
from .company_repo import FileCompanyRepository
from .invoice_repo import FileInvoiceRepository
from .payment_note_repo import FilePaymentNoteRepository
from .payment_repo import FilePaymentRepository
from .product_repo import FileProductRepository


class FilesPlugin(StoragePlugin):
    """File system storage backend plugin."""

    def __init__(self) -> None:
        """Initialize files plugin."""
        self.root_dir: Path | None = None
        self._invoice_repo: FileInvoiceRepository | None = None
        self._client_repo: FileClientRepository | None = None
        self._payment_repo: FilePaymentRepository | None = None
        self._company_repo: FileCompanyRepository | None = None
        self._product_repo: FileProductRepository | None = None
        self._payment_note_repo: FilePaymentNoteRepository | None = None
        self._audit_repo: FileAuditRepository | None = None

    @property
    def name(self) -> str:
        """Plugin name."""
        return "files"

    def initialize(self, **config: Any) -> None:
        """Initialize file storage."""
        # Config should contain 'root_dir' or 'search_path' or we default to a data dir
        # If not provided, maybe default to current dir -> ./data
        root_dir = config.get("root_dir", "./data")
        file_format = config.get("file_format", "json")
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

        # Create repository instances
        self._invoice_repo = FileInvoiceRepository(self.root_dir, file_format)
        self._client_repo = FileClientRepository(self.root_dir, file_format)
        self._payment_repo = FilePaymentRepository(self.root_dir, file_format)
        self._company_repo = FileCompanyRepository(self.root_dir, file_format)
        self._product_repo = FileProductRepository(self.root_dir, file_format)
        self._payment_note_repo = FilePaymentNoteRepository(self.root_dir, file_format)
        self._audit_repo = FileAuditRepository(self.root_dir, file_format)

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
        """Check if backend is healthy."""
        return self.root_dir is not None and self.root_dir.exists()

    def cleanup(self) -> None:
        """Clean up resources."""
        pass


# Auto-register the plugin
PluginRegistry.register(FilesPlugin)
