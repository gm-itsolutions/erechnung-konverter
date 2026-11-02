# Task 01: Gerüst, Modell, Summenabgleich

Spezifikation: Abschnitt 4 und 8. Global Constraints in `index.md`.

**Files:**
- Create: `requirements-dev.txt`, `pytest.ini`, `.gitignore`, `erechnung/__init__.py`, `erechnung/__main__.py`, `erechnung/modell.py`, `tests/test_modell.py`

**Interfaces:**
- Produces: `erechnung.__version__: str`; `erechnung.modell`: `ZWEI`, `runde`, `betrag`, `datum`, `Partei`, `Position`, `Rechnung`, `SummenFehler`, `summenabgleich` (Signaturen in `index.md`). `python -m erechnung --version` gibt die Version aus (Task 05 erweitert die CLI).

- [ ] **Step 1: Umgebung und Grunddateien**

`requirements-dev.txt` (Versionen = Windows-Paket, Task 06 übernimmt sie):
```
pdfplumber==0.11.10
factur-x==7.9
lxml==6.1.3
pyyaml==6.0.3
pytest==8.4.2
reportlab==4.4.4
```
Falls eine Version nicht installierbar ist: nächste verfügbare nehmen und in Task 06 dieselbe verwenden.

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = . tests
markers =
    echt: braucht echte Lexware-Daten (ERECHNUNG_TESTDATEN)
```
`.gitignore`: `__pycache__/`, `*.pyc`, `build/`, `dist/`, `.pytest_cache/`

`erechnung/__init__.py`:
```python
"""PDF-Rechnung → ZUGFeRD-E-Rechnung (EN16931)."""
__version__ = "0.0.0-dev"  # setzt release/bauen.sh aus dem Tag
```

`erechnung/__main__.py` (vorläufig, Task 05 ersetzt):
```python
import sys
from . import __version__
if __name__ == "__main__":
    if sys.argv[1:] == ["--version"]:
        print(__version__)
        sys.exit(0)
    sys.exit("Aufruf: python -m erechnung --version")
```

Venv: `python3 -m venv /root/.venvs/erechnung`, dann `/root/.venvs/erechnung/bin/pip install -r /root/erechnung-konverter/requirements-dev.txt`.

- [ ] **Step 2: Failing tests schreiben** – `tests/test_modell.py`

```python
from datetime import date
from decimal import Decimal as D
import pytest
from erechnung.modell import Partei, Position, Rechnung, SummenFehler, betrag, datum, runde, summenabgleich
def pos(nr, menge, preis, netto, satz="19"):
    return Position(str(nr), f"Leistung {nr}", D(menge), "HUR", D(preis), D(netto), D(satz))
def rechnung(positionen, netto, ust, brutto, steuern=None):
    return Rechnung(nummer="RE0001", datum=date(2026, 10, 15),
                    verkaeufer=Partei("GM IT Solutions"), kaeufer=Partei("Muster GmbH"),
                    positionen=positionen, summe_netto=D(netto), summe_brutto=D(brutto),
                    summe_ust=None if ust is None else D(ust), steuern=steuern or {})
@pytest.mark.parametrize("text,erwartet", [
    ("1.234,56", "1234.56"), ("1.234,56 €", "1234.56"), ("€ 12,00", "12.00"), ("-12,50", "-12.50"),
    ("0,5", "0.5"), ("1234", "1234"), ("1 234,00", "1234.00"),
])
def test_betrag(text, erwartet):
    assert betrag(text) == D(erwartet)
def test_betrag_unsinn():
    with pytest.raises(ValueError):
        betrag("abc")
def test_datum():
    assert datum("05.11.2026") == date(2026, 11, 5)
def test_runde_kaufmaennisch():
    assert runde(D("0.125")) == D("0.13")
    assert runde(D("2.675")) == D("2.68")
def test_abgleich_ok_ein_satz():
    r = rechnung([pos(1, "2", "95.00", "190.00"), pos(2, "1", "10.00", "10.00")],
                 "200.00", "38.00", "238.00", {D("19"): D("38.00")})
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
def test_abgleich_gemischte_saetze():
    r = rechnung([pos(1, "1", "100.00", "100.00"), pos(2, "1", "50.00", "50.00", "7")],
                 "150.00", "22.50", "172.50")
    assert summenabgleich(r) == {D("19"): (D("100.00"), D("19.00")), D("7"): (D("50.00"), D("3.50"))}
def test_abgleich_gedruckte_steuer_mit_cent_toleranz():
    r = rechnung([pos(1, "1", "10.05", "10.05")], "10.05", "1.92", "11.97", {D("19"): D("1.92")})
    assert summenabgleich(r) == {D("19"): (D("10.05"), D("1.92"))}  # berechnet 1.91, gedruckt gilt
@pytest.mark.parametrize("positionen,netto,ust,brutto,steuern,teil", [
    ([], "0", "0", "0", None, "keine Positionen"),
    ([pos(1, "2", "10.00", "25.00")], "25.00", "4.75", "29.75", None, "Position 1"),
    ([pos(1, "1", "100.00", "100.00")], "110.00", "20.90", "130.90", None, "Netto"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "19.00", "120.00", None, "Brutto"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "18.00", "118.00", None, "Umsatzsteuer"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "19.00", "119.00", {D("19"): D("17.00")}, "19 %"),
    ([pos(1, "1", "100.00", "100.00", "0")], "100.00", "0.00", "100.00", None, "0 %"),
])
def test_abgleich_fehler(positionen, netto, ust, brutto, steuern, teil):
    with pytest.raises(SummenFehler, match=teil):
        summenabgleich(rechnung(positionen, netto, ust, brutto, steuern))
```

- [ ] **Step 3: Test laufen lassen, muss scheitern**

Run: `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_modell.py -q` (cwd egal, `pytest.ini` liegt im Repo; ggf. `--rootdir /root/erechnung-konverter`)
Expected: FAIL, `ModuleNotFoundError: erechnung.modell`

- [ ] **Step 4: `erechnung/modell.py` implementieren**

```python
"""Rechnungsmodell (Decimal) und Pflicht-Summenabgleich (Spezifikation Abschnitt 8)."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
ZWEI = Decimal("0.01")
CENT = Decimal("0.01")
def runde(x: Decimal) -> Decimal:
    return x.quantize(ZWEI, rounding=ROUND_HALF_UP)
def betrag(text: str) -> Decimal:
    """Deutscher Betrag: Tausenderpunkt/Leerzeichen, Dezimalkomma, optional €."""
    t = re.sub(r"[€\s ]", "", text).replace(".", "").replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation:
        raise ValueError(f"kein Betrag: {text!r}") from None
def datum(text: str) -> date:
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()
def de(x: Decimal) -> str:
    """Betrag für Fehlermeldungen: 1.234,56"""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
@dataclass
class Partei:
    name: str
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "DE"
    ust_id: str = ""
    steuernummer: str = ""
    email: str = ""
    iban: str = ""
    bic: str = ""
@dataclass
class Position:
    nr: str
    bezeichnung: str
    menge: Decimal
    einheit: str          # UN/ECE Rec 20, z. B. HUR, H87, C62
    einzelpreis: Decimal
    netto: Decimal
    ust_satz: Decimal
@dataclass
class Rechnung:
    nummer: str
    datum: date
    verkaeufer: Partei
    kaeufer: Partei
    positionen: list[Position]
    summe_netto: Decimal
    summe_brutto: Decimal
    summe_ust: Decimal | None = None
    steuern: dict[Decimal, Decimal] = field(default_factory=dict)  # Satz -> gedruckter Steuerbetrag
    leistungsdatum: date | None = None
    faellig: date | None = None
    waehrung: str = "EUR"
    vorlage: str = ""
class SummenFehler(ValueError):
    pass
def summenabgleich(r: Rechnung) -> dict[Decimal, tuple[Decimal, Decimal]]:
    """Prüft alle Summen; liefert {Satz: (Basis, Steuer)} für die XML oder wirft SummenFehler."""
    if not r.positionen:
        raise SummenFehler("keine Positionen erkannt")
    basis: dict[Decimal, Decimal] = {}
    for p in r.positionen:
        if p.ust_satz <= 0:
            raise SummenFehler(f"Position {p.nr}: Steuersatz 0 % wird im ersten Wurf nicht unterstützt")
        if abs(runde(p.menge * p.einzelpreis) - p.netto) > CENT:
            raise SummenFehler(f"Position {p.nr}: Menge × Einzelpreis = {de(runde(p.menge * p.einzelpreis))} ≠ {de(p.netto)}")
        basis[p.ust_satz] = basis.get(p.ust_satz, Decimal(0)) + p.netto
    summe = sum(basis.values(), Decimal(0))
    if summe != r.summe_netto:
        raise SummenFehler(f"Netto: Positionen {de(summe)} ≠ Rechnung {de(r.summe_netto)}")
    ergebnis = {}
    for satz, b in basis.items():
        steuer = runde(b * satz / 100)
        if satz in r.steuern:
            if abs(r.steuern[satz] - steuer) > CENT:
                raise SummenFehler(f"Umsatzsteuer {satz} %: berechnet {de(steuer)} ≠ Rechnung {de(r.steuern[satz])}")
            steuer = r.steuern[satz]
        ergebnis[satz] = (b, steuer)
    ust = sum((s for _, s in ergebnis.values()), Decimal(0))
    if r.summe_ust is not None and ust != r.summe_ust:
        raise SummenFehler(f"Umsatzsteuer: berechnet {de(ust)} ≠ Rechnung {de(r.summe_ust)}")
    if r.summe_netto + ust != r.summe_brutto:
        raise SummenFehler(f"Brutto: {de(r.summe_netto)} + {de(ust)} ≠ Rechnung {de(r.summe_brutto)}")
    return ergebnis
```

Hinweis zu den Fehlerfällen im Test: Fall „19 %“ (gedruckt 17,00) muss vor „Umsatzsteuer“ greifen; Fall „Brutto“ hat `ust` 19,00 korrekt, aber Brutto 120,00. Die Reihenfolge im Code oben erfüllt das.

- [ ] **Step 5: Tests grün**

Run: `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q`
Expected: alle PASS

- [ ] **Step 7: Commit und Push**

```bash
git -C /root/erechnung-konverter add -A
git -C /root/erechnung-konverter commit -m "Gerüst, Rechnungsmodell und Summenabgleich mit Tests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter push origin main
```
