"""Regression tests for issues found in the second review."""

import threading
from datetime import datetime
from pathlib import Path

import pytest
from pydantic_invoices.schemas import (
    ClientCreate,
    Invoice,
    InvoiceCreate,
    InvoiceLine,
    InvoiceLineCreate,
    InvoiceStatus,
    PaymentCreate,
)
from pydantic_invoices.vo import Money

from py_invoices import RepositoryFactory
from py_invoices.core.audit_service import AuditService
from py_invoices.core.credit_service import CreditService
from py_invoices.core.html_service import output_path
from py_invoices.core.summary import MixedCurrencyError
from py_invoices.core.totals import invoice_totals


def _factory(backend: str, tmp_path: Path) -> RepositoryFactory:
    if backend == "files":
        return RepositoryFactory("files", root_dir=str(tmp_path / "data"), file_format="json")
    if backend == "sqlite":
        return RepositoryFactory("sqlite", database_url=f"sqlite:///{tmp_path / 'db.sqlite'}")
    return RepositoryFactory("memory")


BACKENDS = ["memory", "files", "sqlite"]


def _invoice(factory: RepositoryFactory, number: str, *prices: Money, tax: float = 0) -> Invoice:
    client = factory.create_client_repository().create(ClientCreate(name=f"C-{number}"))
    return factory.create_invoice_repository().create(
        InvoiceCreate(
            number=number,
            client_id=client.id,
            status=InvoiceStatus.SENT,
            lines=[
                InvoiceLineCreate(description=f"L{i}", quantity=1, unit_price=p, tax_rate=tax)
                for i, p in enumerate(prices)
            ],
        )
    )


@pytest.mark.parametrize("backend", BACKENDS)
def test_currency_survives_every_backend(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    invoice = _invoice(factory, "E-1", Money("0.10", "EUR"))
    factory.create_payment_repository().create(
        PaymentCreate(
            invoice_id=invoice.id,
            amount=Money("0.05", "EUR"),
            payment_date=datetime.now(),
            payment_method="bank",
        )
    )
    stored = factory.create_invoice_repository().get_by_id(invoice.id)
    assert stored.lines[0].unit_price == Money("0.10", "EUR")
    assert stored.payments[0].amount == Money("0.05", "EUR")
    assert factory.create_invoice_repository().get_summary().total_due == Money("0.05", "EUR")


@pytest.mark.parametrize("backend", BACKENDS)
def test_mixed_currencies_are_reported_not_crashed(backend: str, tmp_path: Path) -> None:
    factory = _factory(backend, tmp_path)
    _invoice(factory, "U-1", Money("1", "USD"))
    _invoice(factory, "E-1", Money("1", "EUR"))
    with pytest.raises(MixedCurrencyError, match="EUR, USD"):
        factory.create_invoice_repository().get_summary()


def test_invoices_without_lines_do_not_force_usd(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    _invoice(factory, "E-1", Money("5", "EUR"))
    _invoice(factory, "EMPTY")
    assert factory.create_invoice_repository().get_summary().total_amount == Money("5", "EUR")


def test_credit_limits_and_summary_use_tax_inclusive_totals(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    invoice = _invoice(factory, "T-1", Money("100", "USD"), tax=20)
    repo = factory.create_invoice_repository()
    assert repo.get_summary().total_due == Money("120.00")

    CreditService(repo).create_credit_note(invoice, reason="all")
    assert repo.get_by_id(invoice.id).status is InvoiceStatus.CREDITED
    assert repo.get_summary().total_due == Money("0")


def test_refused_status_change_leaves_no_credit_note(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    invoice = _invoice(factory, "R-1", Money("10"))
    repo = factory.create_invoice_repository()
    refunded = repo.update(invoice.model_copy(update={"status": InvoiceStatus.REFUNDED}))
    with pytest.raises(ValueError, match="REFUNDED"):
        CreditService(repo).create_credit_note(refunded)
    paid = repo.update(invoice.model_copy(update={"status": InvoiceStatus.PAID}))
    CreditService(repo).create_credit_note(paid)  # PAID -> CREDITED is allowed
    assert [i.number for i in repo.get_all()] == ["R-1", f"CN-{datetime.now().year}-0001"]


def test_a_line_cannot_be_credited_twice(tmp_path: Path) -> None:
    factory = _factory("memory", tmp_path)
    invoice = _invoice(factory, "D-1", Money("100"), Money("100"))
    service = CreditService(factory.create_invoice_repository())
    service.create_credit_note(invoice, refund_lines_indices=[0])
    with pytest.raises(ValueError, match="already credited"):
        service.create_credit_note(invoice, refund_lines_indices=[0])
    service.create_credit_note(invoice, refund_lines_indices=[1])


def test_sql_audit_limit_keeps_most_recent(tmp_path: Path) -> None:
    factory = _factory("sqlite", tmp_path)
    service = AuditService(audit_repo=factory.create_audit_repository())
    for n in range(5):
        service.log_status_changed(n, invoice_number=f"N{n}", new_status="PAID")
    from py_invoices.operations.audit import list_audit_logs

    logs = list_audit_logs(factory, None, None, None, limit=2)
    assert [log.invoice_number for log in logs] == ["N3", "N4"]


@pytest.mark.parametrize("backend", ["memory", "files"])
def test_concurrent_creates_get_distinct_ids(backend: str, tmp_path: Path) -> None:
    repo = _factory(backend, tmp_path).create_client_repository()
    ids: list[int] = []

    def worker(n: int) -> None:
        ids.append(repo.create(ClientCreate(name=f"C{n}")).id)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(ids)) == 20
    assert len(repo.get_all()) == 20


def test_output_paths_cannot_escape_the_output_dir(tmp_path: Path) -> None:
    for name in ["../evil.pdf", "a/b.pdf", ".hidden", "a\\b.pdf"]:
        with pytest.raises(ValueError, match="Unsafe"):
            output_path(str(tmp_path), name)
    assert output_path(str(tmp_path), "INV 1.pdf") == str(tmp_path / "INV 1.pdf")


def test_line_amounts_are_rounded_before_summing() -> None:
    lines = [
        InvoiceLine(id=i, invoice_id=1, description="x", quantity=1, unit_price="0.3333")
        for i in range(3)
    ]
    totals = invoice_totals(Invoice(id=1, number="R", client_id=1, lines=lines))
    assert totals.net == Money("0.99")
