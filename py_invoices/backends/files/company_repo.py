"""File-based company repository."""

from pathlib import Path

from pydantic_invoices.interfaces import CompanyRepository
from pydantic_invoices.schemas.company import Company, CompanyCreate

from .storage import FileStorage


class FileCompanyRepository(CompanyRepository):
    """File-based implementation of CompanyRepository."""

    def __init__(self, root_dir: str | Path, file_format: str = "json") -> None:
        """Initialize file repository."""
        self.storage = FileStorage[Company](
            root_dir, "companies", Company, default_format=file_format
        )

    def create(self, data: CompanyCreate) -> Company:
        """Create a new company."""
        company_id = self.storage.get_next_id()
        company = Company(id=company_id, **data.model_dump())
        self.storage.save(company, company_id)
        return company

    def get_by_id(self, company_id: int) -> Company | None:
        """Get company by ID."""
        return self.storage.load(company_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Company]:
        """Get all companies with pagination."""
        companies = self.storage.load_all()
        return companies[skip : skip + limit]

    def get_active(self) -> list[Company]:
        """Get all active companies."""
        return [c for c in self.storage.load_all() if c.is_active]

    def get_by_name(self, name: str) -> Company | None:
        """Get company by name."""
        for c in self.storage.load_all():
            if c.name == name:
                return c
        return None

    def get_default(self) -> Company | None:
        """Get default company."""
        for company in self.storage.load_all():
            if company.is_default:
                return company
        return None

    def update(self, company: Company) -> Company:
        """Update company."""
        existing = self.storage.load(company.id)
        if not existing:
            raise ValueError(f"Company {company.id} not found")

        self.storage.save(company, company.id)
        return company

    def delete(self, company_id: int) -> bool:
        """Delete company."""
        return self.storage.delete(company_id)
