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
    MISPLACED = "misplaced"
    """Stored under a key other than its ID (files backend: file name vs `id`)"""
    UNSEALED = "unsealed"
    """Issued before hashing existed: nothing to check against"""
    UNSEALABLE = "unsealable"
    """Unsealed, and --seal refused to write while the store is inconsistent"""
    SEALED = "sealed"
    """Unsealed until this run recorded its hash (--seal)"""


FAILING = frozenset({Finding.TAMPERED, Finding.MISPLACED, Finding.UNSEALABLE})
"""Findings that make the check fail (exit 1)"""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    number: str
    """Invoice number; for MISPLACED, where the record is stored"""
    finding: Finding
    detail: str


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    checked: int
    drafts: int
    findings: list[IntegrityFinding]

    @property
    def ok(self) -> bool:
        return not any(f.finding in FAILING for f in self.findings)


def _with_hash(invoice: Invoice) -> Invoice:
    return invoice.model_copy(update={"content_hash": content_hash(invoice)})


def _seal_all(factory: RepositoryFactory, invoices: list[Invoice]) -> list[IntegrityFinding]:
    repo = factory.create_invoice_repository()
    audit = AuditService(audit_repo=factory.create_audit_repository())
    findings = []
    for invoice in invoices:
        sealed = repo.update(_with_hash(invoice))
        audit.log_invoice_sealed(sealed)
        findings.append(
            IntegrityFinding(sealed.number, Finding.SEALED, f"hash {sealed.content_hash}")
        )
    return findings


def check_stored_invoices(factory: RepositoryFactory, seal: bool = False) -> IntegrityReport:
    """Recompute the hash of every issued invoice and report the ones that changed.

    Also reports records stored under a key other than their ID (MISPLACED): they are
    listed, but updating them by ID fails or hits another record.

    With `seal`, invoices issued before hashing get a hash of their current content, with
    an audit entry; that hash vouches for the content from now on, not as it was issued.
    Sealing is all-or-nothing: while any record is MISPLACED (its update would fail or
    overwrite another record), nothing is sealed and each unsealed invoice is UNSEALABLE.
    """
    findings = [
        IntegrityFinding(
            record.location,
            Finding.MISPLACED,
            f"holds id {record.record_id}; rename the file to match its id",
        )
        for record in factory.plugin.misplaced_records()
    ]
    misplaced = bool(findings)
    unsealed: list[Invoice] = []
    checked = drafts = 0
    for invoice in list(iter_all(factory.create_invoice_repository())):
        if is_draft(invoice):
            drafts += 1
            continue
        checked += 1
        if invoice.content_hash is None:
            unsealed.append(invoice)
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
    if not seal:
        findings.extend(
            IntegrityFinding(i.number, Finding.UNSEALED, "issued without a hash") for i in unsealed
        )
    else:
        findings.extend(_seal_or_refuse(factory, unsealed, misplaced))
    return IntegrityReport(checked=checked, drafts=drafts, findings=findings)


def _seal_or_refuse(
    factory: RepositoryFactory, unsealed: list[Invoice], misplaced: bool
) -> list[IntegrityFinding]:
    """Seal every unsealed invoice, or none while a misplaced record makes writes unsafe."""
    if not misplaced:
        return _seal_all(factory, unsealed)
    return [
        IntegrityFinding(
            i.number, Finding.UNSEALABLE, "not sealed: the store has misplaced records"
        )
        for i in unsealed
    ]
