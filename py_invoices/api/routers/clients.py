
from fastapi import APIRouter, Depends, HTTPException, Query

from pydantic_invoices.schemas import Client, ClientCreate

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()

@router.get("/", response_model=list[Client])
def list_clients(
    limit: int = 10, offset: int = 0, factory: RepositoryFactory = Depends(get_factory)
) -> list[Client]:
    repo = factory.create_client_repository()
    return repo.get_all(limit=limit)

@router.post("/", response_model=Client)
def create_client(
    client_in: ClientCreate, factory: RepositoryFactory = Depends(get_factory)
) -> Client:
    repo = factory.create_client_repository()

    return repo.create(client_in)

@router.get("/search", response_model=list[Client])
def search_clients(
    q: str = Query(..., min_length=1),
    factory: RepositoryFactory = Depends(get_factory)
) -> list[Client]:
    repo = factory.create_client_repository()
    return repo.search(q)


@router.get("/{client_id}", response_model=Client)
def get_client(client_id: int, factory: RepositoryFactory = Depends(get_factory)) -> Client:
    repo = factory.create_client_repository()
    client = repo.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
