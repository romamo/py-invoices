"""Factory for creating repository instances from plugins."""

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from pydantic_invoices.interfaces import (
    ClientRepository,
    CompanyRepository,
    InvoiceRepository,
    PaymentNoteRepository,
    PaymentRepository,
    ProductRepository,
)

from .base import AuditRepository, StoragePlugin
from .registry import PluginRegistry

if TYPE_CHECKING:
    from ..config.settings import InvoiceSettings

# Built-in backends: name -> (module that registers the plugin, pip extra it needs)
BUILTIN_BACKENDS: dict[str, tuple[str, str | None]] = {
    "memory": ("py_invoices.backends.memory.plugin", None),
    "files": ("py_invoices.backends.files.plugin", None),
    "sqlite": ("py_invoices.backends.sqlite.plugin", "sqlite"),
    "postgres": ("py_invoices.backends.postgres.plugin", "postgres"),
    "mysql": ("py_invoices.backends.mysql.plugin", "mysql"),
}


def _missing_extra(backend: str, error: ModuleNotFoundError) -> ModuleNotFoundError | None:
    """An install hint when a third-party module of a built-in backend is missing."""
    extra = BUILTIN_BACKENDS.get(backend, ("", None))[1]
    if extra is None or not error.name or error.name.startswith("py_invoices"):
        return None
    return ModuleNotFoundError(
        f"The '{backend}' backend needs the '{error.name}' package. "
        f"Install it with: pip install 'py-invoices[{extra}]'",
        name=error.name,
    )


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
        plugin_class = self._plugin_class(backend)
        self.plugin: StoragePlugin = plugin_class()
        self.config = config
        try:
            self.plugin.initialize(**config)
        except ModuleNotFoundError as e:
            hint = _missing_extra(backend, e)
            if hint is None:
                raise
            raise hint from e

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

    @staticmethod
    def _plugin_class(backend: str) -> type[StoragePlugin]:
        """Import only the requested built-in backend, so optional extras stay optional."""
        if backend in BUILTIN_BACKENDS and PluginRegistry.get(backend) is None:
            module_name = BUILTIN_BACKENDS[backend][0]
            try:
                importlib.import_module(module_name)
            except ModuleNotFoundError as e:
                hint = _missing_extra(backend, e)
                if hint is None:
                    raise
                raise hint from e

        plugin_class = PluginRegistry.get(backend)
        if plugin_class is None:
            available = sorted(set(BUILTIN_BACKENDS) | set(PluginRegistry.list_plugins()))
            raise ValueError(
                f"Unknown backend '{backend}'. Available backends: {', '.join(available)}"
            )
        return plugin_class

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

    def create_audit_repository(self) -> AuditRepository:
        """Create an audit repository instance."""
        return self.plugin.create_audit_repository(**self.config)

    @contextmanager
    def scope(self) -> Iterator["RepositoryFactory"]:
        """A factory for one unit of work, sharing this backend.

        SQL backends get a dedicated session that is closed on exit, which makes it safe
        to use one long-lived factory from concurrent API requests.
        """
        scoped = object.__new__(RepositoryFactory)
        scoped.plugin = self.plugin.open_scope()
        scoped.config = self.config
        try:
            yield scoped
        finally:
            scoped.plugin.close_scope()

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
