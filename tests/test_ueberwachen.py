import json, os, subprocess, sys
from pathlib import Path
import pytest
from facturx import get_xml_from_pdf
from erechnung import __version__
from erechnung.ueberwachen import _frei, lade_konfig, pruefe_ordner, schritt
from hilfen import bild_pdf, pdf_aus_text
from test_vorlagen import TEXT, VORLAGE
REPO = Path(__file__).parents[1]
VERK = {"name": "GM IT Solutions", "strasse": "Musterstraße 1", "plz": "16928", "ort": "Pritzwalk",
        "ust_id": "DE123456789", "iban": "DE02120300000000202051"}
@pytest.fixture
def k(tmp_path):
    for n in ("Eingang", "E-Rechnungen", "Originale", "Fehler", "prog/vorlagen"):
        (tmp_path / n).mkdir(parents=True)
    (tmp_path / "prog/vorlagen/test.yml").write_text(VORLAGE, encoding="utf-8")
    datei = tmp_path / "prog/konfig.json"
    datei.write_text("\ufeff" + json.dumps({"eingang": str(tmp_path / "Eingang"), "ausgabe": str(tmp_path / "E-Rechnungen"),
        "originale": str(tmp_path / "Originale"), "fehler": str(tmp_path / "Fehler"), "verkaeufer": VERK}), encoding="utf-8")
    k = lade_konfig(datei)
    pruefe_ordner(k)
    return k
def drucke(k, text=TEXT, name="rechnung.pdf"):
    (k.eingang / name).write_bytes(pdf_aus_text(text.splitlines()))
def namen(ordner):
    return sorted(p.name for p in ordner.iterdir())
def test_konfig(k):
    assert k.arbeit.name == "arbeit" and k.arbeit.is_dir()
    assert {"test-layout", "lexware-gm-it"} <= {v["name"] for v in k.vorlagen}
def test_konfig_ohne_iban(tmp_path, k):
    d = json.loads((k.arbeit.parent / "konfig.json").read_text(encoding="utf-8-sig"))
    del d["verkaeufer"]["iban"]
    (tmp_path / "k2.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="iban"):
        lade_konfig(tmp_path / "k2.json")
def test_erfolg(k):
    drucke(k)
    assert schritt(k) == 1
    assert namen(k.eingang) == [] and namen(k.arbeit) == []
    assert namen(k.ausgabe) == ["RE9001.pdf", "RE9001.xml"]
    assert len(namen(k.originale)) == 1
    name, xml = get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
    assert xml == (k.ausgabe / "RE9001.xml").read_bytes()
def test_gleiche_nummer_zweimal(k):
    drucke(k)
    schritt(k)
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == ["RE9001-2.pdf", "RE9001-2.xml", "RE9001.pdf", "RE9001.xml"]
def test_summenfehler(k):
    drucke(k, TEXT.replace("Brutto 238,00", "Brutto 239,00"))
    schritt(k)
    assert namen(k.ausgabe) == []
    f = namen(k.fehler)
    grund = next(n for n in f if n.endswith(".fehler.txt"))
    assert len(f) == 2
    assert "Brutto" in (k.fehler / grund).read_text(encoding="utf-8")
def test_unvollstaendig(k):
    (k.eingang / "rechnung.pdf").write_bytes(pdf_aus_text(TEXT.splitlines())[:-200])
    schritt(k)
    assert "unvollständig" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
@pytest.mark.parametrize("name", ["rechnung.pdf", "RE9001 Kopie (2).pdf"])
def test_spooler_schreibt_noch(k, monkeypatch, name):
    """Spooler oder Explorer-Kopie hält die Datei offen → Freigabeverletzung → nächster Takt."""
    drucke(k, name=name)
    echt = os.replace
    def gesperrt(a, b):
        if Path(a).parent == k.eingang:
            raise PermissionError(32, "Sharing violation")
        return echt(a, b)
    monkeypatch.setattr(os, "replace", gesperrt)
    assert schritt(k) == 0
    assert namen(k.eingang) == [name]
def test_verknuepfung_abgelehnt(k, tmp_path):
    os.rmdir(k.ausgabe)
    (tmp_path / "anderswo").mkdir()
    os.symlink(tmp_path / "anderswo", k.ausgabe)
    with pytest.raises(ValueError, match="Verknüpfung"):
        pruefe_ordner(k)
def test_cli_version():
    aus = subprocess.run([sys.executable, "-m", "erechnung", "--version"], capture_output=True, text=True, check=True, cwd=REPO)
    assert aus.stdout.strip() == __version__
def test_cli_umwandeln(k, tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    aus = subprocess.run([sys.executable, "-m", "erechnung", "umwandeln", str(pdf), "--konfig", str(k.arbeit.parent / "konfig.json")],
                         capture_output=True, text=True, cwd=REPO)
    assert aus.returncode == 0, aus.stdout + aus.stderr
    assert (k.ausgabe / "RE9001.xml").exists() and pdf.exists()

def test_beliebige_pdf_namen(k):
    """Senden an / Kopieren: jede *.pdf (auch .PDF, Leerzeichen, Umlaute), andere Dateien bleiben liegen."""
    drucke(k, name="Rechnung für Müller (1).PDF")
    drucke(k, name="zweite.pdf")
    (k.eingang / "notiz.txt").write_text("x", encoding="utf-8")
    assert schritt(k) == 2
    assert namen(k.eingang) == ["notiz.txt"]
    assert namen(k.ausgabe) == ["RE9001-2.pdf", "RE9001-2.xml", "RE9001.pdf", "RE9001.xml"]
    assert len(namen(k.originale)) == 2
def test_gleicher_name_fehler(k):
    for _ in range(2):
        drucke(k, TEXT.replace("Brutto 238,00", "Brutto 239,00"), name="kaputt.pdf")
        schritt(k)
    assert len(namen(k.fehler)) == 4 and namen(k.eingang) == []
def test_frei(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"")
    (tmp_path / "a-2.ocr.txt").write_bytes(b"")
    assert _frei(tmp_path, "b", ".pdf") == "b"
    assert _frei(tmp_path, "a", ".pdf", ".xml", ".ocr.txt") == "a-3"
def test_ocr(k):
    k.ocr = lambda pdf: TEXT
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(TEXT.splitlines())))
    assert schritt(k) == 1
    assert namen(k.ausgabe) == ["RE9001.ocr.txt", "RE9001.pdf", "RE9001.xml"]
    notiz = (k.ausgabe / "RE9001.ocr.txt").read_text(encoding="utf-8")
    assert "per Texterkennung gelesen" in notiz and "Rechnung Nr. RE9001" in notiz
    get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
def test_ocr_summenfehler(k):
    k.ocr = lambda pdf: TEXT.replace("Brutto 238,00", "Brutto 239,00")
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(["x"])))
    schritt(k)
    grund = next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
    assert "Brutto" in grund and "per Texterkennung gelesen" in grund
def test_ohne_tesseract(k):
    k.ocr = None
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(["x"])))
    schritt(k)
    assert "kein Text" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
