"""Test configuration for py-invoices."""
from collections.abc import Generator
from typing import Any

import pytest

from py_invoices import RepositoryFactory


@pytest.fixture(autouse=True, scope="function")
def reset_registry() -> Generator[None, None, None]:
    """Ensure backends are available for each test.

    With lazy registration, backends are registered on first factory creation.
    We don't need to clear the registry between tests since each test that needs
    a factory will trigger registration if needed.
    """
    yield
    # No cleanup needed - lazy registration handles this


@pytest.fixture
def factory() -> Generator[RepositoryFactory, None, None]:
    """Create a memory backend factory for testing."""
    factory = RepositoryFactory(backend="memory")
    yield factory
    factory.cleanup()


@pytest.fixture
def client_repo(factory: RepositoryFactory) -> Any:
    """Get client repository."""
    return factory.create_client_repository()


@pytest.fixture
def invoice_repo(factory: RepositoryFactory) -> Any:
    """Get invoice repository."""
    return factory.create_invoice_repository()


@pytest.fixture
def payment_repo(factory: RepositoryFactory) -> Any:
    """Get payment repository."""
    return factory.create_payment_repository()
