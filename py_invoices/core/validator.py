from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET  # noqa: N817

if TYPE_CHECKING:
    from pydantic_invoices.schemas import Invoice

from dataclasses import dataclass, field


@dataclass
class ValidationMessage:
    level: str  # 'info', 'success', 'warning', 'error'
    text: str


@dataclass
class ValidationResult:
    success: bool
    messages: list[ValidationMessage] = field(default_factory=list)

    def add_message(self, level: str, text: str) -> None:
        self.messages.append(ValidationMessage(level, text))


class UBLValidator:
    """Validates UBL 2.1 XML invoices."""

    NAMESPACES = {
        "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    }

    @staticmethod
    def validate_file(xml_path: str) -> ValidationResult:
        """
        Validate a UBL XML file against basic UBL 2.1 structural requirements.

        Args:
            xml_path: Path to the XML file to validate.

        Returns:
            ValidationResult: Result object containing success status and messages.
        """
        result = ValidationResult(success=True)
        result.add_message("info", f"Validating {xml_path}...")

        try:
            tree = ET.parse(xml_path)  # nosec
            root = tree.getroot()

            if root is None:
                result.add_message("error", "XML root is missing")
                result.success = False
                return result

            # 1. Validate Root Element
            expected_tag = f"{{{UBLValidator.NAMESPACES['ubl']}}}Invoice"
            if root.tag == expected_tag:
                result.add_message("success", "Root element is UBL Invoice-2")
            else:
                msg = f"Root element mismatch. Found: {root.tag}, Expected: {expected_tag}"
                result.add_message("error", msg)
                result.success = False

            # 2. Validate Key Fields
            def check_field(path: str, name: str) -> bool:
                elem = root.find(path, UBLValidator.NAMESPACES)
                if elem is not None and elem.text:
                    result.add_message("success", f"Found {name}: {elem.text}")
                    return True
                else:
                    result.add_message("error", f"Missing Mandatory Field: {name} ({path})")
                    return False

            fields_to_check = [
                ("cbc:ID", "Invoice ID"),
                ("cbc:IssueDate", "Issue Date"),
                ("cbc:InvoiceTypeCode", "Invoice Type Code"),
                ("cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name", "Supplier Name"),
                ("cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name", "Customer Name"),
                ("cac:TaxTotal/cbc:TaxAmount", "Tax Amount"),
                ("cac:LegalMonetaryTotal/cbc:PayableAmount", "Payable Amount"),
            ]

            for path, name in fields_to_check:
                if not check_field(path, name):
                    result.success = False

            # 3. Check Line Items
            lines = root.findall("cac:InvoiceLine", UBLValidator.NAMESPACES)
            result.add_message("info", f"Found {len(lines)} Invoice Lines")
            if len(lines) > 0:
                result.add_message("success", "Contains line items")
            else:
                result.add_message(
                    "warning", "No line items found (technical UBL requires at least one)"
                )

            return result

        except ET.ParseError as e:
            result.add_message("error", f"Fatal: XML Parse Error - {e}")
            result.success = False
            return result
        except FileNotFoundError:
            result.add_message("error", f"Fatal: File not found - {xml_path}")
            result.success = False
            return result
        except (ValueError, TypeError) as e:
            result.add_message("error", f"Fatal: Data Error - {e}")
            result.success = False
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

        if old_status == InvoiceStatus.PAID:
            if new_status not in (InvoiceStatus.REFUNDED, InvoiceStatus.CREDITED):
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
        if invoice.due_date and invoice.issue_date:
            if invoice.due_date < invoice.issue_date.date():
                raise ValueError(
                    f"Invoice {invoice.number} has a due date ({invoice.due_date}) "
                    f"earlier than its issue date ({invoice.issue_date.date()})."
                )
