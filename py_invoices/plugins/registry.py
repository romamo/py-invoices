"""Plugin registry for managing storage backends."""

from .base import StoragePlugin


class PluginRegistry:
    """Central registry for storage plugins.

    This class manages the registration and retrieval of storage backend plugins.
    Plugins can self-register by calling PluginRegistry.register() when imported.
    """

    _plugins: dict[str, type[StoragePlugin]] = {}

    @classmethod
    def register(cls, plugin_class: type[StoragePlugin]) -> None:
        """Register a storage plugin.

        Args:
            plugin_class: The plugin class to register (not an instance)

        Raises:
            ValueError: If a plugin with the same name is already registered
        """
        # Create temporary instance to get the name
        plugin = plugin_class()
        plugin_name = plugin.name

        if plugin_name in cls._plugins:
            raise ValueError(
                f"Plugin '{plugin_name}' is already registered. "
                f"Cannot register {plugin_class.__name__}."
            )

        cls._plugins[plugin_name] = plugin_class

    @classmethod
    def get(cls, name: str) -> type[StoragePlugin] | None:
        """Get a plugin class by name.

        Args:
            name: Plugin name (e.g., 'sqlite', 'postgres')

        Returns:
            Plugin class if found, None otherwise
        """
        return cls._plugins.get(name)

    @classmethod
    def list_plugins(cls) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names
        """
        return list(cls._plugins.keys())

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister a plugin.

        This is primarily useful for testing.

        Args:
            name: Plugin name to unregister
        """
        cls._plugins.pop(name, None)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered plugins.

        This is primarily useful for testing.
        """
        cls._plugins.clear()
