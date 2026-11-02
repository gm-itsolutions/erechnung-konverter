# Task 04: Vorlagen-Auswertung und Vorlage „lexware-gm-it“

Spezifikation: Abschnitt 4.1 (Entscheidung eigene Regex-Vorlagen), 5. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/vorlagen.py`, `erechnung/vorlagen/lexware-gm-it.yml`, `tests/test_vorlagen.py`, `tests/daten/lexware-synthetisch.txt`

**Interfaces:**
- Consumes: `erechnung.modell` (`Partei`, `Position`, `Rechnung`, `betrag`, `datum`, `summenabgleich`); `erechnung.betraege.betraege` (Task 02); echte Daten in `/root/erechnung-testdaten/` (Task 02: `RE01xx.pdf`, `.txt`, `.layout.txt`, `.lexware.xml`).
- Produces:
  - `class VorlagenFehler(ValueError)`
  - `STANDARD = Path(__file__).parent / "vorlagen"`
  - `pdf_text(pdf: Path, layout: bool = False) -> str` (Seiten mit `\n` verbunden)
  - `lade_vorlagen(*ordner: Path) -> list[dict]` (nicht vorhandene Ordner überspringen; Regexe beim Laden kompilieren → `VorlagenFehler` mit Dateiname)
  - `finde_vorlage(text: str, vorlagen: list[dict]) -> dict`
  - `rechnung_aus_text(text: str, vorlage: dict, verkaeufer: Partei) -> Rechnung`
  - `lies_rechnung(pdf: Path, vorlagen: list[dict], verkaeufer: Partei) -> Rechnung`

- [ ] **Step 1: Failing tests (Engine)** – `tests/test_vorlagen.py`

```python
from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung.vorlagen import VorlagenFehler, finde_vorlage, lade_vorlagen, lies_rechnung, rechnung_aus_text
from erechnung.modell import summenabgleich
from hilfen import VERKAEUFER, pdf_aus_text
VORLAGE = """
name: test-layout
schluesselwoerter: ["Testfirma", "Rechnung Nr."]
felder:
  nummer: 'Rechnung Nr\\.\\s*(\\S+)'
  datum: 'Datum:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})'
  faellig: 'zahlbar bis\\s*(\\d{2}\\.\\d{2}\\.\\d{4})'
  summe_netto: '^Netto\\s+([\\d.,]+)'
  summe_brutto: '^Brutto\\s+([\\d.,]+)'
steuern: '^USt (?P<satz>\\d+) %\\s+(?P<betrag>[\\d.,]+)'
kaeufer: 'An:\\n(?P<name>.+)\\n(?P<strasse>.+)\\n(?P<plz>\\d{5}) (?P<ort>.+)'
positionen:
  start: '^Pos Text'
  ende: '^Netto'
  zeile: '^(?P<nr>\\d+) (?P<bezeichnung>.+?) (?P<menge>[\\d,]+) (?P<einheit>Std|Stk) (?P<einzelpreis>[\\d.,]+) (?P<netto>[\\d.,]+)$'
  ust_satz: 19
  ignorieren: ['^Seite \\d+']
einheiten: {Std: HUR, Stk: H87}
"""
TEXT = """Testfirma · Weg 1 · 16928 Pritzwalk
An:
Beispiel Handel GmbH
Hauptstraße 5
19348 Perleberg
Rechnung Nr. RE9001
Datum: 15.10.2026
Pos Text Menge Einheit Preis Gesamt
1 IT-Service 2,00 Std 95,00 190,00
Server geprüft
Seite 1
2 Kabel 2 Stk 5,00 10,00
Netto 200,00
USt 19 % 38,00
Brutto 238,00
zahlbar bis 29.10.2026"""
@pytest.fixture
def vorlagen(tmp_path):
    (tmp_path / "test.yml").write_text(VORLAGE, encoding="utf-8")
    return lade_vorlagen(tmp_path, tmp_path / "gibt-es-nicht")
def test_finde_und_lies(vorlagen):
    v = finde_vorlage(TEXT, vorlagen)
    r = rechnung_aus_text(TEXT, v, VERKAEUFER)
    assert (r.nummer, str(r.datum), str(r.faellig), r.vorlage) == ("RE9001", "2026-10-15", "2026-10-29", "test-layout")
    assert r.kaeufer.name == "Beispiel Handel GmbH" and r.kaeufer.plz == "19348" and r.kaeufer.ort == "Perleberg"
    assert [p.bezeichnung for p in r.positionen] == ["IT-Service Server geprüft", "Kabel"]
    assert [p.einheit for p in r.positionen] == ["HUR", "H87"]
    assert r.steuern == {D("19"): D("38.00")}
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
def test_keine_vorlage(vorlagen):
    with pytest.raises(VorlagenFehler, match="keine Vorlage"):
        finde_vorlage("Andere Firma", vorlagen)
def test_mehrere_vorlagen(tmp_path):
    for n in ("a", "b"):
        (tmp_path / f"{n}.yml").write_text(VORLAGE.replace("test-layout", n), encoding="utf-8")
    with pytest.raises(VorlagenFehler, match="mehrere Vorlagen: a, b"):
        finde_vorlage(TEXT, lade_vorlagen(tmp_path))
def test_pflichtfeld_fehlt(vorlagen):
    with pytest.raises(VorlagenFehler, match="summe_brutto"):
        rechnung_aus_text(TEXT.replace("Brutto", "Gesamt"), vorlagen[0], VERKAEUFER)
def test_kaputte_vorlage(tmp_path):
    (tmp_path / "x.yml").write_text(VORLAGE.replace("'^Pos Text'", "'(['"), encoding="utf-8")
    with pytest.raises(VorlagenFehler, match="x.yml"):
        lade_vorlagen(tmp_path)
def test_pdf_ohne_text(tmp_path, vorlagen):
    leer = tmp_path / "leer.pdf"
    leer.write_bytes(pdf_aus_text([]))
    with pytest.raises(VorlagenFehler, match="kein Text"):
        lies_rechnung(leer, vorlagen, VERKAEUFER)
def test_pdf_durchlauf(tmp_path, vorlagen):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    assert lies_rechnung(pdf, vorlagen, VERKAEUFER).summe_brutto == D("238.00")
```

- [ ] **Step 2: Tests scheitern** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_vorlagen.py -q`

- [ ] **Step 3: `erechnung/vorlagen.py`**

```python
"""Vorlagen je Layout (YAML, angelehnt an invoice2data) → Rechnung. Spezifikation Abschnitt 5."""
import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
import yaml
from .modell import Partei, Position, Rechnung, betrag, datum
STANDARD = Path(__file__).parent / "vorlagen"
PFLICHT = ("nummer", "datum", "summe_netto", "summe_brutto")
class VorlagenFehler(ValueError):
    pass
def pdf_text(pdf: Path, layout: bool = False) -> str:
    with pdfplumber.open(pdf) as d:
        return "\n".join(s.extract_text(layout=layout) or "" for s in d.pages)
def _pruefe(v: dict, datei: Path) -> dict:
    try:
        assert v.get("name") and v.get("schluesselwoerter"), "name/schluesselwoerter fehlen"
        assert all(f in v.get("felder", {}) for f in PFLICHT), f"felder brauchen {', '.join(PFLICHT)}"
        assert all(k in v.get("positionen", {}) for k in ("start", "ende", "zeile")), "positionen: start/ende/zeile"
        muster = [*v["felder"].values(), v.get("steuern"), v.get("kaeufer"),
                  *(v["positionen"][k] for k in ("start", "ende", "zeile")), *v["positionen"].get("ignorieren", [])]
        for m in muster:
            if m:
                re.compile(m)
    except (AssertionError, re.error) as e:
        raise VorlagenFehler(f"Vorlage {datei.name}: {e}") from None
    return v
def lade_vorlagen(*ordner: Path) -> list[dict]:
    vorlagen = []
    for o in ordner:
        if o.is_dir():
            for datei in sorted(o.glob("*.yml")):
                vorlagen.append(_pruefe(yaml.safe_load(datei.read_text(encoding="utf-8")) or {}, datei))
    return vorlagen
def finde_vorlage(text: str, vorlagen: list[dict]) -> dict:
    passend = [v for v in vorlagen if all(k in text for k in v["schluesselwoerter"])]
    if not passend:
        raise VorlagenFehler("keine Vorlage passt zu diesem Layout")
    if len(passend) > 1:
        raise VorlagenFehler("mehrere Vorlagen: " + ", ".join(v["name"] for v in passend))
    return passend[0]
def _feld(text: str, v: dict, name: str) -> str | None:
    muster = v["felder"].get(name)
    m = re.search(muster, text, re.MULTILINE) if muster else None
    if not m and name in PFLICHT:
        raise VorlagenFehler(f"Feld {name} nicht gefunden (Vorlage {v['name']})")
    return m.group(1).strip() if m else None
def _satz(t: str) -> Decimal:
    return Decimal(t.replace(",", ".").replace("%", "").strip())
def _positionen(text: str, v: dict) -> list[Position]:
    p = v["positionen"]
    zeilen = text.splitlines()
    try:
        von = next(i for i, z in enumerate(zeilen) if re.search(p["start"], z))
        bis = max(i for i, z in enumerate(zeilen) if re.search(p["ende"], z))
    except (StopIteration, ValueError):
        raise VorlagenFehler(f"Positionsblock nicht gefunden (Vorlage {v['name']})") from None
    ergebnis: list[Position] = []
    for z in zeilen[von + 1:bis]:
        if not z.strip() or any(re.search(m, z) for m in p.get("ignorieren", [])) or re.search(p["start"], z):
            continue
        m = re.search(p["zeile"], z)
        if m:
            g = m.groupdict()
            ergebnis.append(Position(
                nr=g.get("nr") or str(len(ergebnis) + 1), bezeichnung=g["bezeichnung"].strip(),
                menge=betrag(g["menge"]), einheit=v.get("einheiten", {}).get((g.get("einheit") or "").strip(), "C62"),
                einzelpreis=betrag(g["einzelpreis"]), netto=betrag(g["netto"]),
                ust_satz=_satz(g["ust_satz"]) if g.get("ust_satz") else Decimal(str(p.get("ust_satz", 19)))))
        elif ergebnis:
            ergebnis[-1].bezeichnung += " " + z.strip()
    return ergebnis
def rechnung_aus_text(text: str, vorlage: dict, verkaeufer: Partei) -> Rechnung:
    v = vorlage
    kaeufer = Partei("")
    if v.get("kaeufer"):
        m = re.search(v["kaeufer"], text, re.MULTILINE)
        if not m:
            raise VorlagenFehler(f"Käufer nicht gefunden (Vorlage {v['name']})")
        kaeufer = Partei(**{k: w.strip() for k, w in m.groupdict().items() if w})
    steuern = {_satz(m["satz"]): betrag(m["betrag"]) for m in re.finditer(v["steuern"], text, re.MULTILINE)} if v.get("steuern") else {}
    opt = lambda n: _feld(text, v, n)
    return Rechnung(
        nummer=opt("nummer"), datum=datum(opt("datum")), verkaeufer=verkaeufer, kaeufer=kaeufer,
        positionen=_positionen(text, v), summe_netto=betrag(opt("summe_netto")), summe_brutto=betrag(opt("summe_brutto")),
        summe_ust=betrag(opt("summe_ust")) if opt("summe_ust") else None, steuern=steuern,
        leistungsdatum=datum(opt("leistungsdatum")) if opt("leistungsdatum") else None,
        faellig=datum(opt("faellig")) if opt("faellig") else None, vorlage=v["name"])
def lies_rechnung(pdf: Path, vorlagen: list[dict], verkaeufer: Partei) -> Rechnung:
    text = pdf_text(pdf)
    if not text.strip():
        raise VorlagenFehler("kein Text im PDF (als Bild gedruckt?)")
    v = finde_vorlage(text, vorlagen)
    if v.get("layout"):
        text = pdf_text(pdf, layout=True)
    return rechnung_aus_text(text, v, verkaeufer)
```

`kaeufer`-Gruppen dürfen nur Feldnamen von `Partei` tragen (`name`, `strasse`, `plz`, `ort`, `land`, `ust_id`).

- [ ] **Step 4: Engine-Tests grün** – gleicher Befehl → PASS.

- [ ] **Step 5: Vorlage „lexware-gm-it“ aus echtem Text bauen**

1. `/root/erechnung-testdaten/RE0146.txt` und `RE0146.layout.txt` lesen (nur lokal, nichts davon in Commit oder Rückmeldung zitieren außer Feldbezeichnungen wie „Rechnungsnr.“).
2. Entscheiden, ob `layout: true` nötig ist (Spalten der Positionen sauber trennbar?).
3. `erechnung/vorlagen/lexware-gm-it.yml` schreiben: Schlüsselwörter, die nur auf Marvins Lexware-Rechnungen stehen (z. B. Firmenname + Lexware-typische Feldbezeichnung), Felder, `steuern`, `kaeufer`, `positionen` (mehrzeilige Beschreibungen, Seitenumbruch/„Übertrag“ in `ignorieren`), `einheiten` (Lexware-Einheiten → UN/ECE: Stunde/Std. → HUR, Stück → H87, Pauschal/pauschal → C62, Kilometer/km → KMT, sonst C62).
4. Mit RE0148 und RE0149 gegenprüfen.

- [ ] **Step 6: Synthetischer Text im Repo** – `tests/daten/lexware-synthetisch.txt`: Kopie von `RE0146.txt` (bzw. `.layout.txt`, je nach `layout`), darin Kundenname, Anschrift, Ansprechpartner, Positionstexte, Rechnungsnummer (`RE9146`) und Beträge durch erfundene ersetzen (Summen müssen stimmen: 2 Positionen à 19 %, z. B. 190,00 + 10,00 = 200,00, USt 38,00, Brutto 238,00). Marvins eigene Firmendaten (Kopf/Fuß) dürfen bleiben, IBAN/USt-IdNr. durch die Testwerte aus `index.md` ersetzen. Test in `tests/test_vorlagen.py` ergänzen:

```python
def test_lexware_synthetisch():
    from erechnung.vorlagen import STANDARD
    text = (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
    vorlagen = lade_vorlagen(STANDARD)
    r = rechnung_aus_text(text, finde_vorlage(text, vorlagen), VERKAEUFER)
    assert r.nummer == "RE9146" and r.summe_brutto == D("238.00")
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
```

- [ ] **Step 7: Gegenprobe mit echten PDFs** (ohne Test-Datei, die schreibt Task 08):
`/root/.venvs/erechnung/bin/python -c "import sys; from pathlib import Path; from erechnung.vorlagen import *; from erechnung.modell import *; [print(n, summenabgleich(lies_rechnung(Path('/root/erechnung-testdaten')/f'{n}.pdf', lade_vorlagen(STANDARD), Partei('x')))) for n in sys.argv[1:]]" RE0146 RE0148 RE0149` (cwd Repo) → drei Ergebnisse ohne Fehler; Beträge mit `betraege()` der Lexware-XML vergleichen.

- [ ] **Step 8: Commit und Push** – vorher `git -C /root/erechnung-konverter diff --cached` auf echte Kundennamen/Anschriften prüfen.

```bash
git -C /root/erechnung-konverter add erechnung/vorlagen.py erechnung/vorlagen/lexware-gm-it.yml tests/test_vorlagen.py tests/daten/lexware-synthetisch.txt
git -C /root/erechnung-konverter commit -m "Vorlagen-Auswertung und Vorlage lexware-gm-it" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
