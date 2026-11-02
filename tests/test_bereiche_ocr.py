"""Texterkennung mit Wortlage (Tesseract-TSV) und Bereichsvorlagen bei Bild-PDFs (Lernmodus, Task 05)."""
import shutil
import sys
from decimal import Decimal as D
from functools import partial
from pathlib import Path
import pytest
from erechnung import ocr
from erechnung.bereiche import Wort, finde_anker, treffer
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


# Ersatz-Tesseract: schreibt txt und, mit „txt tsv“ im Aufruf, auch tsv; merkt sich die Aufrufe
ERSATZ = """import pathlib, sys
bild, basis = sys.argv[1:3]
with open(pathlib.Path(basis).parent.parent.parent / "aufrufe.txt", "a", encoding="utf-8") as f:
    f.write(" ".join(sys.argv[3:]) + "\\n")
pathlib.Path(basis + ".txt").write_text("Beispiel Werkstatt Belegnummer", encoding="utf-8")
if sys.argv[-2:] == ["txt", "tsv"]:
    pathlib.Path(basis + ".tsv").write_text("level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\ttop\\twidth\\theight\\tconf\\ttext\\n5\\t1\\t1\\t1\\t1\\t1\\t10\\t20\\t30\\t10\\t90\\tBeleg\\n", encoding="utf-8")
"""


def _ersatz(tmp_path):
    (tmp_path / "e.py").write_text(ERSATZ, encoding="utf-8")
    (tmp_path / "arbeit").mkdir()
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1), dpi=100))
    return pdf, [sys.executable, str(tmp_path / "e.py")]


def test_erkenne_seiten_mit_ersatz(tmp_path):
    pdf, aufruf = _ersatz(tmp_path)
    lesarten = list(ocr.erkenne_seiten(pdf, tmp_path / "arbeit", aufruf))
    assert [n for n, _, _ in lesarten] == [n for n, _, _ in ocr.LESARTEN]          # dieselben Lesarten wie erkenne
    name, text, seiten = lesarten[0]
    assert text == "Beispiel Werkstatt Belegnummer" and len(seiten) == 1 and seiten[0][0].text == "Beleg"
    assert list((tmp_path / "arbeit").iterdir()) == []                              # temporärer Ordner gelöscht
    aufrufe = (tmp_path / "aufrufe.txt").read_text(encoding="utf-8").splitlines()
    assert len(aufrufe) == 4 and all(a.endswith("txt tsv") for a in aufrufe)


def test_erkenne_ohne_tsv(tmp_path):
    """erkenne bleibt beim alten Aufruf (ohne txt tsv) und liefert (Name, Text)."""
    pdf, aufruf = _ersatz(tmp_path)
    assert next(ocr.erkenne(pdf, tmp_path / "arbeit", aufruf)) == ("psm 6", "Beispiel Werkstatt Belegnummer")
    assert not (tmp_path / "aufrufe.txt").read_text(encoding="utf-8").strip().endswith("tsv")


def _vorlagen(tmp_path):
    (tmp_path / "v").mkdir()
    shutil.copy(DATEN / "bereiche-beispiel.yml", tmp_path / "v" / "b.yml")
    return lade_vorlagen(STANDARD, tmp_path / "v")


def test_bereiche_ohne_wortlage(tmp_path):
    pdf = tmp_path / "b.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1), dpi=100))
    with pytest.raises(VorlagenFehler, match="Wortlage"):
        lies_rechnung(pdf, _vorlagen(tmp_path), VERKAEUFER, ocr=lambda p: [("psm 6", "Beispiel Werkstatt Belegnummer")])


@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
@pytest.mark.parametrize("skala", [1.0, 0.95])
def test_bereiche_per_tesseract(tmp_path, skala):
    (tmp_path / "arbeit").mkdir()
    pdf = tmp_path / "edge.pdf"
    pdf.write_bytes(bild_pdf(werkstatt_pdf(MUSTER1, SUMMEN1, skala=skala)))
    erkennen = partial(ocr.erkenne_seiten, arbeit=tmp_path / "arbeit", aufruf=ocr.tesseract())
    r = lies_rechnung(pdf, _vorlagen(tmp_path), VERKAEUFER, ocr=erkennen)
    assert (r.nummer, r.summe_netto, r.summe_brutto, [p.netto for p in r.positionen]) == \
        ("BW-2026-17", D("240.00"), D("285.60"), [D("190.00"), D("50.00")])
    assert r.ocr_text and r.ocr_lesart == "psm 6"
    assert list((tmp_path / "arbeit").iterdir()) == []


# --- aus Review Task 02: Anker-Suche bei Texterkennung ---
def _w(text, x0, top):
    return Wort(text, x0, top, x0 + 0.01 * len(text), top + 0.012)


def test_treffer_ocr_unschaerfe():
    seite = [_w("Belegnurnmer", 0.5, 0.15)]                       # typischer Lesefehler m → rn
    assert treffer(seite, "Belegnummer") == []
    assert treffer(seite, "Belegnummer", ocr=True) == [(0.5, 0.15, 0.62, None)]
    assert treffer([_w("Lieferschein", 0.5, 0.15)], "Belegnummer", ocr=True) == []
    assert treffer([_w("Belegnummer", 0.5, 0.15), _w("Belegnurnmer", 0.5, 0.3)], "Belegnummer", ocr=True) == \
        [(0.5, 0.15, 0.61, None)]                                    # genauer Treffer schlägt unscharfen


def test_anker_naechster_zur_ecke():
    seite = [_w("Summe", 0.1, 0.2), _w("Summe", 0.52, 0.34), _w("Summe", 0.5, 0.8)]
    i, dx, dy = finde_anker([seite], {"text": "Summe", "rahmen": [0.5, 0.35, 0.6, 0.36]}, "erste")
    assert (i, round(dx, 4), round(dy, 4)) == (0, 0.02, -0.01)


def test_anker_letzte_seite():
    seiten = [[_w("Endbetrag", 0.5, 0.4)], [_w("Endbetrag", 0.5, 0.5)], [_w("AGB", 0.1, 0.1)]]
    anker = {"text": "Endbetrag", "rahmen": [0.5, 0.4, 0.6, 0.41]}
    assert finde_anker(seiten, anker, "letzte")[0] == 1           # letzte Seite mit Anker, AGB-Seite übersprungen
    assert finde_anker(seiten, anker, "erste")[0] == 0
