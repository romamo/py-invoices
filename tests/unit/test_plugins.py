"""Unit tests for the plugin system."""

import pytest

from py_invoices.plugins import PluginRegistry, RepositoryFactory


def test_plugin_registry_lists_memory_plugin() -> None:
    """Test that memory plugin is registered after factory creation."""
    # Trigger lazy registration by creating a factory
    _ = RepositoryFactory(backend="memory")

    plugins = PluginRegistry.list_plugins()
    assert "memory" in plugins


def test_repository_factory_creates_memory_backend() -> None:
    """Test creating a factory with memory backend."""
    factory = RepositoryFactory(backend="memory")
    assert factory.health_check() is True


def test_repository_factory_invalid_backend() -> None:
    """Test that invalid backend raises ValueError."""
    with pytest.raises(ValueError, match="Unknown backend 'invalid'"):
        RepositoryFactory(backend="invalid")


def test_repository_factory_creates_repositories() -> None:
    """Test that factory can create all repository types."""
    factory = RepositoryFactory(backend="memory")

    invoice_repo = factory.create_invoice_repository()
    client_repo = factory.create_client_repository()
    payment_repo = factory.create_payment_repository()

    assert invoice_repo is not None
    assert client_repo is not None
    assert payment_repo is not None


def test_repository_factory_context_manager() -> None:
    """Test factory works as context manager."""
    with RepositoryFactory(backend="memory") as factory:
        assert factory.health_check() is True
        repo = factory.create_invoice_repository()
        assert repo is not None


def test_plugin_registry_prevents_duplicate_registration() -> None:
    """Test that registering the same plugin twice raises error."""
    from py_invoices.backends.memory.plugin import MemoryPlugin

    # Plugin auto-registers on import (line 91 of plugin.py)
    # Try to register again manually
    with pytest.raises(ValueError, match="already registered"):
        PluginRegistry.register(MemoryPlugin)


def test_plugin_registry_unregister() -> None:
    """Test unregistering a plugin."""
    # Trigger lazy registration
    _ = RepositoryFactory(backend="memory")

    # Ensure memory is registered
    assert "memory" in PluginRegistry.list_plugins()

    # Unregister
    PluginRegistry.unregister("memory")
    assert "memory" not in PluginRegistry.list_plugins()

    # Re-register for other tests
    from py_invoices.backends.memory.plugin import MemoryPlugin

    PluginRegistry.register(MemoryPlugin)
