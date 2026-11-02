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
    for n in r.nachlaesse:                                   # BG-20/BG-21, Reihenfolge laut XSD wie Lexware
        ac = _e(abr, "ram:SpecifiedTradeAllowanceCharge")
        _e(_e(ac, "ram:ChargeIndicator"), "udt:Indicator", "true" if n.zuschlag else "false")
        _e(ac, "ram:ActualAmount", _betrag(n.betrag))
        _e(ac, "ram:Reason", n.grund or ("Zuschlag" if n.zuschlag else "Nachlass"))   # BR-33/BR-38
        st = _e(ac, "ram:CategoryTradeTax")
        _e(st, "ram:TypeCode", "VAT")
        _e(st, "ram:CategoryCode", "S")
        # ohne Satz nur bei genau einem Steuersatz (summenabgleich prüft das)
        _e(st, "ram:RateApplicablePercent", _zahl(n.ust_satz if n.ust_satz is not None else next(iter(steuern))))
    bed = _e(abr, "ram:SpecifiedTradePaymentTerms")
    if r.faellig:
        _datum(bed, "ram:DueDateDateTime", r.faellig)
    else:
        _e(bed, "ram:Description", "Zahlungsbedingungen siehe Rechnung")
    ust = sum((s for _, s in steuern.values()), Decimal(0))
    summen = _e(abr, "ram:SpecifiedTradeSettlementHeaderMonetarySummation")
    _e(summen, "ram:LineTotalAmount", _betrag(sum((p.netto for p in r.positionen), Decimal(0))))
    if r.nachlaesse:
        for zuschlag, tag in ((True, "ram:ChargeTotalAmount"), (False, "ram:AllowanceTotalAmount")):
            _e(summen, tag, _betrag(sum((n.betrag for n in r.nachlaesse if n.zuschlag == zuschlag), Decimal(0))))
    _e(summen, "ram:TaxBasisTotalAmount", _betrag(r.summe_netto))
    _e(summen, "ram:TaxTotalAmount", _betrag(ust), currencyID=r.waehrung)
    _e(summen, "ram:GrandTotalAmount", _betrag(r.summe_brutto))
    _e(summen, "ram:DuePayableAmount", _betrag(r.summe_brutto))
    return etree.tostring(wurzel, xml_declaration=True, encoding="UTF-8", pretty_print=True)

def bette_ein(pdf: bytes, xml: bytes) -> bytes:
    """ZUGFeRD/Factur-X EN16931; prüft die XML gegen das XSD (wirft bei Fehler)."""
    return generate_from_binary(pdf, xml, flavor="factur-x", level="en16931", check_xsd=True, lang="de-DE")
