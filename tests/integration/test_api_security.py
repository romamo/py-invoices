"""API authentication, pagination and rendering safety."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pydantic_invoices.schemas import InvoiceCreate, InvoiceLineCreate
from pydantic_invoices.schemas.company import CompanyCreate
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.api.deps import get_factory
from py_invoices.api.main import app
from py_invoices.api.routers.validation import MAX_UPLOAD_BYTES
from py_invoices.api.security import API_KEY_HEADER, get_api_settings
from py_invoices.config import InvoiceSettings

KEY = "s3cret"


@pytest.fixture
def factory() -> Generator[RepositoryFactory, None, None]:
    shared = RepositoryFactory("memory")

    def scoped() -> Generator[RepositoryFactory, None, None]:
        with shared.scope() as scoped_factory:
            yield scoped_factory

    app.dependency_overrides[get_factory] = scoped
    app.dependency_overrides[get_api_settings] = lambda: InvoiceSettings(api_key=KEY)
    yield shared
    app.dependency_overrides.clear()


@pytest.fixture
def client(factory: RepositoryFactory) -> TestClient:
    return TestClient(app, headers={API_KEY_HEADER: KEY})


def _invoice(client: TestClient, number: str, client_name: str = "Acme") -> dict:
    client_id = client.post("/clients/", json={"name": client_name}).json()["id"]
    response = client.post(
        "/invoices/",
        json={
            "number": number,
            "status": "SENT",
            "client_id": client_id,
            "client_name_snapshot": client_name,
            "company_name_snapshot": "Co",
            "company_address_snapshot": "Road",
            "lines": [{"description": "Item", "quantity": 1, "unit_price": "10"}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_requests_without_valid_key_are_rejected(factory: RepositoryFactory) -> None:
    anonymous = TestClient(app)
    assert anonymous.get("/invoices/").status_code == 401
    wrong = TestClient(app, headers={API_KEY_HEADER: "nope"})
    assert wrong.get("/invoices/").status_code == 401
    assert anonymous.get("/").status_code == 200  # the static web app stays public


def test_unconfigured_key_refuses_everything(factory: RepositoryFactory) -> None:
    app.dependency_overrides[get_api_settings] = lambda: InvoiceSettings(api_key=None)
    response = TestClient(app, headers={API_KEY_HEADER: ""}).get("/invoices/")
    assert response.status_code == 503
    assert "INVOICES_API_KEY" in response.json()["detail"]


def test_cors_does_not_allow_arbitrary_origins(client: TestClient) -> None:
    response = client.options(
        "/invoices/",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_offset_pages_and_duplicate_numbers(client: TestClient) -> None:
    for n in range(3):
        _invoice(client, f"INV-{n}", client_name=f"C{n}")
    page = client.get("/invoices/?limit=2&offset=1").json()
    assert [i["number"] for i in page] == ["INV-1", "INV-2"]

    duplicate = client.post("/invoices/", json={"number": "INV-0", "client_id": 1, "lines": []})
    assert duplicate.status_code == 409
    assert any(log["action"] == "CREATED" for log in client.get("/audit/").json())


def test_html_escapes_stored_values(client: TestClient) -> None:
    _invoice(client, "INV-X", client_name="<script>alert(1)</script>")
    html = client.get("/invoices/INV-X/html")
    assert html.status_code == 200
    assert "<script>alert" not in html.text
    assert "&lt;script&gt;" in html.text


def test_html_uses_company_record_when_invoice_has_no_snapshot(
    client: TestClient, factory: RepositoryFactory
) -> None:
    factory.create_company_repository().create(
        CompanyCreate(name="Record Co", address="Record St", is_default=True)
    )
    client_id = client.post("/clients/", json={"name": "B"}).json()["id"]
    client.post(
        "/invoices/",
        json={"number": "INV-R", "client_id": client_id, "lines": []},
    )
    assert "Record Co" in client.get("/invoices/INV-R/html").text


def test_validation_rejects_oversized_uploads(client: TestClient) -> None:
    big = b"<a>" + b" " * MAX_UPLOAD_BYTES + b"</a>"
    response = client.post("/validation/ubl", files={"file": ("big.xml", big)})
    assert response.status_code == 413


def test_credit_notes_and_unsafe_numbers_cannot_be_posted_as_invoices(
    client: TestClient,
) -> None:
    original = _invoice(client, "INV-ORIG")
    fake_credit = client.post(
        "/invoices/",
        json={
            "number": "FAKE-CN",
            "type": "CREDIT_NOTE",
            "original_invoice_id": original["id"],
            "client_id": original["client_id"],
            "lines": [{"description": "x", "quantity": 1, "unit_price": "5000"}],
        },
    )
    assert fake_credit.status_code == 422
    traversal = client.post(
        "/invoices/", json={"number": "../../evil", "client_id": original["client_id"]}
    )
    assert traversal.status_code == 422


def test_mixed_currency_summary_is_a_conflict(
    client: TestClient, factory: RepositoryFactory
) -> None:
    client_id = client.post("/clients/", json={"name": "M"}).json()["id"]
    repo = factory.create_invoice_repository()
    for number, currency in [("U", "USD"), ("E", "EUR")]:
        repo.create(
            InvoiceCreate(
                number=number,
                client_id=client_id,
                lines=[
                    InvoiceLineCreate(description="x", quantity=1, unit_price=Money("1", currency))
                ],
            )
        )
    response = client.get("/invoices/summary")
    assert response.status_code == 409
    assert "EUR, USD" in response.json()["detail"]
