from py_invoices.core.numbering_service import NumberingService
from py_invoices.plugins.factory import RepositoryFactory


def test_import() -> None:
    """Test importing the package."""
    import py_invoices

    print(f"Successfully imported py_invoices version: {py_invoices.__version__}")


def test_basic_flow() -> None:
    """Test a simple create flow."""
    # Setup
    factory = RepositoryFactory(backend="memory")
    repo = factory.create_invoice_repository()
    numbering = NumberingService(invoice_repo=repo)

    # Check backend health
    assert factory.health_check() is True
    print("Health check passed")

    # Check numbering
    next_num = numbering.generate_number()
    assert next_num.startswith("INV-")
    print(f"Generated number: {next_num}")


if __name__ == "__main__":
    test_import()
    test_basic_flow()
