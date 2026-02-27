from rich.console import Console

from py_invoices import RepositoryFactory
from py_invoices.config import get_settings

console = Console()

def get_console() -> Console:
    return console

def get_factory(backend: str | None = None) -> RepositoryFactory:
    settings = get_settings()
    # Use explicit backend if provided, otherwise use settings
    if backend and backend != settings.backend:
        settings = settings.model_copy(update={"backend": backend})

    return RepositoryFactory.from_settings(settings)
