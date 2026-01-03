from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic_invoices.schemas.company import Company


from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()

@router.get("/", response_model=List[Company])
def list_companies(
    active_only: bool = True,
    limit: int = 100,
    factory: RepositoryFactory = Depends(get_factory),
) -> List[Company]:
    repo = factory.create_company_repository()
    if active_only:
        companies = repo.get_active()
        return companies[:limit]
    return repo.get_all(limit=limit)


@router.get("/default", response_model=Company)
def get_default_company(
    factory: RepositoryFactory = Depends(get_factory),
) -> Company:
    repo = factory.create_company_repository()
    company = repo.get_default()
    if not company:
        raise HTTPException(status_code=404, detail="Default company not found")
    return company
