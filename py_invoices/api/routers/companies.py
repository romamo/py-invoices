from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic_invoices.schemas.company import Company

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()


@router.get("/", response_model=list[Company])
def list_companies(
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Company]:
    repo = factory.create_company_repository()
    if active_only:
        return repo.get_active()[offset : offset + limit]
    return repo.get_all(skip=offset, limit=limit)


@router.get("/default", response_model=Company)
def get_default_company(
    factory: RepositoryFactory = Depends(get_factory),
) -> Company:
    repo = factory.create_company_repository()
    company = repo.get_default()
    if not company:
        raise HTTPException(status_code=404, detail="Default company not found")
    return company
