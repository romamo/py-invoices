"""Company operations."""

from dataclasses import dataclass

from pydantic_invoices.schemas.company import Company, CompanyCreate

from py_invoices.plugins.factory import RepositoryFactory


@dataclass(frozen=True, slots=True)
class CompanyListing:
    companies: list[Company]
    default_id: int | None


def list_companies(factory: RepositoryFactory) -> CompanyListing:
    """Active companies and the ID of the default one, if any."""
    repo = factory.create_company_repository()
    companies = repo.get_active()
    default = repo.get_default() if companies else None
    return CompanyListing(companies=companies, default_id=default.id if default else None)


def default_company(factory: RepositoryFactory) -> Company | None:
    return factory.create_company_repository().get_default()


def create_company(
    factory: RepositoryFactory,
    name: str,
    tax_id: str | None,
    address: str | None,
    email: str | None,
    phone: str | None,
) -> Company:
    return factory.create_company_repository().create(
        CompanyCreate(
            name=name,
            tax_id=tax_id,
            address=address,
            email=email,
            phone=phone,
            legal_name=None,
            registration_number=None,
            city=None,
            postal_code=None,
            country=None,
            website=None,
            logo_path=None,
        )
    )
