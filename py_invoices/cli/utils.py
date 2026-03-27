from typing import Any

import typer
from rich.console import Console

from py_invoices import RepositoryFactory
from py_invoices.config import get_settings
from py_invoices.utils.image import file_to_base64_data_uri

console = Console()


def get_console() -> Console:
    return console


def get_factory(backend: str | None = None) -> RepositoryFactory:
    settings = get_settings()
    # Use explicit backend if provided, otherwise use settings
    if backend and backend != settings.backend:
        settings = settings.model_copy(update={"backend": backend})

    return RepositoryFactory.from_settings(settings)


def resolve_company_details(
    factory: Any,
    invoice: Any,
    company_name: str | None = None,
    company_address: str | None = None,
    company_tax_id: str | None = None,
    company_email: str | None = None,
    company_logo_path: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """
    Resolve company details from CLI options, snapshots, or live lookup.
    """
    console = get_console()
    name = company_name
    address = company_address
    tax_id = company_tax_id
    email = company_email
    logo_path = company_logo_path

    # 1. Fallback to snapshots
    if not name:
        name = getattr(invoice, "company_name_snapshot", None)
    if not address:
        address = getattr(invoice, "company_address_snapshot", None)
    if not tax_id:
        tax_id = getattr(invoice, "company_tax_id_snapshot", None)
    if not email:
        email = getattr(invoice, "company_email_snapshot", None)
    if not logo_path:
        logo_path = getattr(invoice, "company_logo_path_snapshot", None)

    # 2. Fallback to live lookup via company_id
    # FIX: Perform lookup if any essential field (name, address, tax_id) is missing
    if (
        (not name or not address or not tax_id or not logo_path)
        and hasattr(invoice, "company_id")
        and invoice.company_id
    ):
        company_repo = factory.create_company_repository()
        company_record = company_repo.get_by_id(invoice.company_id)
        if not company_record:
            console.print(f"[red]Error: Company with ID {invoice.company_id} not found.[/red]")
            raise typer.Exit(code=1)
        if not name:
            name = company_record.name
        if not address:
            address = company_record.address
        if not tax_id:
            tax_id = getattr(company_record, "tax_id", None)
        if not email:
            email = getattr(company_record, "email", None)
        if not logo_path:
            logo_path = getattr(company_record, "logo_path", None)

    # 3. Final validation
    if not name or not address:
        console.print(
            "[red]Error: Company details (name and address) could not be resolved. "
            "Please provide them via --company-name and --company-address or ensure "
            "the invoice has a valid company_id.[/red]"
        )
        raise typer.Exit(code=1)

    company_details = {
        "name": name,
        "address": address,
        "email": email,
        "tax_id": tax_id,
    }
    return company_details, file_to_base64_data_uri(logo_path)
