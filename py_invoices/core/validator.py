from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import defusedxml.ElementTree as ET  # noqa: N817
from defusedxml import DefusedXmlException

if TYPE_CHECKING:
    from pydantic_invoices.schemas import Invoice


class MessageLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ValidationMessage:
    level: MessageLevel
    text: str


@dataclass
class ValidationResult:
    success: bool
    messages: list[ValidationMessage] = field(default_factory=list)

    def add_message(self, level: MessageLevel, text: str) -> None:
        self.messages.append(ValidationMessage(level, text))

    def fail(self, text: str) -> None:
        self.add_message(MessageLevel.ERROR, text)
        self.success = False


@dataclass(frozen=True, slots=True)
class _DocumentRules:
    label: str
    type_code_path: str
    line_path: str


_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
_INVOICE_NS = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
_CREDIT_NOTE_NS = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"

_RULES_BY_ROOT = {
    f"{{{_INVOICE_NS}}}Invoice": _DocumentRules(
        "Invoice", "cbc:InvoiceTypeCode", "cac:InvoiceLine"
    ),
    f"{{{_CREDIT_NOTE_NS}}}CreditNote": _DocumentRules(
        "CreditNote", "cbc:CreditNoteTypeCode", "cac:CreditNoteLine"
    ),
}


class UBLValidator:
    """Checks the structure of UBL 2.1 Invoice and CreditNote documents."""

    NAMESPACES: ClassVar[dict[str, str]] = {"cbc": _CBC, "cac": _CAC}

    @staticmethod
    def validate_file(xml_path: str) -> ValidationResult:
        """Validate a UBL XML file; a missing file is reported as a failed result."""
        path = Path(xml_path)
        if not path.is_file():
            result = ValidationResult(success=True)
            result.fail(f"Fatal: File not found - {xml_path}")
            return result
        return UBLValidator.validate_bytes(path.read_bytes(), source=xml_path)

    @staticmethod
    def validate_bytes(content: bytes, source: str) -> ValidationResult:
        """Validate UBL XML content against basic UBL 2.1 structural requirements."""
        result = ValidationResult(success=True)
        result.add_message(MessageLevel.INFO, f"Validating {source}...")

        try:
            root = ET.fromstring(content)
        except (ET.ParseError, DefusedXmlException) as e:
            result.fail(f"Fatal: XML Parse Error - {e}")
            return result

        rules = _RULES_BY_ROOT.get(root.tag)
        if rules is None:
            expected = " or ".join(_RULES_BY_ROOT)
            result.fail(f"Root element mismatch. Found: {root.tag}, Expected: {expected}")
            return result
        result.add_message(MessageLevel.SUCCESS, f"Root element is UBL {rules.label}-2")

        fields_to_check = [
            ("cbc:ID", "Document ID"),
            ("cbc:IssueDate", "Issue Date"),
            (rules.type_code_path, "Type Code"),
            ("cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name", "Supplier Name"),
            ("cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name", "Customer Name"),
            ("cac:TaxTotal/cbc:TaxAmount", "Tax Amount"),
            ("cac:LegalMonetaryTotal/cbc:PayableAmount", "Payable Amount"),
        ]
        for path, name in fields_to_check:
            elem = root.find(path, UBLValidator.NAMESPACES)
            if elem is not None and elem.text:
                result.add_message(MessageLevel.SUCCESS, f"Found {name}: {elem.text}")
            else:
                result.fail(f"Missing Mandatory Field: {name} ({path})")

        lines = root.findall(rules.line_path, UBLValidator.NAMESPACES)
        result.add_message(MessageLevel.INFO, f"Found {len(lines)} {rules.label} Lines")
        if lines:
            result.add_message(MessageLevel.SUCCESS, "Contains line items")
        else:
            result.fail("No line items found (UBL requires at least one)")
        return result


class BusinessValidator:
    """Validates business logic and state transitions."""

    @staticmethod
    def validate_state_transition(old_status: str, new_status: str) -> None:
        """Validate state transition for strict state machine.

        Args:
            old_status: Current status
            new_status: New status

        Raises:
            ValueError: If transition is invalid
        """
        from pydantic_invoices.schemas import InvoiceStatus

        # Valid Transitions:
        # DRAFT -> SENT
        # SENT -> PAID | PARTIALLY_PAID | CANCELLED
        # SENT -> CREDITED (via Credit Note logic, handled separately usually)
        # PAID -> REFUNDED | CREDITED (maybe?)

        if old_status == new_status:
            return

        # If already in a closed state, cannot change status
        # (unless to CREDITED/REFUNDED in specific flows)
        if old_status in (InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED, InvoiceStatus.CREDITED):
            raise ValueError(f"Cannot change status from final state {old_status}")

        if old_status == InvoiceStatus.PAID and new_status not in (
            InvoiceStatus.REFUNDED,
            InvoiceStatus.CREDITED,
        ):
            raise ValueError(f"Cannot change status from PAID to {new_status}")

        if old_status == InvoiceStatus.SENT:
            allowed = (
                InvoiceStatus.PAID,
                InvoiceStatus.PARTIALLY_PAID,
                InvoiceStatus.CANCELLED,
                InvoiceStatus.CREDITED,
            )
            if new_status not in allowed:
                raise ValueError(
                    f"Cannot change status from SENT to {new_status}. Must be one of {allowed}"
                )

        if old_status == InvoiceStatus.DRAFT:
            # Draft effectively can go to SENT.
            # Going directly to PAID is possible for simple flows but discouraged.
            pass

    @staticmethod
    def validate_modification(invoice: "Invoice") -> None:
        """Validate if invoice can be modified based on its state.

        Args:
            invoice: Invoice object

        Raises:
            ValueError: If modification is not allowed
        """
        from pydantic_invoices.schemas import InvoiceStatus

        # In strict mode, only DRAFT invoices can be edited (content, lines, amounts)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(
                f"Cannot modify invoice {invoice.number} because it is in {invoice.status} state. "
                "Only DRAFT invoices can be edited. "
                "To correct a SENT invoice, issue a Credit Note."
            )

    @staticmethod
    def validate_dates(invoice: "Invoice") -> None:
        """Validate invoice dates.

        Args:
            invoice: Invoice object

        Raises:
            ValueError: If dates are invalid
        """
        if invoice.due_date and invoice.issue_date and invoice.due_date < invoice.issue_date:
            raise ValueError(
                f"Invoice {invoice.number} has a due date ({invoice.due_date}) "
                f"earlier than its issue date ({invoice.issue_date})."
            )
