# Task 03: CII-XML (EN16931) und Einbetten mit factur-x

Spezifikation: Abschnitt 4.1, 8. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/cii.py`, `tests/test_cii.py`

**Interfaces:**
- Consumes: `erechnung.modell` (`Rechnung`, `Partei`, `runde`, `summenabgleich`), `tests/hilfen.py` (`beispiel_rechnung`, `pdf_aus_text`) aus Task 01.
- Produces: `erzeuge_cii(r: Rechnung, steuern: dict[Decimal, tuple[Decimal, Decimal]]) -> bytes` (UTF-8, mit XML-Deklaration, XSD-gültig für factur-x EN16931); `bette_ein(pdf: bytes, xml: bytes) -> bytes` (ZUGFeRD-PDF). `steuern` ist das Ergebnis von `summenabgleich(r)`.

Elementreihenfolge folgt dem CII-XSD (D16B), sonst schlägt die XSD-Prüfung fehl. Nur Kategorie `S`.

- [ ] **Step 1: Failing tests** – `tests/test_cii.py`

```python
from decimal import Decimal as D
import pytest
from facturx import get_xml_from_pdf, xml_check_xsd
from lxml import etree
from erechnung.cii import bette_ein, erzeuge_cii
from erechnung.modell import summenabgleich
from erechnung.betraege import betraege
from hilfen import beispiel_rechnung, pdf_aus_text

def xml_von(r):
    return erzeuge_cii(r, summenabgleich(r))

def test_xsd_gueltig():
    assert xml_check_xsd(xml_von(beispiel_rechnung()), flavor="factur-x", level="en16931")

def test_betraege_und_kopf():
    xml = xml_von(beispiel_rechnung())
    assert betraege(xml) == {"nummer": "RE9001", "netto": D("200.00"), "steuer": D("38.00"),
                             "brutto": D("238.00"), "positionen": [D("190.00"), D("10.00")]}
    t = xml.decode()
    for teil in ["urn:cen.eu:en16931:2017", "<ram:TypeCode>380</ram:TypeCode>", "20261015",
                 'schemeID="VA">DE123456789<', "DE02120300000000202051", 'unitCode="HUR"', "20261029"]:
        assert teil in t, teil

def test_zwei_steuersaetze():
    r = beispiel_rechnung()
    r.positionen[1].ust_satz = D("7")
    r.summe_ust, r.summe_brutto, r.steuern = D("36.80"), D("236.80"), {}
    xml = xml_von(r)
    assert xml_check_xsd(xml, flavor="factur-x", level="en16931")
    baum = etree.fromstring(xml)
    saetze = baum.xpath("//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax/ram:RateApplicablePercent/text()",
                        namespaces={"ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"})
    assert sorted(saetze) == ["19", "7"]

def test_ohne_faelligkeit_zahlungsbedingung():
    r = beispiel_rechnung()
    r.faellig = None
    xml = xml_von(r)
    assert xml_check_xsd(xml, flavor="factur-x", level="en16931")
    assert b"<ram:Description>" in xml  # BR-CO-25: Fälligkeit oder Zahlungsbedingung

def test_einbetten():
    xml = xml_von(beispiel_rechnung())
    pdf = bette_ein(pdf_aus_text(["Rechnung RE9001"]), xml)
    name, eingebettet = get_xml_from_pdf(pdf, check_xsd=False)
    assert name == "factur-x.xml"
    assert eingebettet == xml
```

- [ ] **Step 2: Tests scheitern** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_cii.py -q` → `ModuleNotFoundError: erechnung.cii`

- [ ] **Step 3: `erechnung/cii.py`**

```python
"""CII-XML nach EN16931 (Factur-X/ZUGFeRD Profil EN16931) aus dem Rechnungsmodell."""
from datetime import date
from decimal import Decimal
from lxml import etree
from facturx import generate_from_binary
from .modell import Partei, Rechnung, runde

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"
QDT = "urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
NSMAP = {"rsm": RSM, "ram": RAM, "udt": UDT, "qdt": QDT}

def _e(eltern, tag: str, text=None, **attr):
    ns, name = tag.split(":")
    el = etree.SubElement(eltern, f"{{{NSMAP[ns]}}}{name}", **attr)
    if text is not None:
        el.text = str(text)
    return el

def _betrag(x: Decimal) -> str:
    return str(runde(x))

def _zahl(x: Decimal) -> str:
    return format(x.normalize(), "f")

def _datum(eltern, tag: str, d: date):
    _e(_e(eltern, tag), "udt:DateTimeString", d.strftime("%Y%m%d"), format="102")

def _partei(eltern, tag: str, p: Partei, verkaeufer: bool):
    el = _e(eltern, tag)
    _e(el, "ram:Name", p.name)
    adr = _e(el, "ram:PostalTradeAddress")
    if p.plz:
        _e(adr, "ram:PostcodeCode", p.plz)
    if p.strasse:
        _e(adr, "ram:LineOne", p.strasse)
    if p.ort:
        _e(adr, "ram:CityName", p.ort)
    _e(adr, "ram:CountryID", p.land or "DE")
    if p.email:
        _e(_e(el, "ram:URIUniversalCommunication"), "ram:URIID", p.email, schemeID="EM")
    if p.steuernummer and verkaeufer:
        _e(_e(el, "ram:SpecifiedTaxRegistration"), "ram:ID", p.steuernummer, schemeID="FC")
    if p.ust_id:
        _e(_e(el, "ram:SpecifiedTaxRegistration"), "ram:ID", p.ust_id, schemeID="VA")

def erzeuge_cii(r: Rechnung, steuern: dict[Decimal, tuple[Decimal, Decimal]]) -> bytes:
    wurzel = etree.Element(f"{{{RSM}}}CrossIndustryInvoice", nsmap=NSMAP)
    kontext = _e(wurzel, "rsm:ExchangedDocumentContext")
    _e(_e(kontext, "ram:GuidelineSpecifiedDocumentContextParameter"), "ram:ID", "urn:cen.eu:en16931:2017")
    dok = _e(wurzel, "rsm:ExchangedDocument")
    _e(dok, "ram:ID", r.nummer)
    _e(dok, "ram:TypeCode", "380")
    _datum(dok, "ram:IssueDateTime", r.datum)

    tx = _e(wurzel, "rsm:SupplyChainTradeTransaction")
    for i, p in enumerate(r.positionen, 1):
        pos = _e(tx, "ram:IncludedSupplyChainTradeLineItem")
        _e(_e(pos, "ram:AssociatedDocumentLineDocument"), "ram:LineID", str(i))
        _e(_e(pos, "ram:SpecifiedTradeProduct"), "ram:Name", p.bezeichnung)
        _e(_e(_e(pos, "ram:SpecifiedLineTradeAgreement"), "ram:NetPriceProductTradePrice"), "ram:ChargeAmount", _zahl(p.einzelpreis))
        _e(_e(pos, "ram:SpecifiedLineTradeDelivery"), "ram:BilledQuantity", _zahl(p.menge), unitCode=p.einheit or "C62")
        abr = _e(pos, "ram:SpecifiedLineTradeSettlement")
        st = _e(abr, "ram:ApplicableTradeTax")
        _e(st, "ram:TypeCode", "VAT")
        _e(st, "ram:CategoryCode", "S")
        _e(st, "ram:RateApplicablePercent", _zahl(p.ust_satz))
        _e(_e(abr, "ram:SpecifiedTradeSettlementLineMonetarySummation"), "ram:LineTotalAmount", _betrag(p.netto))

    vereinbarung = _e(tx, "ram:ApplicableHeaderTradeAgreement")
    _partei(vereinbarung, "ram:SellerTradeParty", r.verkaeufer, True)
    _partei(vereinbarung, "ram:BuyerTradeParty", r.kaeufer, False)
    lieferung = _e(tx, "ram:ApplicableHeaderTradeDelivery")
    if r.leistungsdatum:
        _datum(_e(lieferung, "ram:ActualDeliverySupplyChainEvent"), "ram:OccurrenceDateTime", r.leistungsdatum)

    abr = _e(tx, "ram:ApplicableHeaderTradeSettlement")
    _e(abr, "ram:PaymentReference", r.nummer)
    _e(abr, "ram:InvoiceCurrencyCode", r.waehrung)
    if r.verkaeufer.iban:
        zm = _e(abr, "ram:SpecifiedTradeSettlementPaymentMeans")
        _e(zm, "ram:TypeCode", "58")
        _e(_e(zm, "ram:PayeePartyCreditorFinancialAccount"), "ram:IBANID", r.verkaeufer.iban.replace(" ", ""))
        if r.verkaeufer.bic:
            _e(_e(zm, "ram:PayeeSpecifiedCreditorFinancialInstitution"), "ram:BICID", r.verkaeufer.bic)
    for satz, (basis, steuer) in sorted(steuern.items(), reverse=True):
        st = _e(abr, "ram:ApplicableTradeTax")
        _e(st, "ram:CalculatedAmount", _betrag(steuer))
        _e(st, "ram:TypeCode", "VAT")
        _e(st, "ram:BasisAmount", _betrag(basis))
        _e(st, "ram:CategoryCode", "S")
        _e(st, "ram:RateApplicablePercent", _zahl(satz))
    bed = _e(abr, "ram:SpecifiedTradePaymentTerms")
    if r.faellig:
        _datum(bed, "ram:DueDateDateTime", r.faellig)
    else:
        _e(bed, "ram:Description", "Zahlungsbedingungen siehe Rechnung")
    ust = sum((s for _, s in steuern.values()), Decimal(0))
    summen = _e(abr, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _e(summen, "ram:LineTotalAmount", _betrag(r.summe_netto))
    _e(summen, "ram:TaxBasisTotalAmount", _betrag(r.summe_netto))
    _e(summen, "ram:TaxTotalAmount", _betrag(ust), currencyID=r.waehrung)
    _e(summen, "ram:GrandTotalAmount", _betrag(r.summe_brutto))
    _e(summen, "ram:DuePayableAmount", _betrag(r.summe_brutto))
    return etree.tostring(wurzel, xml_declaration=True, encoding="UTF-8", pretty_print=True)

def bette_ein(pdf: bytes, xml: bytes) -> bytes:
    """ZUGFeRD/Factur-X EN16931; prüft die XML gegen das XSD (wirft bei Fehler)."""
    return generate_from_binary(pdf, xml, flavor="factur-x", level="en16931", check_xsd=True, lang="de-DE")
```

Hinweis: In `PayeeSpecifiedCreditorFinancialInstitution` steht im XSD die Reihenfolge nach `PayeePartyCreditorFinancialAccount` – passt. Liefert die XSD-Prüfung einen Reihenfolgefehler, die Meldung lesen (Elementname) und die Reihenfolge im XSD nachsehen: `python -c "import facturx, os; print(os.path.dirname(facturx.__file__))"`, darin `xsd/factur-x/en16931/`.

- [ ] **Step 4: Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q` → alle PASS. Gibt `generate_from_binary` eine andere Signatur zurück (factur-x-Version), Parameter nach `help(facturx.generate_from_binary)` anpassen, Interface unverändert lassen.

- [ ] **Step 5: Commit und Push**

```bash
git -C /root/erechnung-konverter add erechnung/cii.py tests/test_cii.py
git -C /root/erechnung-konverter commit -m "CII-XML EN16931 und Einbetten mit factur-x" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
