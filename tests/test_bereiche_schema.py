import copy
from pathlib import Path
import pytest, yaml
from erechnung.bereiche import BereichsFehler, pruefe_bereichsvorlage
from erechnung.vorlagen import VorlagenFehler, lade_vorlagen, STANDARD
DATEI = Path(__file__).parent / "daten" / "bereiche-beispiel.yml"
def gut(): return yaml.safe_load(DATEI.read_text(encoding="utf-8"))
def test_beispiel_gueltig():
    assert pruefe_bereichsvorlage(gut())["name"] == "test-bereiche"
@pytest.mark.parametrize("aendern, meldung", [
    (lambda v: v.update(name="A b"), "name"),
    (lambda v: v.update(format=2), "format"),
    (lambda v: v.update(unbekannt=1), "unbekannt"),
    (lambda v: v["felder"].pop("kaeufer"), "kaeufer"),
    (lambda v: v["felder"].update(xyz={"seite": "erste", "rahmen": [0, 0, 1, 1]}), "xyz"),
    (lambda v: v["felder"]["nummer"].update(rahmen=[0.5, 0.1, 0.4, 0.2]), "rahmen"),
    (lambda v: v["felder"]["nummer"].update(rahmen=[0, 0, 1.2, 1]), "rahmen"),
    (lambda v: v["felder"]["nummer"].update(seite="mitte"), "seite"),
    (lambda v: v["felder"]["nummer"]["anker"].update(text="x" * 81), "anker"),
    (lambda v: v["felder"]["nummer"]["anker"].update(text="Nr {satz}"), "{satz}"),
    (lambda v: v.update(schluesselwoerter=[]), "schluesselwoerter"),
    (lambda v: v.update(schluesselwoerter=["ab"]), "schluesselwoerter"),
    (lambda v: v["positionen"]["spalten"].reverse(), "bis"),
    (lambda v: v["positionen"]["spalten"].append({"bis": 0.99, "art": "netto"}), "netto"),
    (lambda v: v["positionen"]["spalten"][0].update(art="eval"), "art"),
    (lambda v: v["positionen"].update(links=0.5), "links"),
    (lambda v: v.update(einheiten={"Std": "hur"}), "einheiten"),
    (lambda v: v["positionen"].update(ust_satz=99), "ust_satz"),
    (lambda v: v["steuern"]["anker"].update(text="MwSt. {satz} {satz}"), "{satz}"),
    (lambda v: v["steuern"].pop("anker"), "steuern"),
    (lambda v: v["positionen"].update(spalten=v["positionen"]["spalten"][:1]), "Spalten"),
    (lambda v: v["positionen"]["spalten"].__setitem__(1, {"bis": 0.50, "art": "ignorieren"}), "bezeichnung"),
    (lambda v: v["positionen"]["spalten"].insert(2, {"bis": 0.55, "art": "menge"}), "menge"),
    (lambda v: v.update(einheiten={f"e{i}": "HUR" for i in range(51)}), "einheiten"),
    (lambda v: v.update(einheiten={"x" * 21: "HUR"}), "einheiten"),
    (lambda v: v["steuern"]["anker"].update(text="MwSt."), "satz"),
    (lambda v: v["steuern"].update(anker={"text": "MwSt.", "rahmen": [0.5, 0.3, 0.6, 0.4]}, satz=31), "satz"),
    (lambda v: v.update(angelernt={"am": "x", "foo": 1}), "angelernt"),
    (lambda v: v["felder"]["nummer"]["anker"].update(text=""), "anker"),
])
def test_verletzungen(aendern, meldung):
    v = gut()
    aendern(v)
    with pytest.raises(BereichsFehler, match=meldung.replace("{", r"\{").replace("}", r"\}")):
        pruefe_bereichsvorlage(v)
def test_steuern_ohne_platzhalter_braucht_satz():
    v = gut()
    v["steuern"]["anker"]["text"] = "MwSt."
    with pytest.raises(BereichsFehler, match="satz"):
        pruefe_bereichsvorlage(v)
    v["steuern"]["satz"] = 19
    assert pruefe_bereichsvorlage(v)["steuern"]["satz"] == 19
def test_laden_neben_lexware(tmp_path):
    (tmp_path / "x.yml").write_text(DATEI.read_text(encoding="utf-8"), encoding="utf-8")
    namen = [v["name"] for v in lade_vorlagen(STANDARD, tmp_path)]
    assert namen == ["lexware-gm-it", "test-bereiche"]
def test_zu_gross(tmp_path):
    (tmp_path / "x.yml").write_text("name: x\n" + "#" * 70000, encoding="utf-8")
    with pytest.raises(VorlagenFehler, match="zu groß"):
        lade_vorlagen(tmp_path)
def test_tolerant_ueberspringt(tmp_path, caplog):
    (tmp_path / "a.yml").write_text("name: kaputt\nart: bereiche\n", encoding="utf-8")
    (tmp_path / "b.yml").write_text(DATEI.read_text(encoding="utf-8"), encoding="utf-8")
    assert [v["name"] for v in lade_vorlagen(tmp_path, tolerant=True)] == ["test-bereiche"]
    assert "a.yml" in caplog.text
