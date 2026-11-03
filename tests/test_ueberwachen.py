import json, os, subprocess, sys
from pathlib import Path
import pytest
from facturx import get_xml_from_pdf
from erechnung import __version__, mustang
from erechnung.ueberwachen import _frei, lade_konfig, pruefe_ordner, schritt
from hilfen import bild_pdf, pdf_aus_text
from test_vorlagen import TEXT, VORLAGE
REPO = Path(__file__).parents[1]
VERK = {"name": "GM IT Solutions", "strasse": "Musterstraße 1", "plz": "16928", "ort": "Pritzwalk",
        "ust_id": "DE123456789", "iban": "DE02120300000000202051"}
def konfig_datei(tmp_path, **extra):
    datei = tmp_path / "prog/konfig.json"
    datei.write_text("\ufeff" + json.dumps({"eingang": str(tmp_path / "Eingang"), "ausgabe": str(tmp_path / "E-Rechnungen"),
        "originale": str(tmp_path / "Originale"), "fehler": str(tmp_path / "Fehler"), "verkaeufer": VERK, **extra}), encoding="utf-8")
    return datei
@pytest.fixture
def k(tmp_path):
    for n in ("Eingang", "E-Rechnungen", "Originale", "Fehler", "prog/vorlagen"):
        (tmp_path / n).mkdir(parents=True)
    (tmp_path / "prog/vorlagen/test.yml").write_text(VORLAGE, encoding="utf-8")
    k = lade_konfig(konfig_datei(tmp_path))
    pruefe_ordner(k)
    k.geprueft = []
    def pruefe(xml):  # ersetzt Mustang; prüft, dass die fertige XML übergeben wird
        k.geprueft.append(xml.read_bytes())
        return "valid (Test)"
    k.pruefe = pruefe
    return k
def drucke(k, text=TEXT, name="rechnung.pdf"):
    (k.eingang / name).write_bytes(pdf_aus_text(text.splitlines()))
def namen(ordner):
    return sorted(p.name for p in ordner.iterdir())
def test_konfig(k):
    assert k.arbeit.name == "arbeit" and k.arbeit.is_dir()
    assert {"test-layout", "lexware-gm-it"} <= {v["name"] for v in k.vorlagen}
    assert k.xml_einzeln is False
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
    assert namen(k.ausgabe) == ["RE9001.pdf"]
    assert len(namen(k.originale)) == 1
    name, xml = get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
    assert k.geprueft == [xml]
def test_xml_einzeln(tmp_path, k):
    """konfig.json "xml_einzeln": true (Behörden, XRechnung) → zusätzlich <Nummer>.xml."""
    pruefe = k.pruefe
    k = lade_konfig(konfig_datei(tmp_path, xml_einzeln=True))
    k.pruefe = pruefe
    assert k.xml_einzeln is True
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == ["RE9001.pdf", "RE9001.xml"]
    name, xml = get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
    assert xml == (k.ausgabe / "RE9001.xml").read_bytes()
def test_mustang_ungueltig(k):
    def ungueltig(xml):
        raise ValueError("E-Rechnung laut Mustang ungültig:\nBR-CO-15: Invoice total amount with VAT")
    k.pruefe = ungueltig
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == [] and namen(k.arbeit) == [] and namen(k.originale) == []
    assert "BR-CO-15" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
def test_ohne_mustang(k):
    k.pruefe = None
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == [] and namen(k.arbeit) == []
    assert "Mustang" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
def test_pruefbericht_im_log(k, caplog):
    caplog.set_level("INFO", logger="erechnung")
    drucke(k)
    schritt(k)
    assert "Mustang: valid (Test)" in caplog.text
def test_gleiche_nummer_zweimal(k):
    drucke(k)
    schritt(k)
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == ["RE9001-2.pdf", "RE9001.pdf"]
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
    """Eigener Prozess, also echte Mustang-Prüfung; ohne java/Mustang-CLI muss es ein Fehler sein, keine E-Rechnung."""
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    aus = subprocess.run([sys.executable, "-m", "erechnung", "umwandeln", str(pdf), "--konfig", str(k.arbeit.parent / "konfig.json")],
                         capture_output=True, text=True, cwd=REPO)
    assert pdf.exists()
    if mustang.mustang():
        assert aus.returncode == 0, aus.stdout + aus.stderr
        assert namen(k.ausgabe) == ["RE9001.pdf"]
        assert "Mustang: valid" in (k.arbeit.parent / "erechnung.log").read_text(encoding="utf-8")
    else:
        assert aus.returncode == 1 and "Mustang" in aus.stdout and namen(k.ausgabe) == []

def test_beliebige_pdf_namen(k):
    """Senden an / Kopieren: jede *.pdf (auch .PDF, Leerzeichen, Umlaute), andere Dateien bleiben liegen."""
    drucke(k, name="Rechnung für Müller (1).PDF")
    drucke(k, name="zweite.pdf")
    (k.eingang / "notiz.txt").write_text("x", encoding="utf-8")
    assert schritt(k) == 2
    assert namen(k.eingang) == ["notiz.txt"]
    assert namen(k.ausgabe) == ["RE9001-2.pdf", "RE9001.pdf"]
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
def test_ocr(k, caplog):
    """OCR-Vermerk neben das Original in Originale und ins Log, nicht in den Ausgabeordner."""
    caplog.set_level("INFO", logger="erechnung")
    k.ocr = lambda pdf: [("psm 6", TEXT)]
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(TEXT.splitlines())))
    assert schritt(k) == 1
    assert namen(k.ausgabe) == ["RE9001.pdf"]
    orig = namen(k.originale)
    assert len(orig) == 2 and orig[0].endswith("-edge.ocr.txt") and orig[1].endswith("-edge.pdf")
    notiz = (k.originale / orig[0]).read_text(encoding="utf-8")
    assert "per Texterkennung gelesen" in notiz and "Lesart psm 6" in notiz and "Rechnung Nr. RE9001" in notiz and "RE9001" in notiz.splitlines()[0]
    assert "Rechnung Nr. RE9001" in caplog.text
    get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
def test_ocr_summenfehler(k):
    k.ocr = lambda pdf: [("psm 6", TEXT.replace("Brutto 238,00", "Brutto 239,00"))]
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(["x"])))
    schritt(k)
    grund = next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
    assert "Brutto" in grund and "per Texterkennung gelesen" in grund
def test_ohne_tesseract(k):
    k.ocr = None
    (k.eingang / "edge.pdf").write_bytes(bild_pdf(pdf_aus_text(["x"])))
    schritt(k)
    assert "kein Text" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")

FREMD = ["Muster Handel GmbH", "Weg 1, 12345 Teststadt", "", "Rechnung Nr. FR-2026-7", "Rechnungsdatum: 03.11.2026", "",
         "Kunde: Beispiel Handel GmbH", "Hauptstraße 5", "19348 Perleberg", "",
         "Pos Bezeichnung Menge Einzelpreis Betrag", "1 Beratung 2,00 50,00 100,00",
         "Nettosumme 100,00 EUR", "19% USt 19,00 EUR", "Gesamtbetrag 119,00 EUR"]

def test_fehler_mit_vorschlag(k):
    drucke(k, "\n".join(FREMD))
    schritt(k)
    txt = next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
    assert "keine Vorlage passt" in txt and "Vorschlag der generischen Erkennung (nicht verwendet)" in txt
    assert "FR-2026-7" in txt and "119,00 EUR" in txt and "bestätigt: ja" in txt
    assert len(list(k.fehler.glob("*.pdf"))) == 1 and namen(k.ausgabe) == []

def test_vorschlag_ohne_text(k):
    drucke(k, " ")
    schritt(k)
    txt = next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
    assert "kein Vorschlag" in txt

def test_vorschlag_text_zu_lang(k, monkeypatch):
    from erechnung import ueberwachen
    monkeypatch.setattr(ueberwachen, "pdf_text", lambda p: "wort " * 30_000)
    assert "kein Vorschlag: Text zu lang" in ueberwachen.vorschlag_text(Path("x.pdf"))

def test_vorschlag_kaputt_stoert_nicht(k, monkeypatch):
    def kaputt(*a, **kw):
        raise RuntimeError("kaputt")
    monkeypatch.setattr("erechnung.generisch.vorschlag_aus_pdf", kaputt)
    drucke(k, "\n".join(FREMD))
    schritt(k)
    txt = next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
    assert "keine Vorlage passt" in txt and "Vorschlag" not in txt
    assert len(list(k.fehler.glob("*.pdf"))) == 1

def test_cli_vorschlag(tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(pdf_aus_text(FREMD))
    aus = subprocess.run([sys.executable, "-m", "erechnung", "vorschlag", str(pdf)], capture_output=True, text=True, cwd=REPO)
    d = json.loads(aus.stdout)
    assert aus.returncode == 0 and d["nummer"] == "FR-2026-7" and d["summe_brutto"] == "119.00" and d["bestaetigt"] is True
    leer = tmp_path / "leer.pdf"
    leer.write_bytes(pdf_aus_text(["Hallo"]))
    aus = subprocess.run([sys.executable, "-m", "erechnung", "vorschlag", str(leer)], capture_output=True, text=True, cwd=REPO)
    assert aus.returncode == 1 and json.loads(aus.stdout)["bestaetigt"] is False

def test_andere_vorlagenfehler_ohne_vorschlag(k, monkeypatch):
    from erechnung.vorlagen import VorlagenFehler
    def mehrere(*a, **kw):
        raise VorlagenFehler("mehrere Vorlagen: a, b")
    monkeypatch.setattr("erechnung.ueberwachen.lies_rechnung", mehrere)
    drucke(k, "\n".join(FREMD))
    schritt(k)
    assert next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8") == "mehrere Vorlagen: a, b\n"
