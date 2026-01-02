from typing import List
from fastapi import APIRouter, Depends, HTTPException
from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from pydantic_invoices.schemas import Client, ClientCreate

router = APIRouter()

@router.get("/", response_model=List[Client])
def list_clients(limit: int = 10, factory: RepositoryFactory = Depends(get_factory)):
    repo = factory.create_client_repository()
    return repo.get_all()

@router.post("/", response_model=Client)
def create_client(client_in: ClientCreate, factory: RepositoryFactory = Depends(get_factory)):
    repo = factory.create_client_repository()
    return repo.create(client_in)

@router.get("/{client_id}", response_model=Client)
def get_client(client_id: int, factory: RepositoryFactory = Depends(get_factory)):
    repo = factory.create_client_repository()
    client = repo.get(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
