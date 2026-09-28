"""SQLModel product repository implementation."""

from decimal import Decimal

from pydantic_invoices.interfaces import ProductRepository
from pydantic_invoices.schemas.product import (
    Product,
    ProductCreate,
)
from sqlmodel import Session, col, select

from .models import ProductDB, money_columns


def _product_columns(product: ProductCreate | Product) -> dict[str, object]:
    fields = product.model_dump(exclude={"id", "unit_price", "tax_rate"})
    unit_price, _ = money_columns(product.unit_price)
    return {**fields, "unit_price": unit_price, "tax_rate": Decimal(str(product.tax_rate or 0))}


class SQLModelProductRepository(ProductRepository):
    """Generic SQLModel implementation for Product repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: ProductCreate) -> Product:
        """Create product in database."""
        db_product = ProductDB(**_product_columns(data))
        self.session.add(db_product)
        self.session.commit()
        self.session.refresh(db_product)
        return db_product.to_schema()

    def get_by_id(self, product_id: int) -> Product | None:
        """Get product by ID."""
        db_product = self.session.get(ProductDB, product_id)
        return db_product.to_schema() if db_product else None

    def get_by_code(self, code: str) -> Product | None:
        """Get product by code."""
        stmt = select(ProductDB).where(ProductDB.code == code)
        db_product = self.session.exec(stmt).first()
        return db_product.to_schema() if db_product else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Product]:
        """Get all products with pagination."""
        stmt = select(ProductDB).order_by(col(ProductDB.id)).offset(skip).limit(limit)
        db_products = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_products]

    def get_active(self) -> list[Product]:
        """Get all active products."""
        stmt = select(ProductDB).where(ProductDB.is_active == True)  # noqa: E712
        db_products = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_products]

    def get_by_category(self, category: str) -> list[Product]:
        """Get products by category."""
        stmt = select(ProductDB).where(ProductDB.category == category)
        db_products = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_products]

    def search(self, query: str) -> list[Product]:
        """Search products by name or code."""
        stmt = select(ProductDB).where(
            (ProductDB.name.contains(query)) | (ProductDB.code.contains(query))  # type: ignore[attr-defined, union-attr]
        )
        db_products = self.session.exec(stmt).all()
        return [p.to_schema() for p in db_products]

    def update(self, product: Product) -> Product:
        """Update product."""
        db_product = self.session.get(ProductDB, product.id)
        if not db_product:
            raise ValueError(f"Product {product.id} not found")

        for key, value in _product_columns(product).items():
            setattr(db_product, key, value)

        self.session.commit()
        self.session.refresh(db_product)
        return db_product.to_schema()

    def delete(self, product_id: int) -> bool:
        """Delete product."""
        db_product = self.session.get(ProductDB, product_id)
        if db_product:
            self.session.delete(db_product)
            self.session.commit()
            return True
        return False
