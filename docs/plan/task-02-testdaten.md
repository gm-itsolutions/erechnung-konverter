# Task 02: Testhilfen, Lexware-Testdaten, Beträge aus E-Rechnungs-XML

Spezifikation: Abschnitt 4.1 (Testdaten) und 12. Global Constraints in `index.md`.

**Ziel:** PDFs und Lexware-E-Rechnungs-XML der Rechnungen **RE0146, RE0148, RE0149** liegen außerhalb des Repos in `/root/erechnung-testdaten/` (Ordner 0700), dazu der extrahierte Text. Ein kleines Modul liest Kernbeträge aus CII- **und** UBL-XML, damit Task 08 vergleichen kann.

**Warum außerhalb:** Die Rechnungen enthalten Namen und Anschriften von Marvins Kunden (personenbezogene Daten, Global Constraint). Im Repo liegen nur synthetische Daten (Task 04).

**Files:**
- Create: `tests/hilfen.py`, `tests/test_hilfen.py`, `werkzeuge/testdaten_holen.py`, `erechnung/betraege.py`, `tests/test_betraege.py`
- Erzeugt (nicht im Repo): `/root/erechnung-testdaten/RE01xx.pdf`, `RE01xx.lexware.xml`, `RE01xx.txt`, `RE01xx.layout.txt`

**Interfaces:**
- Produces: `tests/hilfen.py`: `VERKAEUFER`, `beispiel_rechnung() -> Rechnung`, `pdf_aus_text(zeilen: list[str]) -> bytes`.
- Produces: `erechnung.betraege.betraege(xml: bytes) -> dict` mit Schlüsseln `nummer: str`, `netto: Decimal`, `steuer: Decimal`, `brutto: Decimal`, `positionen: list[Decimal]` (Netto je Position, in Reihenfolge).

- [ ] **Step 0: Testhilfen für spätere Tasks** – `tests/hilfen.py` (Tasks 03–05 importieren sie als `from hilfen import …`; `pytest.ini` aus Task 01 hat `pythonpath = . tests`). Braucht `erechnung/modell.py` aus Task 01 – läuft Task 01 noch, diesen Schritt zuletzt erledigen.

```python
"""Gemeinsame Testhilfen: Beispielrechnung und PDF aus Textzeilen (reportlab, nur Test)."""
from datetime import date
from decimal import Decimal as D
from io import BytesIO
from erechnung.modell import Partei, Position, Rechnung

VERKAEUFER = Partei("GM IT Solutions", "Musterstraße 1", "16928", "Pritzwalk", "DE",
                    ust_id="DE123456789", email="rechnung@example.org",
                    iban="DE02120300000000202051", bic="BYLADEM1001")

def beispiel_rechnung() -> Rechnung:
    return Rechnung(
        nummer="RE9001", datum=date(2026, 10, 15), leistungsdatum=date(2026, 10, 14), faellig=date(2026, 10, 29),
        verkaeufer=VERKAEUFER, kaeufer=Partei("Beispiel Handel GmbH", "Hauptstraße 5", "19348", "Perleberg"),
        positionen=[Position("1", "IT-Service vor Ort", D("2"), "HUR", D("95.00"), D("190.00"), D("19")),
                    Position("2", "Anfahrt", D("1"), "C62", D("10.00"), D("10.00"), D("19"))],
        summe_netto=D("200.00"), summe_ust=D("38.00"), summe_brutto=D("238.00"), steuern={D("19"): D("38.00")})

def pdf_aus_text(zeilen: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    y = 800
    for z in zeilen:
        if y < 50:
            c.showPage()
            y = 800
        c.drawString(50, y, z)
        y -= 14
    c.save()
    return puffer.getvalue()
```

Einen Mini-Test ergänzen (`tests/test_hilfen.py`): `summenabgleich(beispiel_rechnung())` liefert `{D("19"): (D("200.00"), D("38.00"))}`.

- [ ] **Step 1: Failing test** – `tests/test_betraege.py`

```python
from decimal import Decimal as D
from erechnung.betraege import betraege

CII = b"""<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
 xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
 <rsm:ExchangedDocument><ram:ID>RE0001</ram:ID></rsm:ExchangedDocument>
 <rsm:SupplyChainTradeTransaction>
  <ram:IncludedSupplyChainTradeLineItem><ram:SpecifiedLineTradeSettlement><ram:SpecifiedTradeSettlementLineMonetarySummation>
   <ram:LineTotalAmount>100.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation></ram:SpecifiedLineTradeSettlement></ram:IncludedSupplyChainTradeLineItem>
  <ram:ApplicableHeaderTradeSettlement><ram:SpecifiedTradeSettlementHeaderMonetarySummation>
   <ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount><ram:TaxTotalAmount currencyID="EUR">19.00</ram:TaxTotalAmount>
   <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation></ram:ApplicableHeaderTradeSettlement>
 </rsm:SupplyChainTradeTransaction></rsm:CrossIndustryInvoice>"""

UBL = b"""<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:ID>RE0001</cbc:ID>
 <cac:TaxTotal><cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount></cac:TaxTotal>
 <cac:LegalMonetaryTotal><cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount>
  <cbc:TaxInclusiveAmount currencyID="EUR">119.00</cbc:TaxInclusiveAmount></cac:LegalMonetaryTotal>
 <cac:InvoiceLine><cbc:LineExtensionAmount currencyID="EUR">100.00</cbc:LineExtensionAmount></cac:InvoiceLine>
</Invoice>"""

ERWARTET = {"nummer": "RE0001", "netto": D("100.00"), "steuer": D("19.00"), "brutto": D("119.00"), "positionen": [D("100.00")]}

def test_cii():
    assert betraege(CII) == ERWARTET

def test_ubl():
    assert betraege(UBL) == ERWARTET
```

- [ ] **Step 2: Test scheitert** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_betraege.py -q` → `ModuleNotFoundError`

- [ ] **Step 3: `erechnung/betraege.py`**

```python
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
                "positionen": [Decimal(t) for t in x("//ram:IncludedSupplyChainTradeLineItem//ram:LineTotalAmount/text()")]}
    return {"nummer": x("string(cbc:ID)"),
            "netto": Decimal(x("string(cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount)")),
            "steuer": Decimal(x("string(cac:TaxTotal[1]/cbc:TaxAmount)")),
            "brutto": Decimal(x("string(cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount)")),
            "positionen": [Decimal(t) for t in x("cac:InvoiceLine/cbc:LineExtensionAmount/text()")]}
```

- [ ] **Step 4: Tests grün** – gleicher Befehl, PASS.

- [ ] **Step 5: `werkzeuge/testdaten_holen.py`** (nur gm-claude, Standardbibliothek + factur-x/pdfplumber aus dem venv)

Lexware-API (ai-os `40-wissen/lexware-office-public-api.md`): Basis `https://api.lexware.io`, `Authorization: Bearer <key>`, **höchstens 2 Requests/s**. Key aus `/root/.config/gm-it-os/lexware.env` (Zeile `LEXWARE_API_KEY=…`; tatsächlichen Variablennamen mit `grep -o '^[A-Z_]*=' /root/.config/gm-it-os/lexware.env` nachsehen, Wert nie ausgeben).

```python
"""Holt Lexware-Rechnungen (PDF + E-Rechnungs-XML) nach /root/erechnung-testdaten. Nur gm-claude.
Aufruf: /root/.venvs/erechnung/bin/python werkzeuge/testdaten_holen.py RE0146 RE0148 RE0149"""
import json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ZIEL = Path("/root/erechnung-testdaten")
BASIS = "https://api.lexware.io/v1"

def schluessel() -> str:
    for z in Path("/root/.config/gm-it-os/lexware.env").read_text().splitlines():
        name, _, wert = z.partition("=")
        if name.strip().endswith("KEY") and wert.strip():
            return wert.strip().strip('"')
    sys.exit("kein API-Key in lexware.env")

def hole(pfad: str, accept: str = "application/json") -> bytes:
    time.sleep(0.6)  # 2 Requests/s
    req = urllib.request.Request(BASIS + pfad, headers={"Authorization": f"Bearer {KEY}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def finde_id(nummer: str) -> str:
    seite = 0
    while True:
        d = json.loads(hole(f"/voucherlist?voucherType=invoice&voucherStatus=any&size=250&page={seite}"))
        for v in d["content"]:
            if v.get("voucherNumber") == nummer:
                return v["id"]
        if d.get("last", True):
            sys.exit(f"{nummer} nicht gefunden")
        seite += 1

def pdf_und_xml(rid: str) -> tuple[bytes, bytes | None]:
    try:
        pdf = hole(f"/invoices/{rid}/file", "application/pdf")
    except urllib.error.HTTPError:
        doc = json.loads(hole(f"/invoices/{rid}/document"))
        pdf = hole(f"/files/{doc['documentFileId']}", "application/pdf")
    try:
        return pdf, hole(f"/invoices/{rid}/file", "application/xml")
    except urllib.error.HTTPError:
        from facturx import get_xml_from_pdf  # Lexware-PDF mit eingebetteter XML?
        _, xml = get_xml_from_pdf(pdf, check_xsd=False)
        return pdf, xml or None

if __name__ == "__main__":
    KEY = schluessel()
    ZIEL.mkdir(mode=0o700, exist_ok=True)
    os.chmod(ZIEL, 0o700)
    import pdfplumber
    for nummer in sys.argv[1:]:
        pdf, xml = pdf_und_xml(finde_id(nummer))
        (ZIEL / f"{nummer}.pdf").write_bytes(pdf)
        if xml:
            (ZIEL / f"{nummer}.lexware.xml").write_bytes(xml)
        with pdfplumber.open(ZIEL / f"{nummer}.pdf") as d:
            (ZIEL / f"{nummer}.txt").write_text("\n".join(s.extract_text() or "" for s in d.pages))
            (ZIEL / f"{nummer}.layout.txt").write_text("\n".join(s.extract_text(layout=True) or "" for s in d.pages))
        print(nummer, "PDF", len(pdf), "XML", len(xml or b""))
```

`/invoices/{id}/file` mit `Accept: application/xml` ist nicht sicher belegt **[n. o. b.]**; der Rückfall liest die eingebettete XML aus dem PDF. Liefert keiner der Wege eine XML: Marvin bitten, die drei XML in Lexware herunterzuladen und nach `/root/erechnung-testdaten/` zu legen (Rückmeldung als Blocker, Task 04 kann trotzdem starten, Task 08 nicht).

- [ ] **Step 6: Ausführen und prüfen**

Run: `/root/.venvs/erechnung/bin/python /root/erechnung-konverter/werkzeuge/testdaten_holen.py RE0146 RE0148 RE0149`
Dann: `ls -la /root/erechnung-testdaten` (Rechte `drwx------`), und für jede XML:
`/root/.venvs/erechnung/bin/python -c "import sys; from erechnung.betraege import betraege; print(betraege(open(sys.argv[1],'rb').read()))" /root/erechnung-testdaten/RE0146.lexware.xml` (cwd `/root/erechnung-konverter`).
Expected: Netto + Steuer = Brutto, Anzahl Positionen plausibel. Beträge in der Rückmeldung nennen (netto), **keine** Kundennamen.

- [ ] **Step 7: Commit und Push** (nur Code, keine Testdaten – `git -C /root/erechnung-konverter status` prüfen)

```bash
git -C /root/erechnung-konverter add tests/hilfen.py tests/test_hilfen.py werkzeuge/testdaten_holen.py erechnung/betraege.py tests/test_betraege.py
git -C /root/erechnung-konverter commit -m "Testdaten-Abruf aus Lexware und Betragsleser für CII/UBL" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter push origin main
```
