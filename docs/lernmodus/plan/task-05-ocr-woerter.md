# Task 05: Texterkennung mit Wortlage (TSV), Bereichs-Vorlagen bei Bild-PDF

Spezifikation: `docs/lernmodus/spezifikation.md` 6.1, 6.2 (Unschärfe), 6.5; Hauptspezifikation 3.2. Global Constraints in `index.md`.

**Files:**
- Create: `tests/test_bereiche_ocr.py`
- Modify: `erechnung/ocr.py`, `erechnung/vorlagen.py` (`lies_rechnung`, OCR-Weg), `erechnung/ueberwachen.py` (nur `lade_konfig`: `ocr.erkenne` → `ocr.erkenne_seiten`)

**Interfaces:**
- Consumes: `bereiche.Wort`, `Seite`, `rechnung_aus_bereichen(..., ocr=True)` (Task 02/04); bestehendes `ocr.erkenne(pdf, arbeit, aufruf) -> str`.
- Produces:
  - `ocr.tsv_woerter(tsv: str, breite: int, hoehe: int) -> Seite`
  - `ocr.erkenne_seiten(pdf: Path, arbeit: Path, aufruf: list[str]) -> tuple[str, list[Seite]]` (ein Tesseract-Lauf je Seite mit `txt tsv`)
  - `ocr.erkenne()` bleibt mit gleichem Verhalten und Aufruf (bestehende Tests unverändert)
  - `lies_rechnung(..., ocr=…)`: `ocr` darf `str` oder `(str, list[Seite])` liefern
  - `Konfig.ocr` ist ab jetzt `partial(ocr.erkenne_seiten, arbeit=…, aufruf=…)`

- [ ] **Step 1: Failing tests** – `tests/test_bereiche_ocr.py`

```python
import shutil, sys
from decimal import Decimal as D
from functools import partial
from pathlib import Path
import pytest
from erechnung import ocr
from erechnung.bereiche import Wort
from erechnung.vorlagen import STANDARD, VorlagenFehler, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER, bild_pdf
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
DATEN = Path(__file__).parent / "daten"
TSV = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
       "1\t1\t0\t0\t0\t0\t0\t0\t1000\t2000\t-1\t\n"
       "5\t1\t1\t1\t1\t1\t100\t200\t50\t20\t96.1\tBeleg\n"
       "5\t1\t1\t1\t1\t2\t160\t200\t40\t20\t91.0\t \n"
       "5\t1\t1\t1\t1\t3\t500\t400\t100\t20\t-1\tx\n")
def test_tsv_woerter():
    assert ocr.tsv_woerter(TSV, 1000, 2000) == [Wort("Beleg", 0.1, 0.1, 0.15, 0.11)]
ERSATZ = """import pathlib, sys
bild, basis = sys.argv[1:3]
pathlib.Path(basis + ".txt").write_text("Beispiel Werkstatt Belegnummer", encoding="utf-8")
if "tsv" in sys.argv:
    pathlib.Path(basis + ".tsv").write_text("level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n5\\t1\\t1\\t1\\t1\\t1\\t10\\t20\\t30\\t10\\t90\\tBeleg\\n", encoding="utf-8")
"""
def test_erkenne_seiten_mit_ersatz(tmp_path):
    (tmp_path / "e.py").write_text(ERSATZ, encoding="utf-8")
    (tmp_path / "arbeit").mkdir()
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1), dpi=100))
    text, seiten = ocr.erkenne_seiten(pdf, tmp_path / "arbeit", [sys.executable, str(tmp_path / "e.py")])
    assert text == "Beispiel Werkstatt Belegnummer" and len(seiten) == 1 and seiten[0][0].text == "Beleg"
    assert list((tmp_path / "arbeit").iterdir()) == []          # temporärer Ordner gelöscht
def test_bereiche_ohne_wortlage(tmp_path):
    (tmp_path / "v").mkdir()
    shutil.copy(DATEN / "bereiche-beispiel.yml", tmp_path / "v" / "b.yml")
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1), dpi=100))
    with pytest.raises(VorlagenFehler, match="Wortlage"):
        lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER,
                      ocr=lambda p: "Beispiel Werkstatt Belegnummer")
@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
@pytest.mark.parametrize("skala", [1.0, 0.95])
def test_bereiche_per_tesseract(tmp_path, skala):
    (tmp_path / "v").mkdir()
    (tmp_path / "arbeit").mkdir()
    shutil.copy(DATEN / "bereiche-beispiel.yml", tmp_path / "v" / "b.yml")
    pdf = tmp_path / "edge.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1, skala=skala)))
    erkennen = partial(ocr.erkenne_seiten, arbeit=tmp_path / "arbeit", aufruf=ocr.tesseract())
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER, ocr=erkennen)
    assert (r.nummer, r.summe_netto, r.summe_brutto, [p.netto for p in r.positionen]) == \
        ("BW-2026-17", D("240.00"), D("285.60"), [D("190.00"), D("50.00")])
    assert r.ocr_text
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_bereiche_ocr.py -q`

- [ ] **Step 3: `ocr.py`** – den Schleifenkörper von `erkenne` in `_lauf(pdf, arbeit, aufruf, tsv: bool)` verschieben; `erkenne` ruft `_lauf(..., tsv=False)[0]` (identischer Tesseract-Aufruf wie bisher), `erkenne_seiten` `_lauf(..., tsv=True)`. Mit `tsv=True` wird an den Aufruf `"txt", "tsv"` angehängt (Tesseract schreibt dann `<basis>.txt` und `<basis>.tsv` in einem Lauf).

```python
from .bereiche import Seite, Wort
def tsv_woerter(tsv: str, breite: int, hoehe: int) -> Seite:
    """Tesseract-TSV: Ebene 5 = Wort; conf < 0 und leere Wörter verwerfen; Lage relativ zum Bild."""
    woerter = []
    for z in tsv.splitlines()[1:]:
        f = z.split("\t")
        if len(f) < 12 or f[0] != "5" or float(f[10]) < 0 or not f[11].strip():
            continue
        l, t, w, h = (int(x) for x in f[6:10])
        woerter.append(Wort(f[11].strip(), l / breite, t / hoehe, (l + w) / breite, (t + h) / hoehe))
    return woerter
def _lauf(pdf: Path, arbeit: Path, aufruf: list[str], tsv: bool) -> tuple[str, list[Seite]]:
    d = pdfium.PdfDocument(pdf)
    try:
        if len(d) > MAX_SEITEN:
            raise ValueError(f"zu viele Seiten für die Texterkennung ({len(d)}, höchstens {MAX_SEITEN})")
        texte, seiten = [], []
        with tempfile.TemporaryDirectory(prefix="ocr-", dir=arbeit) as tmp:
            for i, s in enumerate(d):
                skala = min(DPI / 72, MAX_PIXEL / max(s.get_size()))
                bild, basis = Path(tmp) / f"{i}.png", Path(tmp) / str(i)
                pil = s.render(scale=skala, grayscale=True).to_pil()
                pil.save(bild)
                try:
                    subprocess.run([*aufruf, str(bild), str(basis), "-l", "deu", "--psm", "6", "--dpi", str(round(skala * 72)),
                                    *(("txt", "tsv") if tsv else ())],
                                   check=True, capture_output=True, timeout=FRIST,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except subprocess.CalledProcessError as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}, Code {e.returncode}): "
                                     f"{e.stderr.decode(errors='replace').strip()[-300:]}") from None
                except (subprocess.TimeoutExpired, OSError) as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}): {e}") from None
                texte.append(basis.with_suffix(".txt").read_text(encoding="utf-8"))
                if tsv:
                    seiten.append(tsv_woerter(basis.with_suffix(".tsv").read_text(encoding="utf-8"), *pil.size))
    finally:
        d.close()
    return bereinige("\n".join(t.rstrip("\n\f") for t in texte)), seiten
def erkenne(pdf: Path, arbeit: Path, aufruf: list[str]) -> str:
    return _lauf(pdf, arbeit, aufruf, tsv=False)[0]
def erkenne_seiten(pdf: Path, arbeit: Path, aufruf: list[str]) -> tuple[str, list[Seite]]:
    return _lauf(pdf, arbeit, aufruf, tsv=True)
```

Zirkelimport prüfen: `bereiche` importiert `modell` und `pdfplumber`, nicht `ocr` – unbedenklich.

- [ ] **Step 4: `lies_rechnung` (OCR-Weg)** in `vorlagen.py` ersetzen:

```python
    erg = ocr(pdf)
    text, seiten = erg if isinstance(erg, tuple) else (erg, None)
    try:
        v = finde_vorlage(text, vorlagen)
        if v.get("art") == "bereiche":
            if seiten is None:
                raise VorlagenFehler("Texterkennung ohne Wortlage, Bereichs-Vorlage nicht lesbar")
            r = rechnung_aus_bereichen(seiten, v, verkaeufer, ocr=True)
        else:
            r = rechnung_aus_text(text, v, verkaeufer)
    except ValueError as e:
        raise VorlagenFehler(f"{e} ({OCR_HINWEIS})") from None
    r.ocr_text = text
    return r
```

- [ ] **Step 5: `ueberwachen.lade_konfig`** – `partial(ocr.erkenne, …)` → `partial(ocr.erkenne_seiten, …)`; Typ `ocr: Callable[[Path], str | tuple] | None`. Die Startmeldung (`k.ocr.keywords["aufruf"]`) bleibt gültig.

- [ ] **Step 6: Alle Tests** – `/root/.venvs/erechnung/bin/python -m pytest -q`. Auf gm-claude ist Tesseract installiert, die Tesseract-Tests laufen also mit. Liest Tesseract im synthetischen Muster etwas falsch (z. B. `%`), erst `tests/hilfen_bereiche.py` prüfen (Schriftgröße 10 pt, 300 dpi); die Unschärfe in `treffer` (≥ 0,85) nicht weiter senken. Kein Erfolg → im Commit vermerken und Hauptsitzung melden, nicht den Test aufweichen.
- [ ] **Step 6b: Echte Lexware-Tests** – `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest -q -m echt` grün (Regex-Weg unverändert).

- [ ] **Step 7: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/ocr.py erechnung/vorlagen.py erechnung/ueberwachen.py tests/test_bereiche_ocr.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Texterkennung liefert Wortlage, Bereichs-Vorlagen auch für Bild-PDFs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
