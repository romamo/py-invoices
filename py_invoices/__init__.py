"""py-invoices: Framework-agnostic invoice management with pluggable storage backends.

This package provides:
- Core business logic for invoice management
- Pluggable storage backends (SQLite, PostgreSQL, in-memory)
- PDF generation capabilities
"""

__version__ = "1.9.0"

from .config import InvoiceSettings
from .constants import APP_DISPLAY_NAME, APP_NAME
from .core import AuditService, NumberingService, PDFService
from .plugins.factory import RepositoryFactory
from .plugins.registry import PluginRegistry

__all__ = [
    "APP_NAME",
    "APP_DISPLAY_NAME",
    "RepositoryFactory",
    "PluginRegistry",
    "InvoiceSettings",
    "AuditService",
    "NumberingService",
    "PDFService",
    "__version__",
]
