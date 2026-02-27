import os
import shutil
import tempfile
from datetime import date

import pytest
from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceLineCreate, InvoiceStatus
from pydantic_invoices.schemas.company import CompanyCreate
from pydantic_invoices.schemas.payment_note import PaymentNoteCreate

from py_invoices.core.html_service import HTMLService
from py_invoices.plugins.factory import RepositoryFactory


class TestUserScenario:
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for file storage."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_full_invoice_flow(self, temp_dir) -> None:
        """Test a complete user flow from company creation to invoice generation and validation."""

        # 1. Initialize RepositoryFactory with 'files' backend
        factory = RepositoryFactory(backend="files", root_dir=temp_dir, file_format="json")

        # Create repositories
        company_repo = factory.create_company_repository()
        client_repo = factory.create_client_repository()
        invoice_repo = factory.create_invoice_repository()
        payment_note_repo = factory.create_payment_note_repository()

        # 2. Company Creation
        company_data = CompanyCreate(
            name="Acme Corp",
            address="123 Tech Blvd, Silicon Valley, CA",
            tax_id="US-999999",
            email="contact@acme.com",
            phone="+1-555-0100",
        )
        company = company_repo.create(company_data)
        assert company.id is not None
        assert company.name == "Acme Corp"

        # 3. Client Creation
        client_data = ClientCreate(
            name="Globex Corporation",
            address="456 Business Rd, New York, NY",
            tax_id="US-888888",
            email="procurement@globex.com",
        )
        client = client_repo.create(client_data)
        assert client.id is not None
        assert client.name == "Globex Corporation"

        # 4. Payment Note Creation
        payment_note_data = PaymentNoteCreate(
            title="Bank Transfer", content="Please transfer to IBAN: US123456789", is_default=True
        )
        payment_note = payment_note_repo.create(payment_note_data)

        # 5. Invoice Creation
        invoice_data = InvoiceCreate(
            number="INV-001",
            client_id=client.id,
            company_id=company.id,
            date=date.today(),
            due_date=date.today(),
            status=InvoiceStatus.DRAFT,
            lines=[
                InvoiceLineCreate(
                    description="Consulting Services", quantity=10, unit_price=150.0, tax_rate=0.0
                ),
                InvoiceLineCreate(
                    description="Software License", quantity=1, unit_price=500.0, tax_rate=0.0
                ),
            ],
            payment_note_id=payment_note.id,
            client_name_snapshot=client.name,
            client_address_snapshot=client.address,
            client_tax_id_snapshot=client.tax_id,
            company_name_snapshot=company.name,
            company_address_snapshot=company.address,
            company_tax_id_snapshot=company.tax_id,
            payment_terms=payment_note.content,
        )

        invoice = invoice_repo.create(invoice_data)

        assert invoice.id is not None
        assert invoice.number is not None  # Should be auto-generated or default
        assert invoice.total_amount == 2000.0  # (10*150) + (1*500)
        assert invoice.client_name_snapshot == "Globex Corporation"

        # 6. HTML Generation
        html_service = HTMLService(output_dir=os.path.join(temp_dir, "output"))

        # Prepare context for template
        company_dict = company.model_dump()

        output_path = html_service.save_html(
            invoice=invoice, company=company_dict, payment_notes=[payment_note]
        )

        assert os.path.exists(output_path)

        # 7. Validation of Generated HTML Content
        with open(output_path) as f:
            content = f.read()

            # Check Company Info
            assert "Acme Corp" in content
            assert "123 Tech Blvd" in content

            # Check Client Info
            assert "Globex Corporation" in content
            assert "456 Business Rd" in content

            # Check Items
            assert "Consulting Services" in content
            assert "10" in content  # Quantity
            assert "150.0" in content  # Price

            # Check Totals
            assert "2000.0" in content

            # Check Payment Note
            assert "Bank Transfer" in content or "Please transfer to IBAN" in content
