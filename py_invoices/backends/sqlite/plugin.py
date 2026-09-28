"""SQLite storage plugin."""

from ...plugins.registry import PluginRegistry
from ..sqlmodel.base_plugin import SQLModelBasePlugin


class SQLitePlugin(SQLModelBasePlugin):
    """SQLite storage backend plugin.

    Provides persistent storage using SQLite database via SQLModel.
    """

    name = "sqlite"
    default_url = "sqlite:///invoices.db"


# Auto-register the SQLite plugin
PluginRegistry.register(SQLitePlugin)
