import json, os, subprocess, sys
from pathlib import Path
import pytest
from facturx import get_xml_from_pdf
from erechnung import __version__
from erechnung.ueberwachen import lade_konfig, pruefe_ordner, schritt
from hilfen import pdf_aus_text
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
def test_spooler_schreibt_noch(k, monkeypatch):
    drucke(k)
    echt = os.replace
    def gesperrt(a, b):
        if Path(a).parent == k.eingang:
            raise PermissionError(32, "Sharing violation")
        return echt(a, b)
    monkeypatch.setattr(os, "replace", gesperrt)
    assert schritt(k) == 0
    assert namen(k.eingang) == ["rechnung.pdf"]
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
