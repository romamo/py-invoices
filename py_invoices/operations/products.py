"""Product operations."""

from pydantic_invoices.schemas.product import Product, ProductCreate

from py_invoices.operations.errors import ProductNotFoundError
from py_invoices.plugins.factory import RepositoryFactory


def list_products(factory: RepositoryFactory, category: str | None) -> list[Product]:
    """Active products, or all products in a category."""
    repo = factory.create_product_repository()
    return repo.get_by_category(category) if category else repo.get_active()


def find_product(factory: RepositoryFactory, code: str) -> Product:
    product = factory.create_product_repository().get_by_code(code)
    if product is None:
        raise ProductNotFoundError(code)
    return product


def search_products(factory: RepositoryFactory, query: str) -> list[Product]:
    return factory.create_product_repository().search(query)


def create_product(factory: RepositoryFactory, data: ProductCreate) -> Product:
    return factory.create_product_repository().create(data)
