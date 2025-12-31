"""Plugin system for py-invoices storage backends."""

from .base import StoragePlugin
from .factory import RepositoryFactory
from .registry import PluginRegistry

__all__ = [
    "StoragePlugin",
    "RepositoryFactory",
    "PluginRegistry",
]
