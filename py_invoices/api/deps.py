from collections.abc import Generator
from functools import lru_cache

from py_invoices import RepositoryFactory
from py_invoices.config import get_settings


@lru_cache
def _app_factory() -> RepositoryFactory:
    """One factory per process: one SQL engine, and in-memory data shared across requests."""
    return RepositoryFactory.from_settings(get_settings())


def get_factory() -> Generator[RepositoryFactory, None, None]:
    """Dependency: a factory scoped to the request, with its own database session."""
    with _app_factory().scope() as factory:
        yield factory
