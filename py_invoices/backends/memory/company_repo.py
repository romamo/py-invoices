"""In-memory company repository."""

from pydantic_invoices.interfaces import CompanyRepository
from pydantic_invoices.schemas.company import Company, CompanyCreate


class MemoryCompanyRepository(CompanyRepository):
    """In-memory implementation for Company repository."""

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._storage: dict[int, Company] = {}
        self._next_id = 1

    def create(self, data: CompanyCreate) -> Company:
        """Create company."""
        company = Company(id=self._next_id, **data.model_dump())
        self._storage[self._next_id] = company
        self._next_id += 1
        return company

    def get_by_id(self, company_id: int) -> Company | None:
        """Get company by ID."""
        return self._storage.get(company_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[Company]:
        """Get all companies."""
        return list(self._storage.values())[skip : skip + limit]

    def get_active(self) -> list[Company]:
        """Get all active companies."""
        return [c for c in self._storage.values() if c.is_active]

    def get_by_name(self, name: str) -> Company | None:
        """Get company by name."""
        for c in self._storage.values():
            if c.name == name:
                return c
        return None

    def get_default(self) -> Company | None:
        """Get default company."""
        for company in self._storage.values():
            if company.is_default:
                return company
        return None

    def update(self, company: Company) -> Company:
        """Update company."""
        if company.id not in self._storage:
            raise ValueError(f"Company {company.id} not found")
        self._storage[company.id] = company
        return company

    def delete(self, company_id: int) -> bool:
        """Delete company."""
        if company_id in self._storage:
            del self._storage[company_id]
            return True
        return False
