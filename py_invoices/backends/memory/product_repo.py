"""In-memory product repository."""

from pydantic_invoices.interfaces import ProductRepository
from pydantic_invoices.schemas.product import Product, ProductCreate


class MemoryProductRepository(ProductRepository):
    """In-memory implementation for Product repository."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._storage: dict[int, Product] = {}
        self._next_id = 1

    def create(self, data: ProductCreate) -> Product:
        """Create product."""
        product = Product(id=self._next_id, **data.model_dump())
        self._storage[self._next_id] = product
        self._next_id += 1
        return product

    def get_by_id(self, product_id: int) -> Product | None:
        """Get product by ID."""
        return self._storage.get(product_id)

    def get_by_code(self, code: str) -> Product | None:
        """Get product by code."""
        for p in self._storage.values():
            if p.code == code:
                return p
        return None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """Get all products."""
        return list(self._storage.values())[skip : skip + limit]

    def get_active(self) -> list[Product]:
        """Get all active products."""
        return [p for p in self._storage.values() if p.is_active]

    def get_by_category(self, category: str) -> list[Product]:
        """Get products by category."""
        return [p for p in self._storage.values() if p.category == category]

    def search(self, query: str) -> list[Product]:
        """Search products."""
        query = query.lower()
        return [
            p
            for p in self._storage.values()
            if query in p.name.lower() or (p.code and query in p.code.lower())
        ]

    def update(self, product: Product) -> Product:
        """Update product."""
        if product.id not in self._storage:
            raise ValueError(f"Product {product.id} not found")
        self._storage[product.id] = product
        return product

    def delete(self, product_id: int) -> bool:
        """Delete product."""
        if product_id in self._storage:
            del self._storage[product_id]
            return True
        return False
