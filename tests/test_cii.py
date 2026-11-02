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
