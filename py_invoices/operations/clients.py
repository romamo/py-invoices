"""Client operations."""

from pydantic_invoices.schemas import Client, ClientCreate

from py_invoices.operations.errors import ClientNotFoundError
from py_invoices.plugins.factory import RepositoryFactory


def list_clients(factory: RepositoryFactory, limit: int) -> list[Client]:
    return factory.create_client_repository().get_all(limit=limit)


def find_client(factory: RepositoryFactory, identifier: str) -> Client:
    """Find a client by numeric ID first, then by exact name."""
    repo = factory.create_client_repository()
    client = repo.get_by_id(int(identifier)) if identifier.isdigit() else None
    if client is None:
        client = repo.get_by_name(identifier)
    if client is None:
        raise ClientNotFoundError(identifier, by_id=False)
    return client


def search_clients(factory: RepositoryFactory, query: str) -> list[Client]:
    return factory.create_client_repository().search(query)


def create_client(factory: RepositoryFactory, data: ClientCreate) -> Client:
    return factory.create_client_repository().create(data)
