from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic_invoices.schemas.product import Product

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory

router = APIRouter()


@router.get("/", response_model=list[Product])
def list_products(
    active_only: bool = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Product]:
    repo = factory.create_product_repository()
    if active_only:
        return repo.get_active()[offset : offset + limit]
    return repo.get_all(skip=offset, limit=limit)


@router.get("/search", response_model=list[Product])
def search_products(
    q: str,
    limit: int = 100,
    factory: RepositoryFactory = Depends(get_factory),
) -> list[Product]:
    repo = factory.create_product_repository()
    results = repo.search(q)
    return results[:limit]


@router.get("/{code}", response_model=Product)
def get_product(
    code: str,
    factory: RepositoryFactory = Depends(get_factory),
) -> Product:
    repo = factory.create_product_repository()
    product = repo.get_by_code(code)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
