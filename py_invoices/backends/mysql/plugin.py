"""MySQL storage plugin."""

from ...plugins.registry import PluginRegistry
from ..sqlmodel.base_plugin import SQLModelBasePlugin


class MySQLPlugin(SQLModelBasePlugin):
    """MySQL storage backend plugin.

    Provides persistent storage using MySQL database via SQLModel.
    """

    @property
    def name(self) -> str:
        """Plugin name."""
        return "mysql"

    @property
    def default_url(self) -> str:
        """Default database URL."""
        return "mysql+pymysql://root:root@localhost:3306/invoices"


# Auto-register the MySQL plugin
PluginRegistry.register(MySQLPlugin)
