"""SQLite storage plugin."""

from ...plugins.registry import PluginRegistry
from ..sqlmodel.base_plugin import SQLModelBasePlugin


class SQLitePlugin(SQLModelBasePlugin):
    """SQLite storage backend plugin.

    Provides persistent storage using SQLite database via SQLModel.
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        return "sqlite"

    @property
    def default_url(self) -> str:
        """Default database URL."""
        return "sqlite:///invoices.db"


# Auto-register the SQLite plugin
PluginRegistry.register(SQLitePlugin)
