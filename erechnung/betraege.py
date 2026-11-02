"""Kernbeträge aus einer E-Rechnungs-XML (CII oder UBL) – für Abgleich und Tests."""
from decimal import Decimal
from lxml import etree

NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}

def betraege(xml: bytes) -> dict:
    baum = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    x = lambda pfad: baum.xpath(pfad, namespaces=NS)
    if baum.tag == f"{{{NS['rsm']}}}CrossIndustryInvoice":
        s = "rsm:SupplyChainTradeTransaction/ram:ApplicableHeaderTradeSettlement/ram:SpecifiedTradeSettlementHeaderMonetarySummation/"
        return {"nummer": x("string(rsm:ExchangedDocument/ram:ID)"),
                "netto": Decimal(x(f"string({s}ram:TaxBasisTotalAmount)")),
                "steuer": Decimal(x(f"string({s}ram:TaxTotalAmount[1])")),
                "brutto": Decimal(x(f"string({s}ram:GrandTotalAmount)")),
                "nachlass": Decimal(x(f"string({s}ram:AllowanceTotalAmount)") or 0),
                "positionen": [Decimal(t) for t in x("//ram:IncludedSupplyChainTradeLineItem//ram:LineTotalAmount/text()")]}
    return {"nummer": x("string(cbc:ID)"),
            "netto": Decimal(x("string(cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount)")),
            "steuer": Decimal(x("string(cac:TaxTotal[1]/cbc:TaxAmount)")),
            "brutto": Decimal(x("string(cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount)")),
            "nachlass": Decimal(x("string(cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount)") or 0),
            "positionen": [Decimal(t) for t in x("cac:InvoiceLine/cbc:LineExtensionAmount/text()")]}
