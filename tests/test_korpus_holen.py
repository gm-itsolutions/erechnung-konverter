"""Sollwert-Ableitung aus eingebetteter CII/UBL-XML (Beispiele im Test erzeugt, nichts heruntergeladen)."""
from werkzeuge import korpus_holen as kh

CII = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
 xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
 <rsm:ExchangedDocument><ram:ID>RE-1</ram:ID><ram:TypeCode>381</ram:TypeCode>
  <ram:IssueDateTime><udt:DateTimeString format="102">20261102</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
 <rsm:SupplyChainTradeTransaction>
  <ram:IncludedSupplyChainTradeLineItem>
   <ram:SpecifiedTradeProduct><ram:Name>Kabel</ram:Name></ram:SpecifiedTradeProduct>
   <ram:SpecifiedLineTradeAgreement><ram:NetPriceProductTradePrice><ram:ChargeAmount>5.00</ram:ChargeAmount></ram:NetPriceProductTradePrice></ram:SpecifiedLineTradeAgreement>
   <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="C62">2</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
   <ram:SpecifiedLineTradeSettlement><ram:ApplicableTradeTax><ram:RateApplicablePercent>19</ram:RateApplicablePercent></ram:ApplicableTradeTax>
    <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>10.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation>
   </ram:SpecifiedLineTradeSettlement>
  </ram:IncludedSupplyChainTradeLineItem>
  <ram:ApplicableHeaderTradeAgreement><ram:SellerTradeParty><ram:Name>Verkäufer AG</ram:Name></ram:SellerTradeParty>
   <ram:BuyerTradeParty><ram:Name>Käufer GmbH</ram:Name></ram:BuyerTradeParty></ram:ApplicableHeaderTradeAgreement>
  <ram:ApplicableHeaderTradeSettlement>
   <ram:ApplicableTradeTax><ram:CalculatedAmount>1.90</ram:CalculatedAmount><ram:RateApplicablePercent>19</ram:RateApplicablePercent></ram:ApplicableTradeTax>
   <ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:LineTotalAmount>10.00</ram:LineTotalAmount>
    <ram:TaxBasisTotalAmount>10.00</ram:TaxBasisTotalAmount><ram:TaxTotalAmount>1.90</ram:TaxTotalAmount>
    <ram:GrandTotalAmount>11.90</ram:GrandTotalAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation>
  </ram:ApplicableHeaderTradeSettlement>
 </rsm:SupplyChainTradeTransaction></rsm:CrossIndustryInvoice>"""

UBL = """<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
 <cbc:CustomizationID>x</cbc:CustomizationID><cbc:ID>U-7</cbc:ID><cbc:IssueDate>2026-11-03</cbc:IssueDate>
 <cac:AccountingSupplierParty><cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Lieferer</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
 <cac:AccountingCustomerParty><cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Kunde</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>
 <cac:TaxTotal><cbc:TaxAmount>0.70</cbc:TaxAmount><cac:TaxSubtotal><cbc:TaxableAmount>10.00</cbc:TaxableAmount><cbc:TaxAmount>0.70</cbc:TaxAmount>
  <cac:TaxCategory><cbc:Percent>7</cbc:Percent></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
 <cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount>10.00</cbc:TaxExclusiveAmount><cbc:TaxInclusiveAmount>10.70</cbc:TaxInclusiveAmount></cac:LegalMonetaryTotal>
 <cac:InvoiceLine><cbc:ID>1</cbc:ID><cbc:InvoicedQuantity unitCode="H87">4</cbc:InvoicedQuantity><cbc:LineExtensionAmount>10.00</cbc:LineExtensionAmount>
  <cac:Item><cbc:Name>Buch</cbc:Name><cac:ClassifiedTaxCategory><cbc:Percent>7</cbc:Percent></cac:ClassifiedTaxCategory></cac:Item>
  <cac:Price><cbc:PriceAmount>2.50</cbc:PriceAmount></cac:Price></cac:InvoiceLine></Invoice>"""


def test_soll_aus_cii():
    s = kh.soll_aus_xml(CII.encode())
    assert (s["nummer"], s["datum"], s["netto"], s["brutto"], s["art"]) == ("RE-1", "2026-11-02", "10.00", "11.90", "gutschrift")
    assert s["steuern"] == {"19": "1.90"} and s["kaeufer"] == {"name": "Käufer GmbH"} and s["verkaeufer"] == "Verkäufer AG"
    assert s["positionen"] == [{"bezeichnung": "Kabel", "menge": "2", "einheit": "C62", "einzelpreis": "5.00",
                                "netto": "10.00", "satz": "19"}]


def test_soll_aus_ubl():
    s = kh.soll_aus_xml(UBL.encode())
    assert (s["nummer"], s["datum"], s["netto"], s["brutto"], s["steuern"]) == ("U-7", "2026-11-03", "10.00", "10.70", {"7": "0.70"})
    assert s["kaeufer"]["name"] == "Kunde"
    assert s["positionen"] == [{"bezeichnung": "Buch", "menge": "4", "einheit": "H87", "einzelpreis": "2.50",
                                "netto": "10.00", "satz": "7"}]
