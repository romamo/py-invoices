"""Factur-X EN 16931: CII XML validated against the official XSD and Schematron rules."""

import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import facturx
import pytest
from pydantic_invoices.schemas import Invoice, InvoiceLine, InvoiceType
from pypdf import PdfReader
from saxonche import PySaxonProcessor, PyXslt30Processor, PyXsltExecutable

from py_invoices.core import CIIService, FacturXDataError, PDFService
from py_invoices.core.pdf_service import PdfSystemLibrariesError, WeasyPrintMissingError

EN16931_XSLT = Path(__file__).parents[1] / "data" / "en16931" / "EN16931-CII-validation.xslt"
FACTURX_XSLT = (
    Path(facturx.__file__).parent
    / "xsd_and_schematron"
    / "facturx-en16931"
    / "FACTUR-X_EN16931.xslt"
)

SELLER = {
    "name": "Seller GmbH",
    "address": "Hauptstr. 1",
    "city": "Berlin",
    "postal_code": "10115",
    "country_code": "DE",
    "tax_id": "DE123456789",
}


def _invoice(number: str = "INV-1", **changes: Any) -> Invoice:
    data: dict[str, Any] = dict(
        id=1,
        number=number,
        client_id=1,
        issue_date=date(2026, 9, 29),
        due_date=date(2026, 10, 29),
        payment_terms="Net 30",
        client_name_snapshot="Buyer SARL",
        client_address_snapshot="1 Rue <Haute> & Co",
        client_city_snapshot="Paris",
        client_postal_code_snapshot="75001",
        client_country_snapshot="FR",
        client_tax_id_snapshot="FR40303265045",
        lines=[
            InvoiceLine(
                id=1,
                invoice_id=1,
                description="Consulting",
                quantity=3,
                unit_price="33.333",
                tax_rate=19,
            ),
            InvoiceLine(
                id=2,
                invoice_id=1,
                description="Books",
                quantity=2,
                unit_price="10.5",
                tax_rate=7,
            ),
            InvoiceLine(
                id=3,
                invoice_id=1,
                description="Export item",
                quantity=1,
                unit_price="5",
                tax_rate=0,
            ),
        ],
    )
    data.update(changes)
    return Invoice(**data)


def _credit_note() -> Invoice:
    return _invoice("CN-1", type=InvoiceType.CREDIT_NOTE, reason="Returned goods")


class Schematron:
    """Compiled Schematron XSLTs; returns the text of every failed assertion."""

    def __init__(self, processor: PySaxonProcessor) -> None:
        self.processor = processor
        compiler: PyXslt30Processor = processor.new_xslt30_processor()
        self.sheets: dict[str, PyXsltExecutable] = {
            "EN16931": compiler.compile_stylesheet(stylesheet_file=str(EN16931_XSLT)),
            "Factur-X": compiler.compile_stylesheet(stylesheet_file=str(FACTURX_XSLT)),
        }

    def failures(self, xml: str) -> dict[str, list[str]]:
        result = {}
        for name, sheet in self.sheets.items():
            svrl = sheet.transform_to_string(xdm_node=self.processor.parse_xml(xml_text=xml))
            texts = re.findall(
                r"<svrl:failed-assert.*?<svrl:text>(.*?)</svrl:text>", svrl or "", re.S
            )
            result[name] = [" ".join(t.split()) for t in texts]
        return result


@pytest.fixture(scope="module")
def schematron() -> Iterator[Schematron]:
    with PySaxonProcessor(license=False) as processor:
        yield Schematron(processor)


@pytest.mark.parametrize(
    ("invoice", "context"),
    [
        (_invoice(), {}),
        (_credit_note(), {"original_invoice_number": "INV-1"}),
    ],
    ids=["invoice", "credit-note"],
)
def test_cii_passes_xsd_and_schematron(
    schematron: Schematron, invoice: Invoice, context: dict[str, str]
) -> None:
    xml = CIIService().generate_cii(invoice, SELLER, **context)

    assert facturx.xml_check_xsd(xml.encode(), flavor="factur-x", level="en16931")
    assert schematron.failures(xml) == {"EN16931": [], "Factur-X": []}


def test_schematron_catches_wrong_totals(schematron: Schematron) -> None:
    """The validators are live: a broken grand total is reported."""
    xml = CIIService().generate_cii(_invoice(), SELLER)
    broken = re.sub(r"<ram:GrandTotalAmount>[^<]+<", "<ram:GrandTotalAmount>1.00<", xml, count=1)

    failures = schematron.failures(broken)

    assert any("BR-CO-15" in text for text in failures["EN16931"])


def test_cii_document_content() -> None:
    xml = CIIService().generate_cii(_credit_note(), SELLER, original_invoice_number="INV-1")

    assert "<ram:TypeCode>381</ram:TypeCode>" in xml
    assert "<ram:ID>urn:cen.eu:en16931:2017</ram:ID>" in xml
    assert '<ram:ID schemeID="VA">DE123456789</ram:ID>' in xml
    assert '<ram:ID schemeID="VA">FR40303265045</ram:ID>' in xml
    assert "<ram:IssuerAssignedID>INV-1</ram:IssuerAssignedID>" in xml
    assert "1 Rue &lt;Haute&gt; &amp; Co" in xml
    assert "<ram:RateApplicablePercent>0</ram:RateApplicablePercent>" in xml
    assert "<ram:CategoryCode>Z</ram:CategoryCode>" in xml


def test_non_vat_tax_numbers(schematron: Schematron) -> None:
    """A seller tax number is a tax registration (FC); a buyer's is a legal ID."""
    seller = {**SELLER, "tax_id": "12/345/67890", "registration_number": "HRB 12345"}
    invoice = _invoice(client_tax_id_snapshot="US-123456789")

    xml = CIIService().generate_cii(invoice, seller)

    assert '<ram:ID schemeID="FC">12/345/67890</ram:ID>' in xml
    assert re.search(r"<ram:SpecifiedLegalOrganization>\s*<ram:ID>HRB 12345</ram:ID>", xml)
    assert re.search(r"<ram:SpecifiedLegalOrganization>\s*<ram:ID>US-123456789</ram:ID>", xml)
    assert 'schemeID="VA">US-123456789' not in xml
    assert schematron.failures(xml) == {"EN16931": [], "Factur-X": []}


def test_seller_tax_number_needs_registration_number() -> None:
    """BR-CO-26: without a VAT number the seller must have a legal registration number."""
    with pytest.raises(FacturXDataError, match="legal registration number"):
        CIIService().generate_cii(_invoice(), {**SELLER, "tax_id": "12/345/67890"})


def test_missing_data_is_reported_at_once() -> None:
    seller = {"name": "Seller GmbH"}
    invoice = _invoice(client_country_snapshot=None)

    with pytest.raises(FacturXDataError) as exc:
        CIIService().generate_cii(invoice, seller)

    assert exc.value.problems == [
        "seller country code is missing",
        "seller VAT or tax number (company['tax_id']) is missing",
        "buyer country code is missing",
    ]


def test_company_schema_country_key_is_accepted() -> None:
    """A dumped Company schema has `country`, not `country_code`."""
    seller = {k: v for k, v in SELLER.items() if k != "country_code"} | {"country": "de"}

    xml = CIIService().generate_cii(_invoice(), seller)

    assert "<ram:CountryID>DE</ram:CountryID>" in xml


def test_invalid_seller_country_is_reported() -> None:
    with pytest.raises(FacturXDataError, match="'Germany' is not an ISO 3166-1 alpha-2"):
        CIIService().generate_cii(_invoice(), {**SELLER, "country_code": "Germany"})


def test_delivery_date_defaults_to_issue_date() -> None:
    xml = CIIService().generate_cii(_invoice(), SELLER)
    later = CIIService().generate_cii(_invoice(), SELLER, delivery_date=date(2026, 9, 30))

    delivery = r"<ram:OccurrenceDateTime>\s*<udt:DateTimeString format=\"102\">(\d+)<"
    assert re.search(delivery, xml).group(1) == "20260929"  # type: ignore[union-attr]
    assert re.search(delivery, later).group(1) == "20260930"  # type: ignore[union-attr]


def test_facturx_pdf(tmp_path: Path) -> None:
    """PDF/A-3B with factur-x.xml (text/xml, Alternative) and the Factur-X XMP properties."""
    service = PDFService(output_dir=str(tmp_path))
    try:
        service._get_weasyprint_modules()
    except (WeasyPrintMissingError, PdfSystemLibrariesError) as e:
        pytest.skip(f"WeasyPrint unavailable: {e}")
    invoice = _invoice()

    pdf = service.generate_facturx_bytes(invoice, SELLER)

    filename, xml = facturx.get_xml_from_pdf(pdf, check_xsd=True)
    assert filename == "factur-x.xml"
    assert xml.decode() == CIIService().generate_cii(invoice, SELLER)

    path = tmp_path / "invoice.pdf"
    path.write_bytes(pdf)
    catalog: Any = PdfReader(path).trailer["/Root"]
    filespecs = {ref.get_object()["/F"]: ref.get_object() for ref in catalog["/AF"]}
    assert list(filespecs) == ["factur-x.xml"]
    filespec = filespecs["factur-x.xml"]
    assert filespec["/AFRelationship"] == "/Alternative"
    assert filespec["/EF"]["/F"].get_object()["/Subtype"] == "/text/xml"

    xmp = catalog["/Metadata"].get_object().get_data().decode()
    for key, value in {
        "pdfaid:part": "3",
        "pdfaid:conformance": "B",
        "fx:DocumentType": "INVOICE",
        "fx:DocumentFileName": "factur-x.xml",
        "fx:Version": "1.0",
        "fx:ConformanceLevel": "EN 16931",
    }.items():
        assert re.search(rf'{key}(="{value}"|>{value}<)', xmp), key
