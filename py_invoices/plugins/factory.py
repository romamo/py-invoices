"""Factory for creating repository instances from plugins."""

from typing import TYPE_CHECKING, Any

from pydantic_invoices.interfaces import (
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)

from .base import StoragePlugin
from .registry import PluginRegistry

if TYPE_CHECKING:
    from ..config.settings import InvoiceSettings


class RepositoryFactory:
    """Factory for creating repository instances from registered plugins.

    This class provides a convenient interface for initializing a storage backend
    and creating repository instances.

    Example:
        >>> factory = RepositoryFactory(
        ...     backend="sqlite",
        ...     database_url="sqlite:///invoices.db"
        ... )
        >>> invoice_repo = factory.create_invoice_repository()
        >>> client_repo = factory.create_client_repository()
    """

    def __init__(self, backend: str, **config: Any):
        """Initialize factory with a specific backend.

        Args:
            backend: Plugin name (e.g., 'sqlite', 'postgres', 'memory')
            **config: Backend-specific configuration options

        Raises:
            ValueError: If the backend plugin is not registered
        """
        # Ensure backends are registered before looking up
        self._ensure_backends_registered()

        plugin_class = PluginRegistry.get(backend)
        if not plugin_class:
            available = PluginRegistry.list_plugins()
            raise ValueError(
                f"Unknown backend '{backend}'. "
                f"Available backends: {', '.join(available) if available else 'none'}"
            )

        self.plugin: StoragePlugin = plugin_class()
        self.config = config

        # Initialize backend
        self.plugin.initialize(**config)

    @classmethod
    def from_settings(cls, settings: "InvoiceSettings | None" = None) -> "RepositoryFactory":
        """Create factory from settings.

        This method allows configuration via environment variables or .env files.

        Args:
            settings: Settings instance. If None, loads from environment variables
                and .env file automatically.

        Returns:
            Configured RepositoryFactory instance

        Example:
            >>> # Load from environment variables
            >>> factory = RepositoryFactory.from_settings()

            >>> # Load from explicit settings
            >>> from py_invoices.config import InvoiceSettings
            >>> settings = InvoiceSettings(backend="sqlite")
            >>> factory = RepositoryFactory.from_settings(settings)
        """
        if settings is None:
            from ..config.settings import InvoiceSettings

            settings = InvoiceSettings()

        # Build config dict from settings
        config: dict[str, Any] = {}
        if settings.database_url:
            config["database_url"] = settings.database_url
        if settings.database_echo:
            config["echo"] = settings.database_echo
        
        if settings.backend == "files":
            config["file_format"] = settings.file_format
            config["root_dir"] = settings.storage_path

        return cls(backend=settings.backend, **config)

    _registered_backends = False

    @classmethod
    def _ensure_backends_registered(cls) -> None:
        """Lazy-load and register available backends.

        This method is called automatically when creating a factory.
        It imports and registers backends only when needed, allowing
        optional dependencies to work correctly.
        """
        if cls._registered_backends:
            return

        # Always available - memory backend has no dependencies
        try:
            from ..backends.memory.plugin import MemoryPlugin  # noqa: F401
        except ImportError:
            pass

        try:
            from ..backends.files.plugin import FilesPlugin  # noqa: F401
        except ImportError:
            pass

        cls._registered_backends = True

        # Optional backends - only register if dependencies are available
        try:
            from ..backends.sqlite.plugin import SQLitePlugin  # noqa: F401
        except ImportError:
            pass

        try:
            from ..backends.postgres.plugin import PostgresPlugin  # noqa: F401
        except ImportError:
            pass

        try:
            from ..backends.mysql.plugin import MySQLPlugin  # noqa: F401
        except ImportError:
            pass

    def create_invoice_repository(self) -> InvoiceRepository:
        """Create an invoice repository instance.

        Returns:
            InvoiceRepository implementation for the configured backend
        """
        return self.plugin.create_invoice_repository(**self.config)

    def create_client_repository(self) -> ClientRepository:
        """Create a client repository instance.

        Returns:
            ClientRepository implementation for the configured backend
        """
        return self.plugin.create_client_repository(**self.config)

    def create_payment_repository(self) -> PaymentRepository:
        """Create a payment repository instance.

        Returns:
            PaymentRepository implementation for the configured backend
        """
        return self.plugin.create_payment_repository(**self.config)

    def create_company_repository(self) -> CompanyRepository:
        """Create a company repository instance."""
        return self.plugin.create_company_repository(**self.config)

    def create_product_repository(self) -> ProductRepository:
        """Create a product repository instance."""
        return self.plugin.create_product_repository(**self.config)

    def create_payment_note_repository(self) -> PaymentNoteRepository:
        """Create a payment note repository instance."""
        return self.plugin.create_payment_note_repository(**self.config)

    def create_audit_repository(self) -> Any:
        """Create an audit repository instance."""
        return self.plugin.create_audit_repository(**self.config)

    def health_check(self) -> bool:
        """Check if the backend is healthy and accessible.

        Returns:
            True if backend is healthy, False otherwise
        """
        return self.plugin.health_check()

    def cleanup(self) -> None:
        """Clean up backend resources.

        Call this method when you're done using the factory to properly
        close connections and release resources.
        """
        self.plugin.cleanup()

    def __enter__(self) -> "RepositoryFactory":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit with automatic cleanup."""
        self.cleanup()
