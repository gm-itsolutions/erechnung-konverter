# Task 02: Wörter mit Lage, Zeilen, Anker (Text-PDF)

Spezifikation: `docs/lernmodus/spezifikation.md` 6.1, 6.2. Global Constraints in `index.md`.

**Files:**
- Create: `tests/hilfen_bereiche.py`, `tests/test_bereiche_anker.py`
- Modify: `erechnung/bereiche.py` (ergänzen)

**Interfaces:**
- Consumes: Task 01 (`BereichsFehler`, `PFLICHT_FELDER`, `tests/daten/bereiche-beispiel.yml`).
- Produces (in `bereiche.py`):
  - `class Wort(NamedTuple): text: str; x0: float; top: float; x1: float; bottom: float`; `Seite = list[Wort]`
  - Konstanten `RAND = 0.005`, `BETRAG`, `DATUM`, `SATZ` (für Task 03/04)
  - `woerter_aus_pdf(pdf: Path) -> list[Seite]`
  - `zeilen(woerter: Seite) -> list[list[Wort]]`
  - `treffer(seite: Seite, text: str, ocr: bool = False) -> list[tuple[float, float, float, str | None]]` (x0, top, x1 der Wortfolge, gelesener Satz)
  - `finde_anker(seiten, anker, seite, ocr=False) -> tuple[int, float, float] | None`
  - `woerter_im_rahmen(seite, rahmen, dx=0, dy=0) -> Seite`
  - `feld_text(seiten, v, name, ocr=False, spur=None) -> tuple[int, list[str]] | None` (Pflichtfeld ohne Anker-Treffer → `BereichsFehler` „Anker „…“ nicht gefunden“)
  - `tests/hilfen_bereiche.py`: `werkstatt_pdf(zeilen, summen, dx=0.0, dy=0.0, umbruch_nach=None, uebertrag="", kopf_wiederholen=True, nummer="BW-2026-17") -> bytes`, `MUSTER1`, `SUMMEN1`

- [ ] **Step 1: Testhilfe** – `tests/hilfen_bereiche.py` (Layout „Beispiel Werkstatt“; Text-Oberkante liegt bei `y`, weil pdfminer bei Helvetica 10 pt die Oberkante rund 7,9 pt über der Grundlinie setzt)

```python
"""Synthetische Rechnung „Beispiel Werkstatt“ für Bereichs-Vorlagen (tests/daten/bereiche-beispiel.yml)."""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
W, H = A4
SPALTEN_X = (0.08, 0.14, 0.51, 0.62, 0.80)
MUSTER1 = [("1", "Inspektion nach Herstellervorgabe", "2 Std", "95,00", "190,00"),
           ("", "inkl. Probefahrt", "", "", ""),
           ("2", "Motoröl 5W-30", "4 Stk", "12,50", "50,00")]
SUMMEN1 = ("240,00", "45,60", "285,60")
def werkstatt_pdf(zeilen, summen, dx=0.0, dy=0.0, umbruch_nach=None, uebertrag="", kopf_wiederholen=True,
                  nummer="BW-2026-17") -> bytes:
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    c.setFont("Helvetica", 10)
    def t(x, y, s):
        c.drawString((x + dx) * W, H * (1 - (y + dy)) - 8, s)
    def kopf(y):
        for x, s in zip(SPALTEN_X, ("Nr", "Leistung", "Anzahl", "Preis", "Betrag")):
            t(x, y, s)
    t(0.08, 0.08, "Beispiel Werkstatt · Feldweg 2 · 16928 Pritzwalk")
    for i, s in enumerate(("Muster Kunde GmbH", "Am Markt 3", "19348 Perleberg")):
        t(0.08, 0.150 + 0.02 * i, s)
    for i, (l, w) in enumerate((("Belegnummer", nummer), ("Belegdatum", "05.11.2026"), ("Zahlbar in", "14 Tage"))):
        t(0.50, 0.150 + 0.02 * i, l)
        t(0.70, 0.150 + 0.02 * i, w)
    kopf(0.250)
    y = 0.275
    for i, z in enumerate(zeilen):
        if i == umbruch_nach:
            t(0.50, y, "Übertrag"); t(0.80, y, uebertrag)
            t(0.08, 0.95, "Seite 1/2")
            c.showPage(); c.setFont("Helvetica", 10)
            t(0.08, 0.08, "Beispiel Werkstatt · Feldweg 2 · 16928 Pritzwalk")
            t(0.50, 0.10, "Belegnummer"); t(0.70, 0.10, nummer)
            y = 0.15
            if kopf_wiederholen:
                kopf(y); y += 0.025
            t(0.50, y, "Übertrag"); t(0.80, y, uebertrag); y += 0.02
        for x, s in zip(SPALTEN_X, z):
            if s:
                t(x, y, s)
        y += 0.02
    y += 0.01
    for l, w in zip(("Summe netto", "MwSt. 19 %", "Endbetrag"), summen):
        t(0.50, y, l); t(0.80, y, w); y += 0.02
    c.save()
    return puffer.getvalue()
```

`t(0.50, y, "Übertrag"); …` steht so nur in der Testhilfe (Python erlaubt `;`); die Shell-Regel betrifft Befehle, nicht Code. Wer es sauberer will: zwei Zeilen.

- [ ] **Step 2: Failing tests** – `tests/test_bereiche_anker.py`

```python
from decimal import Decimal as D
from pathlib import Path
import yaml
from erechnung.bereiche import Wort, finde_anker, woerter_aus_pdf, zeilen
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
V = yaml.safe_load((Path(__file__).parent / "daten" / "bereiche-beispiel.yml").read_text(encoding="utf-8"))
def seiten(tmp_path, pdf: bytes):
    p = tmp_path / "m.pdf"
    p.write_bytes(pdf)
    return woerter_aus_pdf(p)
def test_woerter_relativ(tmp_path):
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    w = next(w for w in s[0] if w.text == "Belegnummer")
    assert abs(w.x0 - 0.50) < 0.002 and abs(w.top - 0.150) < 0.003 and 0 < w.bottom - w.top < 0.02
def test_zeilen_gruppiert():
    z = zeilen([Wort("b", 0.3, 0.101, 0.4, 0.111), Wort("a", 0.1, 0.100, 0.2, 0.110), Wort("c", 0.1, 0.2, 0.2, 0.21)])
    assert [[w.text for w in l] for l in z] == [["a", "b"], ["c"]]
def test_anker_verschoben(tmp_path):
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=0.02, dy=0.03))
    i, dx, dy = finde_anker(s, V["felder"]["nummer"]["anker"], "erste")
    assert i == 0 and abs(dx - 0.02) < 0.003 and abs(dy - 0.03) < 0.003
def test_anker_fehlt(tmp_path):
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    assert finde_anker(s, {"text": "Gibt es nicht", "rahmen": [0, 0, 0.1, 0.1]}, "erste") is None
```

- [ ] **Step 3: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_bereiche_anker.py -q`

- [ ] **Step 4: Implementieren** – in `erechnung/bereiche.py` ergänzen

```python
import difflib, statistics
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple
import pdfplumber
from .modell import Partei, betrag
RAND = 0.005
BETRAG = re.compile(r"-?\d[\d. ]*[,.] ?\d{2}")
DATUM = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})")
SATZ = r"(\d{1,2}(?:[,.]\d{1,2})?)"
class Wort(NamedTuple):
    text: str; x0: float; top: float; x1: float; bottom: float
Seite = list[Wort]
def woerter_aus_pdf(pdf: Path) -> list[Seite]:
    with pdfplumber.open(pdf) as d:
        return [[Wort(w["text"], w["x0"] / s.width, w["top"] / s.height, w["x1"] / s.width, w["bottom"] / s.height)
                 for w in s.extract_words()] for s in d.pages]
def zeilen(woerter: Seite) -> list[list[Wort]]:
    if not woerter:
        return []
    tol = statistics.median(w.bottom - w.top for w in woerter) / 2
    mitte = lambda w: (w.top + w.bottom) / 2
    ergebnis: list[list[Wort]] = []
    for w in sorted(woerter, key=mitte):
        if ergebnis and mitte(w) - mitte(ergebnis[-1][0]) <= tol:
            ergebnis[-1].append(w)
        else:
            ergebnis.append([w])
    return [sorted(z, key=lambda w: w.x0) for z in ergebnis]
def _norm(t: str) -> str:
    return "".join(t.split()).lower()
def treffer(seite: Seite, text: str, ocr: bool = False) -> list[tuple[float, float, float, str | None]]:
    """Wortfolgen einer Zeile, die dem Ankertext entsprechen; {satz} liest eine Zahl."""
    teile = _norm(text).split("{satz}")
    muster = re.compile(SATZ.join(map(re.escape, teile))) if len(teile) == 2 else None
    ziel, n = _norm(text), len(text.split()) + 2
    genau, unscharf = [], []
    for z in zeilen(seite):
        for i in range(len(z)):
            for j in range(i + 1, min(i + n, len(z)) + 1):
                kette = _norm("".join(w.text for w in z[i:j]))
                if muster:
                    m = muster.fullmatch(kette)
                    if m:
                        genau.append((z[i].x0, z[i].top, z[j - 1].x1, m.group(1).replace(",", ".")))
                elif kette == ziel:
                    genau.append((z[i].x0, z[i].top, z[j - 1].x1, None))
                elif ocr and difflib.SequenceMatcher(None, kette, ziel).ratio() >= 0.85:
                    unscharf.append((z[i].x0, z[i].top, z[j - 1].x1, None))
    return genau or unscharf
def finde_anker(seiten, anker, seite, ocr=False):
    x, y = anker["rahmen"][:2]
    reihenfolge = range(len(seiten)) if seite == "erste" else range(len(seiten) - 1, -1, -1)
    for i in reihenfolge:
        t = treffer(seiten[i], anker["text"], ocr)
        if t:
            tx, ty, _, _ = min(t, key=lambda h: (h[0] - x) ** 2 + (h[1] - y) ** 2)
            return i, tx - x, ty - y
    return None
def woerter_im_rahmen(seite, rahmen, dx=0.0, dy=0.0):
    x0, y0, x1, y1 = rahmen[0] + dx - RAND, rahmen[1] + dy - RAND, rahmen[2] + dx + RAND, rahmen[3] + dy + RAND
    return [w for w in seite if x0 <= (w.x0 + w.x1) / 2 <= x1 and y0 <= (w.top + w.bottom) / 2 <= y1]
def feld_text(seiten, v, name, ocr=False, spur=None):
    f = v["felder"].get(name)
    if not f:
        return None
    if "anker" in f:
        gefunden = finde_anker(seiten, f["anker"], f["seite"], ocr)
        if gefunden is None:
            if name in PFLICHT_FELDER:
                raise BereichsFehler(f"Anker „{f['anker']['text']}“ nicht gefunden (Vorlage {v['name']})")
            return None
        i, dx, dy = gefunden
    else:   # ohne Anker: Seitenversatz des Nummer-Ankers übernehmen (Druckweg verschiebt die ganze Seite)
        i, dx, dy = (0 if f["seite"] == "erste" else len(seiten) - 1), 0.0, 0.0
        n = v["felder"]["nummer"]
        if name != "nummer" and "anker" in n:
            g = finde_anker(seiten, n["anker"], n["seite"], ocr)
            if g and g[0] == i:
                dx, dy = g[1], g[2]
    r = f["rahmen"]
    if spur is not None:
        spur[name] = {"seite": i, "rahmen": [round(r[0] + dx, 4), round(r[1] + dy, 4), round(r[2] + dx, 4), round(r[3] + dy, 4)]}
    return i, [" ".join(w.text for w in z) for z in zeilen(woerter_im_rahmen(seiten[i], r, dx, dy))]
```

- [ ] **Step 5: Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`. Schlägt `test_woerter_relativ` an der Oberkante fehl (Font-Metrik), nur den Versatz `- 8` in `werkstatt_pdf` justieren, nie die Toleranz der Tests aufweichen; die Koordinaten in `bereiche-beispiel.yml` gelten dann weiter.

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/bereiche.py tests/hilfen_bereiche.py tests/test_bereiche_anker.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Wörter mit Lage und Anker-Suche" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
