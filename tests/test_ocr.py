"""Texterkennung: ohne Tesseract mit einem Ersatzprogramm, mit Tesseract nur wenn vorhanden."""
import shutil, sys
from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung import ocr
from erechnung.modell import SummenFehler, summenabgleich
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
    lesarten = list(ocr.erkenne(pdf, tmp_path / "arbeit", ersatz("Zeile | eins")))
    assert lesarten == [(n, "Zeile eins\nZeile eins") for n, _, _ in ocr.LESARTEN]
    aufrufe = (tmp_path / "quelle.txt.aufrufe").read_text(encoding="utf-8").splitlines()
    assert len(aufrufe) == 8 and all("-l deu" in a and "--dpi 300" in a for a in aufrufe)
    assert [a.split("--psm ")[1][0] for a in aufrufe] == list("66664444")
    assert sum("ohne-linien" in a for a in aufrufe) == 4    # Linien entfernt: Lesart 2 und 4, je zwei Seiten
    assert all(str(tmp_path / "arbeit") in a for a in aufrufe)  # Bilder im Arbeitsordner
    assert list((tmp_path / "arbeit").iterdir()) == []      # aufgeräumt

def test_erkenne_frist(tmp_path, ersatz, monkeypatch):
    monkeypatch.setattr(ocr, "FRIST", 1)
    with pytest.raises(ValueError, match="Texterkennung"):
        next(ocr.erkenne(bild(tmp_path, ["x"]), tmp_path / "arbeit", ersatz("SCHLAF")))
    assert list((tmp_path / "arbeit").iterdir()) == []

def test_erkenne_fehlercode(tmp_path, ersatz):
    with pytest.raises(ValueError, match="Texterkennung"):
        next(ocr.erkenne(bild(tmp_path, ["x"]), tmp_path / "arbeit", ersatz("FEHLER")))

def test_erkenne_zu_viele_seiten(tmp_path, ersatz, monkeypatch):
    monkeypatch.setattr(ocr, "MAX_SEITEN", 1)
    with pytest.raises(ValueError, match="Seiten"):
        next(ocr.erkenne(bild(tmp_path, ["Seite"] * 80), tmp_path / "arbeit", ersatz("x")))

def test_tesseract_aus_paket(tmp_path, monkeypatch):
    (tmp_path / "tesseract.exe").write_bytes(b"")
    monkeypatch.setattr(ocr, "PAKET", tmp_path)
    assert ocr.tesseract() == [str(tmp_path / "tesseract.exe"), "--tessdata-dir", str(tmp_path / "tessdata")]

@pytest.fixture
def vorlagen(tmp_path):
    (tmp_path / "test.yml").write_text(VORLAGE, encoding="utf-8")
    return lade_vorlagen(tmp_path)

def test_lies_rechnung_per_ocr(tmp_path, vorlagen):
    r = lies_rechnung(bild(tmp_path, TEXT.splitlines()), vorlagen, VERKAEUFER, ocr=lambda pdf: [("psm 6", TEXT)])
    assert (r.nummer, r.summe_brutto, r.ocr_text, r.ocr_lesart) == ("RE9001", D("238.00"), TEXT, "psm 6")

def test_text_pdf_ohne_ocr(tmp_path, vorlagen):
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    r = lies_rechnung(pdf, vorlagen, VERKAEUFER, ocr=lambda pdf: pytest.fail("OCR bei Text-PDF"))
    assert r.ocr_text == ""

def test_ocr_fehler_mit_hinweis(tmp_path, vorlagen):
    with pytest.raises(VorlagenFehler, match="per Texterkennung gelesen"):
        lies_rechnung(bild(tmp_path, ["x"]), vorlagen, VERKAEUFER, ocr=lambda pdf: [("psm 6", TEXT.replace("Brutto", "Brotto"))])

def test_ohne_ocr_kein_text(tmp_path, vorlagen):
    with pytest.raises(VorlagenFehler, match="kein Text"):
        lies_rechnung(bild(tmp_path, TEXT.splitlines()), vorlagen, VERKAEUFER)

@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
def test_tesseract_echt(tmp_path):
    """Synthetische Lexware-Rechnung als Bild-PDF durch das echte Tesseract (gm-claude, VM)."""
    (tmp_path / "arbeit").mkdir()
    pdf = bild(tmp_path, LEXWARE.splitlines())
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD), VERKAEUFER, ocr=lambda p: ocr.erkenne(p, tmp_path / "arbeit", ocr.tesseract()))
    assert (r.nummer, str(r.datum)) == ("RE9146", "2026-10-15")
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
    assert [p.netto for p in r.positionen] == [D("190.00"), D("10.00")]


# --- Rückfall auf weitere Lesarten (Spezifikation 3.2), erfundene Daten ---
POS2 = "2 Patchkabel Cat. 6 - 1 m 2 Stück 5,00 19,00 10,00\n"
ZEILE_WEG = LEXWARE.replace(POS2, "")                                   # wie psm 6: einzeilige Position fehlt

def _lies(tmp_path, lesarten, vorlagen=None):
    def gen(pdf):
        for name, text in lesarten:
            assert text is not None, f"Lesart {name} hätte nicht mehr gelesen werden dürfen"
            yield name, text
    return lies_rechnung(bild(tmp_path, ["x"]), vorlagen or lade_vorlagen(STANDARD), VERKAEUFER, ocr=gen)

def test_rueckfall_greift(tmp_path):
    r = _lies(tmp_path, [("psm 6", ZEILE_WEG), ("psm 6 ohne Linien", LEXWARE), ("psm 4", None)])
    assert (r.nummer, r.ocr_lesart, r.ocr_text, len(r.positionen)) == ("RE9146", "psm 6 ohne Linien", LEXWARE, 2)

def test_rueckfall_alle_scheitern(tmp_path):
    with pytest.raises(SummenFehler) as e:
        _lies(tmp_path, [("psm 6", ZEILE_WEG), ("psm 6 ohne Linien", ZEILE_WEG),
                         ("psm 4", ZEILE_WEG.replace("Gesamtbetrag", "Gesamtbetrog"))])
    zeilen = str(e.value).splitlines()
    assert zeilen[0].startswith("Netto:") and zeilen[0].endswith("(per Texterkennung gelesen)")   # Grund der ersten Lesart
    assert zeilen[1] == "Versuchte Lesarten: psm 6, psm 6 ohne Linien, psm 4 (Feld summe_brutto nicht gefunden (Vorlage lexware-gm-it))"

def test_rueckfall_nur_mit_nummern_gegenprobe(tmp_path, vorlagen):
    """Rückfall nur, wenn Gegenprobe der Rechnungsnummer möglich (test-layout hat keine) und bestanden ist."""
    with pytest.raises(SummenFehler, match="Versuchte Lesarten: psm 6, psm 4"):
        _lies(tmp_path, [("psm 6", TEXT.replace("Brutto 238", "Brutto 239")), ("psm 4", TEXT)], vorlagen)
    falsch = LEXWARE.replace("Rechnung RE9146", "Rechnung RE9148")
    r = _lies(tmp_path, [("psm 6", ZEILE_WEG), ("psm 6 ohne Linien", falsch), ("psm 4", LEXWARE)])
    assert r.ocr_lesart == "psm 4"

def test_rueckfall_tesseract_bricht_ab(tmp_path):
    def gen(pdf):
        yield "psm 6", ZEILE_WEG
        raise ValueError("Texterkennung fehlgeschlagen (Seite 1): Zeitüberschreitung")
    with pytest.raises(SummenFehler, match=r"(?s)^Netto.*Versuchte Lesarten: psm 6, Abbruch: Texterkennung"):
        lies_rechnung(bild(tmp_path, ["x"]), lade_vorlagen(STANDARD), VERKAEUFER, ocr=gen)

def test_gesamtfrist(tmp_path, ersatz, monkeypatch):
    monkeypatch.setattr(ocr, "GESAMTFRIST", 0)
    assert [n for n, _ in ocr.erkenne(bild(tmp_path, ["x"]), tmp_path / "arbeit", ersatz("x"))] == ["psm 6"]
    assert list((tmp_path / "arbeit").iterdir()) == []

# Ersatz-Tesseract, der wie das echte bei psm 6 die Position zwischen zwei Tabellenlinien verliert
ERSATZ_LINIEN = """import pathlib, sys
from PIL import Image
quelle, bild, basis = sys.argv[1:4]
im = Image.open(bild).convert("L")
w, h = im.size
zeilen = im.point(lambda v: 255 if v < 128 else 0).resize((1, h), Image.BOX)
linien = any(zeilen.getpixel((0, y)) > 128 for y in range(h))
text = pathlib.Path(quelle).read_text(encoding="utf-8")
if linien and sys.argv[sys.argv.index("--psm") + 1] == "6":
    text = text.replace(%r, "")
pathlib.Path(basis + ".txt").write_text(text, encoding="utf-8")
""" % POS2

def tabellen_bild(tmp_path):
    """Bild-PDF wie eine Lexware-Rechnung: Positionen mit Linien darüber und darunter."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    puffer, y = BytesIO(), 800
    c = canvas.Canvas(puffer, pagesize=A4)
    for z in LEXWARE.splitlines():
        if z.startswith("2 Patchkabel"):
            c.line(40, y + 11, 555, y + 11)
            c.line(40, y - 4, 555, y - 4)
        c.drawString(50, y, z)
        y -= 15
    c.save()
    p = tmp_path / "tabelle.pdf"
    p.write_bytes(bild_pdf(puffer.getvalue()))
    return p

def test_rueckfall_bild_pdf_mit_linien(tmp_path, ersatz):
    """Echtes Bild mit Tabellenlinien: psm 6 scheitert, die Linienentfernung im Bild rettet die Position."""
    ersatz(LEXWARE)
    (tmp_path / "ersatz.py").write_text(ERSATZ_LINIEN, encoding="utf-8")
    aufruf = [sys.executable, str(tmp_path / "ersatz.py"), str(tmp_path / "quelle.txt")]
    r = lies_rechnung(tabellen_bild(tmp_path), lade_vorlagen(STANDARD), VERKAEUFER,
                      ocr=lambda p: ocr.erkenne(p, tmp_path / "arbeit", aufruf))
    assert (r.ocr_lesart, [p.netto for p in r.positionen]) == ("psm 6 ohne Linien", [D("190.00"), D("10.00")])
    assert list((tmp_path / "arbeit").iterdir()) == []
