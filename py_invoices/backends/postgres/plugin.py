"""PostgreSQL storage plugin."""

from ...plugins.registry import PluginRegistry
from ..sqlmodel.base_plugin import SQLModelBasePlugin


class PostgresPlugin(SQLModelBasePlugin):
    """PostgreSQL storage backend plugin.

    Provides persistent storage using PostgreSQL database via SQLModel.
    """

    name = "postgres"
    default_url = "postgresql://postgres:postgres@localhost:5432/invoices"


# Auto-register the Postgres plugin
PluginRegistry.register(PostgresPlugin)
