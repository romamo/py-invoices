"""Company operations."""

from dataclasses import dataclass

from pydantic import ValidationError
from pydantic_invoices.interfaces import CompanyRepository
from pydantic_invoices.schemas.company import Company, CompanyCreate, CompanyUpdate

from py_invoices.core.audit_service import AuditEntity, AuditService
from py_invoices.core.paging import iter_all
from py_invoices.operations.errors import CompanyNotFoundError, NumberPrefixError
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
    number_prefix: str | None = None,
) -> Company:
    repo = factory.create_company_repository()
    prefix = _free_prefix(repo, number_prefix, None) if number_prefix is not None else None
    company = repo.create(
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
            number_prefix=prefix,
        )
    )
    AuditService(audit_repo=factory.create_audit_repository()).log_record_event(
        AuditEntity.COMPANY, company.id, "CREATED", new_value=company.name
    )
    return company


def set_number_prefix(factory: RepositoryFactory, company_id: int, number_prefix: str) -> Company:
    """Give a company its own number series; numbers already issued keep their prefix."""
    repo = factory.create_company_repository()
    company = repo.get_by_id(company_id)
    if company is None:
        raise CompanyNotFoundError(company_id)
    prefix = _free_prefix(repo, number_prefix, company_id)
    updated = repo.update(company.model_copy(update={"number_prefix": prefix}))
    AuditService(audit_repo=factory.create_audit_repository()).log_record_event(
        AuditEntity.COMPANY,
        company_id,
        "NUMBER_PREFIX_SET",
        old_value=company.number_prefix,
        new_value=prefix,
    )
    return updated


def _free_prefix(repo: CompanyRepository, number_prefix: str, company_id: int | None) -> str:
    """A well-formed prefix that no other company's series uses."""
    try:
        prefix = CompanyUpdate(number_prefix=number_prefix).number_prefix
    except ValidationError as e:
        raise NumberPrefixError(
            f"Number prefix {number_prefix!r} must be 1-20 letters or digits", number_prefix
        ) from e
    if prefix is None:
        raise NumberPrefixError("Number prefix must not be empty", number_prefix)
    holder = next(
        (c for c in iter_all(repo) if c.id != company_id and c.number_prefix == prefix), None
    )
    if holder is not None:
        raise NumberPrefixError(
            f"Number prefix {prefix!r} already gives company {holder.id} its series", prefix
        )
    return prefix
