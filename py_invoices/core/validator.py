import xml.etree.ElementTree as ET
from rich.console import Console

console = Console()

class UBLValidator:
    """Validates UBL 2.1 XML invoices."""
    
    NAMESPACES = {
        'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    @staticmethod
    def validate_file(xml_path: str) -> bool:
        """
        Validate a UBL XML file against basic UBL 2.1 structural requirements.
        
        Args:
            xml_path: Path to the XML file to validate.
            
        Returns:
            bool: True if validation passed, False otherwise.
        """
        console.print(f"Validating [bold]{xml_path}[/bold]...")
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            success = True
            
            # 1. Validate Root Element
            expected_tag = f"{{{UBLValidator.NAMESPACES['ubl']}}}Invoice"
            if root.tag == expected_tag:
                 console.print("[green]✓ Root element is UBL Invoice-2[/green]")
            else:
                 console.print(f"[red]✗ Root element mismatch. Found: {root.tag}, Expected: {expected_tag}[/red]")
                 success = False
            
            # 2. Validate Key Fields
            def check_field(path: str, name: str) -> bool:
                elem = root.find(path, UBLValidator.NAMESPACES)
                if elem is not None and elem.text:
                    console.print(f"[green]✓ Found {name}: {elem.text}[/green]")
                    return True
                else:
                    console.print(f"[red]✗ Missing Mandaory Field: {name} ({path})[/red]")
                    return False

            fields_to_check = [
                ('cbc:ID', "Invoice ID"),
                ('cbc:IssueDate', "Issue Date"),
                ('cbc:InvoiceTypeCode', "Invoice Type Code"),
                ('cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name', "Supplier Name"),
                ('cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name', "Customer Name"),
                ('cac:TaxTotal/cbc:TaxAmount', "Tax Amount"),
                ('cac:LegalMonetaryTotal/cbc:PayableAmount', "Payable Amount")
            ]
            
            for path, name in fields_to_check:
                if not check_field(path, name):
                    success = False

            # 3. Check Line Items
            lines = root.findall('cac:InvoiceLine', UBLValidator.NAMESPACES)
            console.print(f"[blue]ℹ Found {len(lines)} Invoice Lines[/blue]")
            if len(lines) > 0:
                 console.print("[green]✓ Contains line items[/green]")
            else:
                 console.print("[yellow]⚠ Warning: No line items found (technical UBL requires at least one)[/yellow]")
                 # We treat this as a warning for now, strictly it might be invalid depending on profile
            
            return success

        except ET.ParseError as e:
            console.print(f"[red]Fatal: XML Parse Error - {e}[/red]")
            return False
        except FileNotFoundError:
            console.print(f"[red]Fatal: File not found - {xml_path}[/red]")
            return False

        except Exception as e:
            console.print(f"[red]Fatal: Validation Error - {e}[/red]")
            return False


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
        from pydantic_invoices.schemas import InvoiceStatus  # type: ignore[import-untyped]

        # Valid Transitions:
        # DRAFT -> SENT
        # SENT -> PAID | PARTIALLY_PAID | CANCELLED
        # SENT -> CREDITED (via Credit Note logic, handled separately usually)
        # PAID -> REFUNDED | CREDITED (maybe?)

        if old_status == new_status:
            return

        # If already in a closed state, cannot change status (unless to CREDITED/REFUNDED in specific flows)
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
                InvoiceStatus.CREDITED
            )
            if new_status not in allowed:
                raise ValueError(f"Cannot change status from SENT to {new_status}. Must be one of {allowed}")

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
        from pydantic_invoices.schemas import Invoice, InvoiceStatus # type: ignore[import-untyped]

        # In strict mode, only DRAFT invoices can be edited (content, lines, amounts)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(
                f"Cannot modify invoice {invoice.number} because it is in {invoice.status} state. "
                "Only DRAFT invoices can be edited. "
                "To correct a SENT invoice, issue a Credit Note."
            )
