from rich.console import Console

from py_invoices import RepositoryFactory
from py_invoices.config import get_settings

console = Console()

def get_console() -> Console:
    return console

def get_factory(backend: str | None = None) -> RepositoryFactory:
    settings = get_settings()
    # Use explicit backend if provided, otherwise use settings
    backend_to_use = backend if backend else settings.backend
    return RepositoryFactory(backend=backend_to_use)
