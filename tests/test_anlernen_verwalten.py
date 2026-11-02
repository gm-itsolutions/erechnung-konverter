import hashlib, json
from pathlib import Path
import pytest, yaml
from erechnung.anlernen import verwalten
from erechnung.anlernen.verwalten import aktivieren, deaktivieren, exportieren, loeschen, probelauf, reaktivieren
from erechnung.bereiche import pruefe_bereichsvorlage
from erechnung.ueberwachen import lade_alle_vorlagen, lade_konfig
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
BEISPIEL = (Path(__file__).parent / "daten" / "bereiche-beispiel.yml").read_text(encoding="utf-8")
def _konfig_datei(tmp_path) -> Path:
    for o in ("Eingang", "E-Rechnungen", "Originale", "Fehler"):
        (tmp_path / o).mkdir(exist_ok=True)
    konfig = tmp_path / "prog" / "konfig.json"
    konfig.parent.mkdir(exist_ok=True)
    konfig.write_text(json.dumps({"eingang": str(tmp_path / "Eingang"), "ausgabe": str(tmp_path / "E-Rechnungen"),
        "originale": str(tmp_path / "Originale"), "fehler": str(tmp_path / "Fehler"), "verkaeufer": VERKAEUFER.__dict__}), encoding="utf-8")
    return konfig
def _entwurf(ordner: Path) -> Path:
    (ordner / "muster").mkdir(parents=True)
    (ordner / "vorlage.json").write_text(json.dumps(yaml.safe_load(BEISPIEL)), encoding="utf-8")
    (ordner / "muster" / "m1.pdf").write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
    (ordner / "muster" / "m2.pdf").write_bytes(werkstatt_pdf(MUSTER1 + [("3", "Filter", "1 Stk", "10,00", "10,00")],
                                                           ("250,00", "47,50", "297,50"), dx=0.01, dy=0.02))
    return ordner
@pytest.fixture
def umgebung(tmp_path):
    konfig = _konfig_datei(tmp_path)
    (tmp_path / "arbeit").mkdir()
    k = lade_konfig(konfig, arbeit=tmp_path / "arbeit")
    k.pruefe = lambda xml: "valid (Test)"
    return _entwurf(tmp_path / "entwurf" / "test-bereiche"), k, konfig
def test_probelauf_gruen(umgebung):
    e, k, _ = umgebung
    p = probelauf(e, k)
    assert p["vorlage_fehler"] is None and p["bereit"] is True
    assert [m["ok"] for m in p["muster"]] == [True, True]
    assert p["muster"][1]["werte"]["summe_brutto"] == "297,50" and p["muster"][0]["mustang"] == "valid (Test)"
    assert "nummer" in p["muster"][0]["spur"]
def test_probelauf_summenfehler(umgebung):
    e, k, _ = umgebung
    (e / "muster" / "m2.pdf").write_bytes(werkstatt_pdf(MUSTER1, ("240,00", "45,60", "299,99")))
    p = probelauf(e, k)
    assert p["bereit"] is False and "Brutto" in p["muster"][1]["fehler"]
def test_probelauf_ein_muster_nicht_bereit(umgebung):
    e, k, _ = umgebung
    (e / "muster" / "m2.pdf").unlink()
    assert probelauf(e, k)["bereit"] is False
def test_probelauf_konflikt(umgebung):
    e, k, konfig = umgebung
    ziel = konfig.parent / "vorlagen" / "angelernt"
    ziel.mkdir(parents=True)
    (ziel / "andere.yml").write_text(BEISPIEL.replace("name: test-bereiche", "name: andere"), encoding="utf-8")
    k.vorlagen = lade_alle_vorlagen([ziel])
    p = probelauf(e, k)
    assert p["bereit"] is False and "mehrere Vorlagen" in p["muster"][0]["fehler"]
def test_probelauf_schema(umgebung):
    e, k, _ = umgebung
    v = json.loads((e / "vorlage.json").read_text(encoding="utf-8"))
    del v["felder"]["kaeufer"]
    (e / "vorlage.json").write_text(json.dumps(v), encoding="utf-8")
    assert "kaeufer" in probelauf(e, k)["vorlage_fehler"]
def test_aktivieren_protokoll_und_ersetzen(umgebung, monkeypatch):
    e, k, konfig = umgebung
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)     # Mustang-Ersatz auch im „erhöhten“ Lauf
    assert aktivieren(e, konfig, "kasse")["ok"] is True
    datei = konfig.parent / "vorlagen" / "angelernt" / "test-bereiche.yml"
    assert pruefe_bereichsvorlage(yaml.safe_load(datei.read_text(encoding="utf-8")))["name"] == "test-bereiche"
    zeile = (datei.parent / "protokoll.txt").read_text(encoding="utf-8").splitlines()[-1]
    assert "aktiviert" in zeile and "kasse" in zeile and hashlib.sha256(datei.read_bytes()).hexdigest() in zeile
    assert aktivieren(e, konfig, "kasse")["ok"] is True
    assert len(list((datei.parent / "deaktiviert").glob("test-bereiche-*.yml"))) == 1
def test_aktivieren_prueft_selbst(umgebung, monkeypatch):
    e, k, konfig = umgebung
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    (e / "muster" / "m2.pdf").write_bytes(werkstatt_pdf(MUSTER1, ("240,00", "45,60", "299,99")))
    r = aktivieren(e, konfig, "kasse")
    assert r["ok"] is False and not (konfig.parent / "vorlagen" / "angelernt" / "test-bereiche.yml").exists()
def test_aktivieren_mitgelieferter_name(umgebung, monkeypatch):
    e, k, konfig = umgebung
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    v = json.loads((e / "vorlage.json").read_text(encoding="utf-8"))
    v["name"] = "lexware-gm-it"
    (e / "vorlage.json").write_text(json.dumps(v), encoding="utf-8")
    assert "mitgeliefert" in aktivieren(e, konfig, "kasse")["meldung"]
def test_deaktivieren_reaktivieren_loeschen(umgebung, monkeypatch):
    e, k, konfig = umgebung
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    aktivieren(e, konfig, "kasse")
    a = konfig.parent / "vorlagen" / "angelernt"
    assert deaktivieren("test-bereiche", konfig, "kasse")["ok"] and (a / "deaktiviert" / "test-bereiche.yml").exists()
    assert reaktivieren("test-bereiche", konfig, "kasse")["ok"] and (a / "test-bereiche.yml").exists()
    assert loeschen("test-bereiche", konfig, "kasse")["ok"] and not (a / "test-bereiche.yml").exists()
    assert deaktivieren("../x", konfig, "kasse")["ok"] is False
def test_export(umgebung, tmp_path):
    e, _, _ = umgebung
    ziel = tmp_path / "export"
    ziel.mkdir()
    z = exportieren(e, ziel)   # F2: nur die Vorlage, keine Muster-PDFs
    assert z.name.startswith("erechnung-vorlage-test-bereiche-") and z.suffix == ".yml"
    assert [p.name for p in ziel.iterdir()] == [z.name]
    v = yaml.safe_load(z.read_text(encoding="utf-8"))
    pruefe_bereichsvorlage(v)
    assert "%PDF" not in z.read_text(encoding="utf-8")
def test_probelauf_ersetzt_gleichnamige(umgebung, monkeypatch):
    e, k, konfig = umgebung       # W4: aktive gleichnamige Vorlage stört den Probelauf nicht (Ersetzen, Spec 7.4)
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    assert aktivieren(e, konfig, "kasse")["ok"] is True
    k.vorlagen = lade_alle_vorlagen(k.vorlagen_ordner)
    assert "test-bereiche" in [v["name"] for v in k.vorlagen]
    assert probelauf(e, k)["bereit"] is True
def test_probelauf_mitgelieferter_name(umgebung):
    e, k, _ = umgebung            # W4: Namenskollision schon im Probelauf, vor der UAC-Abfrage
    v = json.loads((e / "vorlage.json").read_text(encoding="utf-8"))
    v["name"] = "lexware-gm-it"
    (e / "vorlage.json").write_text(json.dumps(v), encoding="utf-8")
    p = probelauf(e, k)
    assert p["bereit"] is False and "mitgeliefert" in p["vorlage_fehler"]
def test_verwalten_unbekannt_und_geraet(umgebung):
    _, _, konfig = umgebung       # W17
    r = deaktivieren("gibt-es-nicht", konfig, "kasse")
    assert r["ok"] is False and "nicht gefunden" in r["meldung"]
    assert loeschen("con", konfig, "kasse")["ok"] is False
    assert reaktivieren("gibt-es-nicht", konfig, "kasse")["ok"] is False
def test_probelauf_legt_arbeitsordner_an(umgebung):
    e, k, _ = umgebung            # erhöhter Lauf: Arbeitsordner kann fehlen
    k.arbeit.rmdir()
    assert probelauf(e, k)["bereit"] is True
