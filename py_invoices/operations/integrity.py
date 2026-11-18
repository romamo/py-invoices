"""Integrity check of stored invoices: content hashes of issued invoices."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic_invoices.schemas import Invoice

from py_invoices.core.audit_service import AuditService
from py_invoices.core.lifecycle import content_hash, is_draft
from py_invoices.core.paging import iter_all
from py_invoices.plugins.factory import RepositoryFactory


class Finding(StrEnum):
    TAMPERED = "tampered"
    """Issued, and the content no longer matches its hash"""
    UNSEALED = "unsealed"
    """Issued before hashing existed: nothing to check against"""
    SEALED = "sealed"
    """Unsealed until this run recorded its hash (--seal)"""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    number: str
    finding: Finding
    detail: str


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    checked: int
    drafts: int
    findings: list[IntegrityFinding]

    @property
    def ok(self) -> bool:
        return not any(f.finding is Finding.TAMPERED for f in self.findings)


def _seal(factory: RepositoryFactory, invoice: Invoice) -> Invoice:
    sealed = factory.create_invoice_repository().update(
        invoice.model_copy(update={"content_hash": content_hash(invoice)})
    )
    AuditService(audit_repo=factory.create_audit_repository()).log_invoice_sealed(sealed)
    return sealed


def check_stored_invoices(factory: RepositoryFactory, seal: bool = False) -> IntegrityReport:
    """Recompute the hash of every issued invoice and report the ones that changed.

    With `seal`, invoices issued before hashing get a hash of their current content, with
    an audit entry; that hash vouches for the content from now on, not as it was issued.
    """
    findings = []
    checked = drafts = 0
    for invoice in list(iter_all(factory.create_invoice_repository())):
        if is_draft(invoice):
            drafts += 1
            continue
        checked += 1
        if invoice.content_hash is None:
            if seal:
                sealed = _seal(factory, invoice)
                findings.append(
                    IntegrityFinding(sealed.number, Finding.SEALED, f"hash {sealed.content_hash}")
                )
            else:
                findings.append(
                    IntegrityFinding(invoice.number, Finding.UNSEALED, "issued without a hash")
                )
            continue
        actual = content_hash(invoice)
        if actual != invoice.content_hash:
            findings.append(
                IntegrityFinding(
                    invoice.number,
                    Finding.TAMPERED,
                    f"stored hash {invoice.content_hash}, content hashes to {actual}",
                )
            )
    return IntegrityReport(checked=checked, drafts=drafts, findings=findings)
