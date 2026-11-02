"""Texterkennung: ohne Tesseract mit einem Ersatzprogramm, mit Tesseract nur wenn vorhanden."""
import shutil, sys
from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung import ocr
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, VorlagenFehler, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER, bild_pdf, pdf_aus_text
from test_vorlagen import TEXT, VORLAGE

LEXWARE = (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
# Ersatz für tesseract.exe: <quelle> <bild> <ausgabebasis> -l deu …; schreibt <ausgabebasis>.txt und protokolliert den Aufruf
ERSATZ = """import pathlib, sys, time
quelle, bild, basis = sys.argv[1:4]
q = pathlib.Path(quelle).read_text(encoding="utf-8")
if q == "SCHLAF":
    time.sleep(30)
if q == "FEHLER":
    sys.exit(3)
pathlib.Path(quelle + ".aufrufe").open("a", encoding="utf-8").write(" ".join(sys.argv[2:]) + "\\n")
assert pathlib.Path(bild).read_bytes()[:8] == b"\\x89PNG\\r\\n\\x1a\\n"
pathlib.Path(basis + ".txt").write_text(q, encoding="utf-8")
"""

@pytest.fixture
def ersatz(tmp_path):
    (tmp_path / "ersatz.py").write_text(ERSATZ, encoding="utf-8")
    (tmp_path / "arbeit").mkdir()
    def aufruf(text):
        (tmp_path / "quelle.txt").write_text(text, encoding="utf-8")
        return [sys.executable, str(tmp_path / "ersatz.py"), str(tmp_path / "quelle.txt")]
    return aufruf

def bild(tmp_path, zeilen, name="bild.pdf"):
    p = tmp_path / name
    p.write_bytes(bild_pdf(pdf_aus_text(zeilen)))
    return p

def test_bereinige():
    assert ocr.bereinige("4 Arbeitsstunde 1| Stunde  90,00 | 19,00 90,00 \n\n x") == "4 Arbeitsstunde 1 Stunde 90,00 19,00 90,00\nx"

def test_erkenne_je_seite(tmp_path, ersatz):
    pdf = bild(tmp_path, ["Seite"] * 80)                   # zwei Seiten
    text = ocr.erkenne(pdf, tmp_path / "arbeit", ersatz("Zeile | eins"))
    assert text == "Zeile eins\nZeile eins"
    aufrufe = (tmp_path / "quelle.txt.aufrufe").read_text(encoding="utf-8").splitlines()
    assert len(aufrufe) == 2 and all("-l deu" in a and "--dpi 300" in a for a in aufrufe)
    assert all(str(tmp_path / "arbeit") in a for a in aufrufe)  # Bilder im Arbeitsordner
    assert list((tmp_path / "arbeit").iterdir()) == []      # aufgeräumt

def test_erkenne_frist(tmp_path, ersatz, monkeypatch):
    monkeypatch.setattr(ocr, "FRIST", 1)
    with pytest.raises(ValueError, match="Texterkennung"):
        ocr.erkenne(bild(tmp_path, ["x"]), tmp_path / "arbeit", ersatz("SCHLAF"))
    assert list((tmp_path / "arbeit").iterdir()) == []

def test_erkenne_fehlercode(tmp_path, ersatz):
    with pytest.raises(ValueError, match="Texterkennung"):
        ocr.erkenne(bild(tmp_path, ["x"]), tmp_path / "arbeit", ersatz("FEHLER"))

def test_erkenne_zu_viele_seiten(tmp_path, ersatz, monkeypatch):
    monkeypatch.setattr(ocr, "MAX_SEITEN", 1)
    with pytest.raises(ValueError, match="Seiten"):
        ocr.erkenne(bild(tmp_path, ["Seite"] * 80), tmp_path / "arbeit", ersatz("x"))

def test_tesseract_aus_paket(tmp_path, monkeypatch):
    (tmp_path / "tesseract.exe").write_bytes(b"")
    monkeypatch.setattr(ocr, "PAKET", tmp_path)
    assert ocr.tesseract() == [str(tmp_path / "tesseract.exe"), "--tessdata-dir", str(tmp_path / "tessdata")]

@pytest.fixture
def vorlagen(tmp_path):
    (tmp_path / "test.yml").write_text(VORLAGE, encoding="utf-8")
    return lade_vorlagen(tmp_path)

def test_lies_rechnung_per_ocr(tmp_path, vorlagen):
    r = lies_rechnung(bild(tmp_path, TEXT.splitlines()), vorlagen, VERKAEUFER, ocr=lambda pdf: TEXT)
    assert (r.nummer, r.summe_brutto, r.ocr_text) == ("RE9001", D("238.00"), TEXT)

def test_text_pdf_ohne_ocr(tmp_path, vorlagen):
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    r = lies_rechnung(pdf, vorlagen, VERKAEUFER, ocr=lambda pdf: pytest.fail("OCR bei Text-PDF"))
    assert r.ocr_text == ""

def test_ocr_fehler_mit_hinweis(tmp_path, vorlagen):
    with pytest.raises(VorlagenFehler, match="per Texterkennung gelesen"):
        lies_rechnung(bild(tmp_path, ["x"]), vorlagen, VERKAEUFER, ocr=lambda pdf: TEXT.replace("Brutto", "Brotto"))

def test_ohne_ocr_kein_text(tmp_path, vorlagen):
    with pytest.raises(VorlagenFehler, match="kein Text"):
        lies_rechnung(bild(tmp_path, TEXT.splitlines()), vorlagen, VERKAEUFER)

@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
def test_tesseract_echt(tmp_path):
    """Synthetische Lexware-Rechnung als Bild-PDF durch das echte Tesseract (gm-claude, VM)."""
    (tmp_path / "arbeit").mkdir()
    pdf = bild(tmp_path, LEXWARE.splitlines())
    text = ocr.erkenne(pdf, tmp_path / "arbeit", ocr.tesseract())
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD), VERKAEUFER, ocr=lambda p: text)
    assert (r.nummer, str(r.datum)) == ("RE9146", "2026-10-15")
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
    assert [p.netto for p in r.positionen] == [D("190.00"), D("10.00")]
