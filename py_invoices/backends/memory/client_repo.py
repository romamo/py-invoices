"""In-memory storage backend for testing and development."""

from pydantic_invoices.interfaces import ClientRepository  # type: ignore[import-untyped]
from pydantic_invoices.schemas import (  # type: ignore[import-untyped]
    Client,
    ClientCreate,
)


class MemoryClientRepository(ClientRepository):  # type: ignore[misc]
    """In-memory implementation of ClientRepository for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._storage: dict[int, Client] = {}
        self._next_id = 1

    def create(self, data: ClientCreate) -> Client:
        """Create a new client."""
        client = Client(id=self._next_id, **data.model_dump())
        self._storage[self._next_id] = client
        self._next_id += 1
        return client

    def get_by_id(self, client_id: int) -> Client | None:
        """Get client by ID."""
        return self._storage.get(client_id)

    def get_by_tax_id(self, tax_id: str) -> Client | None:
        """Get client by tax ID."""
        for client in self._storage.values():
            if client.tax_id == tax_id:
                return client
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Client]:
        """Get all clients with pagination."""
        clients = list(self._storage.values())
        return clients[skip : skip + limit]

    def search_by_name(self, name: str) -> list[Client]:
        """Search clients by name (case-insensitive partial match)."""
        name_lower = name.lower()
        return [client for client in self._storage.values() if name_lower in client.name.lower()]

    def get_by_name(self, name: str) -> Client | None:
        """Get client by exact name match."""
        for client in self._storage.values():
            if client.name == name:
                return client
        return None

    def search(self, query: str) -> list[Client]:
        """Search clients by name or tax ID."""
        query_lower = query.lower()
        return [
            client
            for client in self._storage.values()
            if query_lower in client.name.lower()
            or (client.tax_id and query_lower in client.tax_id.lower())
        ]

    def update(self, client: Client) -> Client:
        """Update client."""
        if client.id not in self._storage:
            raise ValueError(f"Client {client.id} not found")

        self._storage[client.id] = client
        return client

    def delete(self, client_id: int) -> bool:
        """Delete client."""
        if client_id in self._storage:
            del self._storage[client_id]
            return True
        return False
