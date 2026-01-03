from datetime import datetime, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic_invoices.schemas import InvoiceStatus

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.api.main import app

# Shared factory for the module to persist state between API calls
_shared_factory = RepositoryFactory("memory")

def get_shared_memory_factory() -> Generator[RepositoryFactory, None, None]:
    yield _shared_factory

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_repository_factory():
    """Override the repository factory for this test module."""
    app.dependency_overrides[get_factory] = get_shared_memory_factory
    yield
    app.dependency_overrides.pop(get_factory, None)

@pytest.fixture(autouse=True)
def clear_memory_state():
    """Clear memory state before each test."""
    _shared_factory.cleanup()
    _shared_factory.plugin.initialize()  # Re-init

def test_create_credit_note_api() -> None:
    """Test creating a credit note via API."""
    # 1. Create Client
    response = client.post(
        "/clients/",
        json={
            "name": "API Credit Client",
            "address": "123 API St",
            "tax_id": "API-999",
        },
    )
    assert response.status_code == 200
    client_data = response.json()
    client_id = client_data["id"]

    # 2. Create Invoice
    response = client.post(
        "/invoices/",
        json={
            "number": "INV-API-001",
            "issue_date": datetime.now().date().isoformat(),
            "due_date": (datetime.now() + timedelta(days=30)).date().isoformat(),
            "status": InvoiceStatus.DRAFT,
            "client_id": client_id,
            "lines": [
                {"description": "Service A", "quantity": 1, "unit_price": 100.0}
            ],
            "client_name_snapshot": "Snapshot Name",
            "client_address_snapshot": "Snapshot Address",
            "client_tax_id_snapshot": "Snapshot Tax",
        },
    )
    assert response.status_code == 200
    invoice_data = response.json()
    invoice_id = invoice_data["id"]

def test_create_credit_note_flow() -> None:
    # 1. Create Client
    response = client.post(
        "/clients/",
        json={
            "name": "API Credit Client",
            "address": "123 API St",
            "tax_id": "API-999",
        },
    )
    assert response.status_code == 200
    client_id = response.json()["id"]

    # 2. Create Invoice
    response = client.post(
        "/invoices/",
        json={
            "number": "INV-API-002",
            "issue_date": datetime.now().date().isoformat(),
            "due_date": (datetime.now() + timedelta(days=30)).date().isoformat(),
            "status": InvoiceStatus.DRAFT,
            "client_id": client_id,
            "lines": [
                {"description": "Service A", "quantity": 1, "unit_price": 100.0}
            ],
            "client_name_snapshot": "Snapshot Name",
            "client_address_snapshot": "Snapshot Address",
            "client_tax_id_snapshot": "Snapshot Tax",
        },
    )
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    invoice_id = response.json()["id"]

    # 3. Update Invoice Status to SENT (Direct Repo access needed)
    repo = _shared_factory.create_invoice_repository()
    
    invoice = repo.get_by_id(invoice_id)
    assert invoice is not None, f"Invoice {invoice_id} not found in repo used by test"
    
    invoice.status = InvoiceStatus.SENT
    repo.update(invoice)

    # 4. Create Credit Note
    response = client.post(
        "/credit-notes/",
        json={
            "original_invoice_id": invoice_id,
            "reason": "Customer unhappy",
        },
    )
    if response.status_code != 201:
        print(response.json())
    assert response.status_code == 201
    cn_data = response.json()
    assert cn_data["original_invoice_id"] == invoice_id
    assert cn_data["reason"] == "Customer unhappy"
    assert "CN-" in cn_data["number"]

