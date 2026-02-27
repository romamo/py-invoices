"""File-based product repository."""

from pathlib import Path

from pydantic_invoices.interfaces import ProductRepository
from pydantic_invoices.schemas.product import Product, ProductCreate

from .storage import FileStorage


class FileProductRepository(ProductRepository):
    """File-based implementation of ProductRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[Product](
            root_dir, "products", Product, default_format=file_format
        )

    def create(self, data: ProductCreate) -> Product:
        """Create a new product."""
        product_id = self.storage.get_next_id()
        product = Product(id=product_id, **data.model_dump())
        self.storage.save(product, product_id)
        return product

    def get_by_id(self, product_id: int) -> Product | None:
        """Get product by ID."""
        return self.storage.load(product_id)

    def get_by_code(self, code: str) -> Product | None:
        """Get product by code."""
        for p in self.storage.load_all():
            if p.code == code:
                return p
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """Get all products with pagination."""
        products = self.storage.load_all()
        return products[skip : skip + limit]

    def get_active(self) -> list[Product]:
        """Get all active products."""
        return [p for p in self.storage.load_all() if p.is_active]

    def get_by_category(self, category: str) -> list[Product]:
        """Get products by category."""
        return [p for p in self.storage.load_all() if p.category == category]

    def search(self, query: str) -> list[Product]:
        """Search products."""
        query = query.lower()
        return [
            p
            for p in self.storage.load_all()
            if query in p.name.lower() or (p.code and query in p.code.lower())
        ]

    def update(self, product: Product) -> Product:
        """Update product."""
        existing = self.storage.load(product.id)
        if not existing:
            raise ValueError(f"Product {product.id} not found")

        self.storage.save(product, product.id)
        return product

    def delete(self, product_id: int) -> bool:
        """Delete product."""
        return self.storage.delete(product_id)
