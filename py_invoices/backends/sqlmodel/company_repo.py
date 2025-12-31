"""SQLModel company repository implementation."""

from pydantic_invoices.interfaces import CompanyRepository  # type: ignore[import-untyped]
from pydantic_invoices.schemas.company import (  # type: ignore[import-untyped]
    Company,
    CompanyCreate,
)
from sqlmodel import Session, select

from .models import CompanyDB


class SQLModelCompanyRepository(CompanyRepository):  # type: ignore[misc]
    """Generic SQLModel implementation for Company repository."""

    def __init__(self, session: Session):
        """Initialize with SQLModel session."""
        self.session = session

    def create(self, data: CompanyCreate) -> Company:
        """Create company in database."""
        db_company = CompanyDB(**data.model_dump())
        self.session.add(db_company)
        self.session.commit()
        self.session.refresh(db_company)
        return db_company.to_schema()

    def get_by_id(self, company_id: int) -> Company | None:
        """Get company by ID."""
        db_company = self.session.get(CompanyDB, company_id)
        return db_company.to_schema() if db_company else None

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Company]:
        """Get all companies with pagination."""
        stmt = select(CompanyDB).offset(skip).limit(limit)
        db_companies = self.session.exec(stmt).all()
        return [c.to_schema() for c in db_companies]

    def get_active(self) -> list[Company]:
        """Get all active companies."""
        stmt = select(CompanyDB).where(CompanyDB.is_active == True)  # noqa: E712
        db_companies = self.session.exec(stmt).all()
        return [c.to_schema() for c in db_companies]

    def get_by_name(self, name: str) -> Company | None:
        """Get company by name."""
        stmt = select(CompanyDB).where(CompanyDB.name == name)
        db_company = self.session.exec(stmt).first()
        return db_company.to_schema() if db_company else None

    def get_default(self) -> Company | None:
        """Get the default company."""
        stmt = select(CompanyDB).where(CompanyDB.is_default == True)  # noqa: E712
        db_company = self.session.exec(stmt).first()
        return db_company.to_schema() if db_company else None

    def update(self, company: Company) -> Company:
        """Update company."""
        db_company = self.session.get(CompanyDB, company.id)
        if not db_company:
            raise ValueError(f"Company {company.id} not found")

        for key, value in company.model_dump(exclude={"id"}).items():
            setattr(db_company, key, value)

        self.session.commit()
        self.session.refresh(db_company)
        return db_company.to_schema()

    def delete(self, company_id: int) -> bool:
        """Delete company."""
        db_company = self.session.get(CompanyDB, company_id)
        if db_company:
            self.session.delete(db_company)
            self.session.commit()
            return True
        return False
