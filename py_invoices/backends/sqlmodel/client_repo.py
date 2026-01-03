"""SQLModel client repository implementation."""

from pydantic_invoices.interfaces import ClientRepository
from pydantic_invoices.schemas import (
    Client,
    ClientCreate,
)
from sqlmodel import Session, select

from .models import ClientDB


class SQLModelClientRepository(ClientRepository):
    """Generic SQLModel implementation for Client repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: ClientCreate) -> Client:
        """Create client in database."""
        db_client = ClientDB(**data.model_dump())
        self.session.add(db_client)
        self.session.commit()
        self.session.refresh(db_client)
        return db_client.to_schema()

    def get_by_id(self, client_id: int) -> Client | None:
        """Get client by ID."""
        db_client = self.session.get(ClientDB, client_id)
        return db_client.to_schema() if db_client else None

    def get_by_tax_id(self, tax_id: str) -> Client | None:
        """Get client by tax ID."""
        stmt = select(ClientDB).where(ClientDB.tax_id == tax_id)
        db_client = self.session.exec(stmt).first()
        return db_client.to_schema() if db_client else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Client]:
        """Get all clients with pagination."""
        stmt = select(ClientDB).offset(skip).limit(limit)
        db_clients = self.session.exec(stmt).all()
        return [c.to_schema() for c in db_clients]

    def search_by_name(self, name: str) -> list[Client]:
        """Search clients by name (partial match)."""
        stmt = select(ClientDB).where(ClientDB.name.contains(name))  # type: ignore[attr-defined]
        db_clients = self.session.exec(stmt).all()
        return [c.to_schema() for c in db_clients]

    def get_by_name(self, name: str) -> Client | None:
        """Get client by exact name match."""
        stmt = select(ClientDB).where(ClientDB.name == name)
        db_client = self.session.exec(stmt).first()
        return db_client.to_schema() if db_client else None

    def search(self, query: str) -> list[Client]:
        """Search clients by name or tax ID."""
        stmt = select(ClientDB).where(
            (ClientDB.name.contains(query)) | (ClientDB.tax_id.contains(query))  # type: ignore[attr-defined, union-attr]
        )
        db_clients = self.session.exec(stmt).all()
        return [c.to_schema() for c in db_clients]

    def update(self, client: Client) -> Client:
        """Update client."""
        db_client = self.session.get(ClientDB, client.id)
        if not db_client:
            raise ValueError(f"Client {client.id} not found")

        for key, value in client.model_dump(exclude={"id"}).items():
            setattr(db_client, key, value)

        self.session.commit()
        self.session.refresh(db_client)
        return db_client.to_schema()

    def delete(self, client_id: int) -> bool:
        """Delete client."""
        db_client = self.session.get(ClientDB, client_id)
        if db_client:
            self.session.delete(db_client)
            self.session.commit()
            return True
        return False
