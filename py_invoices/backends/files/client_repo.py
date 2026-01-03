"""File-based client repository."""

from pathlib import Path
from typing import Any

from pydantic_invoices.interfaces import ClientRepository
from pydantic_invoices.schemas import Client, ClientCreate

from .storage import FileStorage


class FileClientRepository(ClientRepository):
    """File-based implementation of ClientRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[Client](
            root_dir, "clients", Client, default_format=file_format
        )

    def create(self, data: ClientCreate) -> Client:
        """Create a new client."""
        client_id = self.storage.get_next_id()
        client = Client(id=client_id, **data.model_dump())
        self.storage.save(client, client_id)
        return client

    def get_by_id(self, client_id: int) -> Client | None:
        """Get client by ID."""
        return self.storage.load(client_id)

    def get_by_tax_id(self, tax_id: str) -> Client | None:
        """Get client by tax ID."""
        for client in self.storage.load_all():
            if client.tax_id == tax_id:
                return client
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Client]:
        """Get all clients with pagination."""
        clients = self.storage.load_all()
        return clients[skip : skip + limit]

    def search_by_name(self, name: str) -> list[Client]:
        """Search clients by name (case-insensitive partial match)."""
        name_lower = name.lower()
        return [
            client for client in self.storage.load_all() 
            if name_lower in client.name.lower()
        ]

    def get_by_name(self, name: str) -> Client | None:
        """Get client by exact name match."""
        for client in self.storage.load_all():
            if client.name == name:
                return client
        return None

    def search(self, query: str) -> list[Client]:
        """Search clients by name or tax ID."""
        query_lower = query.lower()
        return [
            client
            for client in self.storage.load_all()
            if query_lower in client.name.lower()
            or (client.tax_id and query_lower in client.tax_id.lower())
        ]

    def update(self, client: Client) -> Client:
        """Update client."""
        existing = self.storage.load(client.id)
        if not existing:
            raise ValueError(f"Client {client.id} not found")

        self.storage.save(client, client.id)
        return client

    def delete(self, client_id: int) -> bool:
        """Delete client."""
        return self.storage.delete(client_id)
