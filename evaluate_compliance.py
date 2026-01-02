
import os
import sys
from datetime import datetime, date
import xml.etree.ElementTree as ET

from py_invoices import RepositoryFactory
from py_invoices.core import UBLService, PDFService
from pydantic_invoices.schemas import InvoiceCreate, InvoiceLineCreate, InvoiceStatus, ClientCreate

def validate_xml_file(xml_path):
    print(f"Validating {xml_path}...")
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Check Namespaces
        ns = {'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
              'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
              'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
        
        if root.tag == f"{{{ns['ubl']}}}Invoice":
            print("[PASS] Root element is UBL Invoice-2")
        else:
            print(f"[FAIL] Root element is {root.tag}, expected {{{ns['ubl']}}}Invoice")
            
        def check_field(path, name):
            elem = root.find(path, ns)
            if elem is not None and elem.text:
                print(f"[PASS] Found {name}: {elem.text}")
            else:
                print(f"[FAIL] Missing {name} ({path})")
                
        check_field('cbc:ID', "Invoice ID")
        check_field('cbc:IssueDate', "Issue Date")
        check_field('cbc:InvoiceTypeCode', "Invoice Type Code")
        check_field('cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name', "Supplier Name")
        check_field('cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name', "Customer Name")
        check_field('cac:TaxTotal/cbc:TaxAmount', "Tax Amount")
        check_field('cac:LegalMonetaryTotal/cbc:PayableAmount', "Payable Amount")
        
        lines = root.findall('cac:InvoiceLine', ns)
        print(f"[INFO] Found {len(lines)} Invoice Lines")
        if len(lines) > 0:
             print("[PASS] Contains line items")
        else:
             print("[WARN] No line items found")
             
    except Exception as e:
        print(f"[ERROR] Validation Failed: {e}")

def evaluate_standards():
    if len(sys.argv) > 1:
        # If argument provided, just validate that file
        validate_xml_file(sys.argv[1])
        return

    print("Evaluating Invoice Standards Compliance (Generation Mode)...\n")
    
    # 1. Setup Environment
    factory = RepositoryFactory(backend="memory")
    client_repo = factory.create_client_repository()
    invoice_repo = factory.create_invoice_repository()
    
    # 2. Create Data
    client = client_repo.create(ClientCreate(
        name="Standard Customer Ltd",
        address="123 Industry Rd, B-1000 Brussels, Belgium",
        tax_id="BE0123456789",
        email="invoices@standard.com"
    ))
    
    invoice = invoice_repo.create(InvoiceCreate(
        number="INV-STD-001",
        issue_date=datetime.now(),
        due_date=date.today(),
        status=InvoiceStatus.UNPAID,
        client_id=client.id,
        client_name_snapshot=client.name,
        client_address_snapshot=client.address,
        client_tax_id_snapshot=client.tax_id,
        lines=[
            InvoiceLineCreate(description="Standard Widget", quantity=10, unit_price=25.0),
            InvoiceLineCreate(description="Service Fee", quantity=1, unit_price=50.0)
        ]
    ))
    
    company_data = {
        "name": "My Compliant Company",
        "address": "99 Regulatory Ave, London, UK",
        "tax_id": "GB987654321",
        "email": "billing@compliant.com"
    }

    # 3. Generate & Validate UBL
    print("--- Checking UBL 2.1 Compliance ---")
    
    try:
        # Hack to find templates if needed, but UBLService might assume them present
        # Assuming we are running from root where py_invoices is available
        import py_invoices
        pkg_dir = os.path.dirname(os.path.abspath(py_invoices.__file__))
        template_dir = os.path.join(pkg_dir, "templates")
        
        ubl_service = UBLService(template_dir=template_dir, output_dir="eval_output")
        os.makedirs("eval_output", exist_ok=True)
        
        xml_path = ubl_service.save_ubl(invoice, company_data)
        print(f"Generated UBL: {xml_path}")
        
        # Parse XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Check Namespaces
        ns = {'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
              'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
              'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'}
        
        # Validate Root
        if root.tag == f"{{{ns['ubl']}}}Invoice":
            print("[PASS] Root element is UBL Invoice-2")
        else:
            print(f"[FAIL] Root element is {root.tag}, expected {{{ns['ubl']}}}Invoice")
            
        # Validate Key Fields
        def check_field(path, name):
            elem = root.find(path, ns)
            if elem is not None and elem.text:
                print(f"[PASS] Found {name}: {elem.text}")
            else:
                print(f"[FAIL] Missing {name} ({path})")
                
        check_field('cbc:ID', "Invoice ID")
        check_field('cbc:IssueDate', "Issue Date")
        check_field('cbc:InvoiceTypeCode', "Invoice Type Code")
        check_field('cac:AccountingSupplierParty/cac:Party/cac:PartyName/cbc:Name', "Supplier Name")
        check_field('cac:AccountingCustomerParty/cac:Party/cac:PartyName/cbc:Name', "Customer Name")
        check_field('cac:TaxTotal/cbc:TaxAmount', "Tax Amount")
        check_field('cac:LegalMonetaryTotal/cbc:PayableAmount', "Payable Amount")
        
        # Check Line Items
        lines = root.findall('cac:InvoiceLine', ns)
        print(f"[INFO] Found {len(lines)} Invoice Lines")
        if len(lines) == 2:
            print("[PASS] Line item count matches")
        else:
             print("[FAIL] Line item count mismatch")
             
    except Exception as e:
        print(f"[ERROR] UBL Evaluation Failed: {e}")
        import traceback
        traceback.print_exc()

    # 4. Generate Factur-X (Optional check)
    print("\n--- Checking Factur-X Capability ---")
    try:
        pdf_service = PDFService(template_dir=template_dir, output_dir="eval_output")
        facturx_path = pdf_service.generate_pdf(invoice, company_data) # This generates normal PDF unless factur-x specific method is called
        # Actually pdf_service has generate_facturx
        if hasattr(pdf_service, 'generate_facturx'):
             # Note: generate_facturx might require external libs (WeasyPrint) which relies on pango/etc
             # We'll try it
             fx_path = pdf_service.generate_facturx(invoice, company_data)
             print(f"[PASS] Generated Factur-X PDF: {fx_path}")
             print("[INFO] (Deep validation of PDF/A-3 requires external tools like verapdf, skipping strict check)")
        else:
             print("[WARN] generate_facturx method not found on PDFService")
             
    except ImportError:
        print("[SKIP] WeasyPrint or dependencies not installed, skipping Factur-X generation")
    except Exception as e:
        print(f"[WARN] Factur-X Generation failed (likely system dependencies): {e}")

if __name__ == "__main__":
    evaluate_standards()
