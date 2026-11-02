# Task 01: Vorlagenformat `art: bereiche`, Schema, Laden

Spezifikation: `docs/lernmodus/spezifikation.md` Abschnitt 5. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/bereiche.py` (nur Schema-Teil), `tests/test_bereiche_schema.py`, `tests/daten/bereiche-beispiel.yml`
- Modify: `erechnung/vorlagen.py` (`_pruefe`, `lade_vorlagen`)

**Interfaces:**
- Consumes: `vorlagen.VorlagenFehler`, `vorlagen._pruefe(v, datei)`, `lade_vorlagen(*ordner)`.
- Produces: `bereiche.BereichsFehler(ValueError)`, `FORMAT = 1`, `PFLICHT_FELDER`, `FELDER`, `SPALTEN`, `pruefe_bereichsvorlage(v: dict) -> dict`; `vorlagen.MAX_BYTES = 65536`; `lade_vorlagen(*ordner, tolerant: bool = False)` (tolerant: ungültige Datei → `log.warning`, überspringen).

- [ ] **Step 1: Beispielvorlage** – `tests/daten/bereiche-beispiel.yml`. Die Koordinaten passen zum synthetischen Muster aus Task 02 (`tests/hilfen_bereiche.py`, Layout dort beschrieben: Text-Oberkante bei `y`; Wertrahmen von `y - 0.002` bis `y + 0.016`, Ankerrahmen = Umriss der Ankerwörter (linke obere Ecke = Oberkante des ersten Ankerworts, daran misst `finde_anker` die Verschiebung); Muster 1 hat zwei Positionen plus eine Fortsetzungszeile, die Summen beginnen bei y = 0.345).

```yaml
name: test-bereiche
art: bereiche
format: 1
schluesselwoerter: ["Beispiel Werkstatt", "Belegnummer"]
angelernt: {am: "2026-11-02", muster: 2}
felder:
  nummer: {seite: erste, rahmen: [0.68, 0.148, 0.95, 0.166], anker: {text: "Belegnummer", rahmen: [0.50, 0.150, 0.60, 0.162]}}
  datum: {seite: erste, rahmen: [0.68, 0.168, 0.95, 0.186], anker: {text: "Belegdatum", rahmen: [0.50, 0.170, 0.59, 0.182]}}
  zahlungsziel_tage: {seite: erste, rahmen: [0.68, 0.188, 0.95, 0.206], anker: {text: "Zahlbar in", rahmen: [0.50, 0.190, 0.58, 0.202]}}
  kaeufer: {seite: erste, rahmen: [0.07, 0.146, 0.45, 0.206]}
  summe_netto: {seite: letzte, rahmen: [0.75, 0.343, 0.95, 0.361], anker: {text: "Summe netto", rahmen: [0.50, 0.345, 0.60, 0.357]}}
  summe_brutto: {seite: letzte, rahmen: [0.75, 0.383, 0.95, 0.401], anker: {text: "Endbetrag", rahmen: [0.50, 0.385, 0.58, 0.397]}}
steuern:
  seite: letzte
  anker: {text: "MwSt. {satz} %", rahmen: [0.50, 0.365, 0.60, 0.377]}
  rahmen: [0.75, 0.363, 0.95, 0.381]
positionen:
  kopf: {text: "Nr Leistung Anzahl", rahmen: [0.08, 0.250, 0.562, 0.262]}
  ende: {text: "Summe netto", rahmen: [0.50, 0.345, 0.60, 0.357]}
  unten: 0.92
  links: 0.07
  spalten:
    - {bis: 0.13, art: nr}
    - {bis: 0.50, art: bezeichnung}
    - {bis: 0.60, art: menge_einheit}
    - {bis: 0.75, art: einzelpreis}
    - {bis: 0.95, art: netto}
  ust_satz: 19
einheiten: {Std: HUR, Stk: H87}
```

- [ ] **Step 2: Failing tests** – `tests/test_bereiche_schema.py`

```python
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
    pruefe_bereichsvorlage(v)
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
```

- [ ] **Step 3: Tests laufen lassen, FAIL erwartet** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_bereiche_schema.py -q` (ImportError).

- [ ] **Step 4: Schema implementieren** – `erechnung/bereiche.py`

```python
"""Angelernte Vorlagen: Felder per Rahmen und Anker, keine Regex (docs/lernmodus/spezifikation.md 5, 6)."""
import re
FORMAT = 1
PFLICHT_FELDER = ("nummer", "datum", "summe_netto", "summe_brutto", "kaeufer")
FELDER = (*PFLICHT_FELDER, "nummer_kontrolle", "leistungsdatum", "faellig", "zahlungsziel_tage", "summe_ust", "nachlass")
SPALTEN = ("nr", "bezeichnung", "menge", "einheit", "menge_einheit", "einzelpreis", "ust_satz", "netto", "ignorieren")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,39}")
class BereichsFehler(ValueError):
    pass
def _ja(bedingung, meldung: str) -> None:
    if not bedingung:
        raise BereichsFehler(meldung)
def _schluessel(d, erlaubt: set, wo: str) -> None:
    _ja(isinstance(d, dict), f"{wo}: Abschnitt fehlt")
    fremd = set(d) - erlaubt
    _ja(not fremd, f"{wo}: unbekannt: {', '.join(sorted(map(str, fremd)))}")
def _zahl(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1
def _rahmen(r, wo: str) -> None:
    _ja(isinstance(r, list) and len(r) == 4 and all(map(_zahl, r)) and r[0] < r[2] and r[1] < r[3],
        f"{wo}: rahmen braucht [x0, y0, x1, y1] in 0..1 mit x0 < x1, y0 < y1")
def _text(t, wo: str, mini=1, maxi=80) -> None:
    _ja(isinstance(t, str) and mini <= len(t) <= maxi, f"{wo}: Text mit {mini}–{maxi} Zeichen nötig")
def _anker(a, wo: str, platzhalter: bool = False) -> None:
    _schluessel(a, {"text", "rahmen"}, f"{wo}.anker")
    _text(a.get("text"), f"{wo}.anker")
    _ja(a["text"].count("{satz}") <= (1 if platzhalter else 0), f"{wo}.anker: {{satz}} nicht erlaubt")
    _rahmen(a.get("rahmen"), f"{wo}.anker")
def _satz(x, wo: str) -> None:
    _ja(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x <= 30, f"{wo}: ust_satz/satz muss 0 < x ≤ 30 sein")
def _feld(f, wo: str) -> None:
    _schluessel(f, {"seite", "rahmen", "anker"}, wo)
    _ja(f.get("seite") in ("erste", "letzte"), f"{wo}: seite muss erste oder letzte sein")
    _rahmen(f.get("rahmen"), wo)
    if "anker" in f:
        _anker(f["anker"], wo)
def pruefe_bereichsvorlage(v: dict) -> dict:
    _schluessel(v, {"name", "art", "format", "schluesselwoerter", "angelernt", "felder", "steuern", "positionen", "einheiten"}, "Vorlage")
    _ja(isinstance(v.get("name"), str) and NAME.fullmatch(v["name"]), "name: nur a-z, 0-9, -, 2–40 Zeichen")
    _ja(v.get("format") == FORMAT, f"format muss {FORMAT} sein")
    sw = v.get("schluesselwoerter")
    _ja(isinstance(sw, list) and 1 <= len(sw) <= 5, "schluesselwoerter: 1–5 Texte")
    for s in sw:
        _text(s, "schluesselwoerter", 3, 80)
    if "angelernt" in v:
        _schluessel(v["angelernt"], {"am", "muster"}, "angelernt")
    felder = v.get("felder")
    _schluessel(felder, set(FELDER), "felder")
    for n in PFLICHT_FELDER:
        _ja(n in felder, f"felder: {n} fehlt")
    for n, f in felder.items():
        _feld(f, f"felder.{n}")
    if "steuern" in v:
        s = v["steuern"]
        _schluessel(s, {"seite", "anker", "rahmen", "satz"}, "steuern")
        _ja("anker" in s, "steuern: anker fehlt")
        _feld({k: s[k] for k in ("seite", "rahmen") if k in s}, "steuern")
        _anker(s["anker"], "steuern", platzhalter=True)
        if "{satz}" not in s["anker"]["text"]:
            _ja("satz" in s, "steuern: ohne {satz} im Anker ist satz Pflicht")
            _satz(s["satz"], "steuern")
    p = v.get("positionen")
    _schluessel(p, {"kopf", "ende", "unten", "links", "spalten", "ust_satz"}, "positionen")
    _anker(p.get("kopf"), "positionen.kopf")
    if "ende" in p:
        _anker(p["ende"], "positionen.ende")
    _ja(_zahl(p.get("unten")) and _zahl(p.get("links")), "positionen: unten und links in 0..1")
    sp = p.get("spalten")
    _ja(isinstance(sp, list) and 2 <= len(sp) <= 12, "positionen.spalten: 2–12 Spalten")
    for s in sp:
        _schluessel(s, {"bis", "art"}, "positionen.spalten")
        _ja(s.get("art") in SPALTEN, f"positionen.spalten: art {s.get('art')!r} unbekannt")
        _ja(_zahl(s.get("bis")), "positionen.spalten: bis in 0..1")
    grenzen = [p["links"], *(s["bis"] for s in sp)]
    _ja(all(a < b for a, b in zip(grenzen, grenzen[1:])), "positionen.spalten: bis streng steigend, links davor")
    arten = [s["art"] for s in sp]
    _ja(arten.count("bezeichnung") == 1, "positionen.spalten: genau eine bezeichnung")
    _ja(arten.count("netto") == 1, "positionen.spalten: genau eine netto")
    _ja(arten.count("menge") + arten.count("menge_einheit") <= 1, "positionen.spalten: höchstens eine menge/menge_einheit")
    if "ust_satz" in p:
        _satz(p["ust_satz"], "positionen.ust_satz")
    e = v.get("einheiten", {})
    _ja(isinstance(e, dict) and len(e) <= 50 and all(isinstance(k, str) and 1 <= len(k) <= 20 and isinstance(w, str)
        and re.fullmatch(r"[A-Z0-9]{2,3}", w) for k, w in e.items()), "einheiten: höchstens 50, Code wie HUR")
    return v
```

Die Meldung für `links` (Test „links“) entsteht über „bis streng steigend, links davor“ – passt auf `match="links"`.

- [ ] **Step 5: `vorlagen.py` anpassen**

```python
import logging
from .bereiche import BereichsFehler, pruefe_bereichsvorlage
log = logging.getLogger("erechnung")
MAX_BYTES = 64 * 1024
def _pruefe(v: dict, datei: Path) -> dict:
    if v.get("art") == "bereiche":
        try:
            return pruefe_bereichsvorlage(v)
        except BereichsFehler as e:
            raise VorlagenFehler(f"Vorlage {datei.name}: {e}") from None
    ...  # bisheriger Regex-Teil unverändert
def lade_vorlagen(*ordner: Path, tolerant: bool = False) -> list[dict]:
    vorlagen = []
    for o in ordner:
        if o.is_dir():
            for datei in sorted(o.glob("*.yml")):
                try:
                    if datei.stat().st_size > MAX_BYTES:
                        raise VorlagenFehler(f"Vorlage {datei.name}: zu groß (höchstens {MAX_BYTES} Byte)")
                    vorlagen.append(_pruefe(yaml.safe_load(datei.read_text(encoding="utf-8")) or {}, datei))
                except (VorlagenFehler, yaml.YAMLError, UnicodeDecodeError) as e:
                    if not tolerant:
                        raise VorlagenFehler(str(e)) from None
                    log.warning("Vorlage übersprungen: %s: %s", datei, e)
    return vorlagen
```

Namenskonflikte (mitgeliefert gewinnt) regelt Task 06, nicht hier.

- [ ] **Step 6: Alle Tests** – `/root/.venvs/erechnung/bin/python -m pytest -q` → alles grün (bestehende `test_vorlagen.py` unverändert).

- [ ] **Step 7: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/bereiche.py erechnung/vorlagen.py tests/test_bereiche_schema.py tests/daten/bereiche-beispiel.yml
git -C /root/ek-wt-lern commit -m "Lernmodus: Vorlagenformat bereiche mit Schema-Prüfung" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
