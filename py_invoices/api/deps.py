from typing import Generator
from py_invoices import RepositoryFactory
from py_invoices.config import get_settings

def get_factory() -> Generator[RepositoryFactory, None, None]:
    """Dependency to get a RepositoryFactory instance."""
    settings = get_settings()
    factory = RepositoryFactory(backend=settings.backend)
    yield factory
