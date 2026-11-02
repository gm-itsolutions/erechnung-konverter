# Task 09: Probelauf, Aktivieren, Verwalten, Export (Logik)

Spezifikation: `docs/lernmodus/spezifikation.md` 4, 7.3, 7.4, 10, 11 (F1: alles Verwalten per UAC; F2: Export nur `vorlage.yml`). Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/anlernen/verwalten.py`, `tests/test_anlernen_verwalten.py`

**Interfaces:**
- Consumes: Task 01 `pruefe_bereichsvorlage`, `vorlagen.MAX_BYTES`, `STANDARD`, `lade_vorlagen`; Task 02 `woerter_aus_pdf`; Task 04 `rechnung_aus_bereichen`, `positionen_aus_bereichen`; Task 05 `Konfig.ocr` → `(text, seiten)`; Task 06 `lade_konfig(datei, arbeit)`, `lade_alle_vorlagen`, `ANGELERNT`; Task 07 `NAME`; `modell.summenabgleich`, `modell.de`, `cii.erzeuge_cii`, `vorlagen.finde_vorlage`, `vorlagen.pdf_text`, `vorlagen.MIN_ZEICHEN`, `Konfig.pruefe` (Mustang, XML-Pfad → Kurzbericht, `ValueError` wenn ungültig).
- Produces:
  - `MIN_MUSTER = 2`
  - `probelauf(entwurf: Path, k: Konfig) -> dict` → `{"vorlage_fehler": str|None, "muster": [{"id", "ok", "fehler", "werte", "positionen", "ignoriert", "spur", "mustang"}], "bereit": bool}`
  - `aktivieren(entwurf: Path, konfig: Path, benutzer: str) -> dict`, `deaktivieren/reaktivieren/loeschen(name, konfig, benutzer) -> dict` (alle `{"ok": bool, "meldung": str}`)
  - `exportieren(entwurf: Path, ziel: Path) -> Path` (nur `vorlage.yml`, keine Muster)
  - Testhilfen `_konfig_datei(tmp_path)`, `_entwurf(ordner)`, `BEISPIEL` (Task 10 importiert sie)

- [ ] **Step 1: Failing tests** – `tests/test_anlernen_verwalten.py`

```python
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
    z = exportieren(e, tmp_path)   # F2: nur die Vorlage, keine Muster-PDFs
    assert z.name.startswith("erechnung-vorlage-test-bereiche-") and z.suffix == ".yml"
    assert [p.name for p in tmp_path.iterdir()] == [z.name]
    v = yaml.safe_load(z.read_text(encoding="utf-8"))
    pruefe_bereichsvorlage(v)
    assert "%PDF" not in z.read_text(encoding="utf-8")
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_anlernen_verwalten.py -q`

- [ ] **Step 3: `verwalten.py`** – Kernpunkte (vollständig ausschreiben):

```python
MIN_MUSTER = 2
def _konfig(konfig: Path, arbeit: Path):            # in Tests ersetzbar
    return lade_konfig(konfig, arbeit=arbeit)
def _muster(entwurf: Path) -> list[Path]:
    return sorted((entwurf / "muster").glob("m*.pdf"), key=lambda p: int(p.stem[1:]))
def _ein_muster(pdf: Path, v: dict, k) -> dict:
    erg = {"id": pdf.stem, "ok": False, "fehler": None, "werte": {}, "positionen": [], "ignoriert": [], "spur": {}, "mustang": None}
    try:
        text = pdf_text(pdf)
        ocr = len(re.findall(r"\w", text)) < MIN_ZEICHEN
        if ocr:
            if not k.ocr:
                raise ValueError("kein Text im PDF, Texterkennung nicht verfügbar")
            text, seiten = k.ocr(pdf)
        else:
            seiten = woerter_aus_pdf(pdf)
        treffer = finde_vorlage(text, [*k.vorlagen, v])   # wirft bei „keine“ und „mehrere Vorlagen“
        if treffer is not v:
            raise ValueError(f"Muster passt zur Vorlage {treffer['name']}, nicht zu dieser")
        r = rechnung_aus_bereichen(seiten, v, k.verkaeufer, ocr=ocr, spur=erg["spur"])
        erg["werte"] = {"nummer": r.nummer, "datum": f"{r.datum:%d.%m.%Y}", "faellig": f"{r.faellig:%d.%m.%Y}" if r.faellig else "",
                        "kaeufer": " / ".join(filter(None, (r.kaeufer.name, r.kaeufer.strasse, f"{r.kaeufer.plz} {r.kaeufer.ort}"))),
                        "summe_netto": de(r.summe_netto), "summe_brutto": de(r.summe_brutto),
                        "steuern": {str(s): de(b) for s, b in r.steuern.items()}}
        erg["positionen"] = [[p.nr, p.bezeichnung, str(p.menge), p.einheit, de(p.einzelpreis), str(p.ust_satz), de(p.netto)] for p in r.positionen]
        erg["ignoriert"] = positionen_aus_bereichen(seiten, v, ocr)[1]
        xml = erzeuge_cii(r, summenabgleich(r))
        if not k.pruefe:
            raise ValueError("Mustang-Prüfung nicht verfügbar")
        datei = k.arbeit / f"probe-{pdf.stem}.xml"
        datei.write_bytes(xml)
        try:
            erg["mustang"] = k.pruefe(datei)
        finally:
            datei.unlink(missing_ok=True)
        erg["ok"] = True
    except ValueError as e:
        erg["fehler"] = str(e)
    return erg
def probelauf(entwurf: Path, k) -> dict:
    v = json.loads((entwurf / "vorlage.json").read_text(encoding="utf-8"))
    try:
        pruefe_bereichsvorlage(v)
    except ValueError as e:
        return {"vorlage_fehler": str(e), "muster": [], "bereit": False}
    muster = [_ein_muster(p, v, k) for p in _muster(entwurf)]
    return {"vorlage_fehler": None, "muster": muster, "bereit": len(muster) >= MIN_MUSTER and all(m["ok"] for m in muster)}
```

`aktivieren(entwurf, konfig, benutzer)`: `angelernt = konfig.parent / "vorlagen" / ANGELERNT`, `angelernt/"deaktiviert"` anlegen; `k = _konfig(konfig, arbeit=konfig.parent / "arbeit")` (Admin darf dort schreiben); `k.vorlagen` ohne eine schon aktive gleichnamige Vorlage (Ersetzen ist erlaubt); Name in `lade_vorlagen(STANDARD)` oder `konfig.parent/"vorlagen"` → `{"ok": False, "meldung": "Name … ist mitgeliefert"}`; `p = probelauf(entwurf, k)`; nicht `bereit` → `{"ok": False, "meldung": <erster Fehler>}`. Sonst `v["angelernt"] = {"am": date.today().isoformat(), "muster": len(p["muster"])}`, `text = yaml.safe_dump(v, allow_unicode=True, sort_keys=False)`, Größe ≤ `MAX_BYTES`, nochmals `pruefe_bereichsvorlage(yaml.safe_load(text))`; vorhandene Datei nach `deaktiviert/<name>-<YYYYmmdd-HHMMSS>.yml` (`os.replace`); `<name>.yml.tmp` schreiben, `os.replace` auf `<name>.yml`; Protokoll.

Protokoll `_protokoll(angelernt, aktion, name, benutzer, datei=None, muster=0)`: eine Zeile, Tabulator-getrennt: ISO-Zeit, `benutzer=<Oberflächen-Benutzer>`, `admin=<os.environ USERDOMAIN\USERNAME>`, Aktion, Name, `sha256=<…>` (falls Datei), `muster=<n>`. Öffnen mit `"a"`, UTF-8.

`deaktivieren`: `<name>.yml` → `deaktiviert/<name>.yml` (vorhandenes Ziel vorher mit Stempel umbenennen); `reaktivieren`: zurück, vorher `pruefe_bereichsvorlage`; `loeschen`: aktive oder deaktivierte Datei löschen (gestempelte Altstände bleiben). Jeder Name zuerst gegen `NAME.fullmatch` (sonst `ok False`). Alle drei protokollieren.

`exportieren(entwurf, ziel)`: **nur** `erechnung-vorlage-<name>-<YYYY-MM-DD>.yml` in `ziel` (`yaml.safe_dump` des Entwurfs, vorher `pruefe_bereichsvorlage`); keine Muster-PDFs, keine `.png`, keine `.woerter.json`, kein ZIP (F2).

- [ ] **Step 4: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 4b: Probelauf mit fremden Layouts (nur gm-claude)** – Entwurf mit `/root/erechnung-testdaten/fremd/E-1.pdf` und `E-2.pdf` als Muster (Vorlage von Hand oder aus Task 04): `probelauf` bestanden, Summen gleich `E-<n>.soll.json` (Nachlass), Käufer ist der Rechnungsempfänger, nicht die Lieferanschrift. Gegenprobe: Muster `F-1.pdf` (§ 19 UStG) → `bereit` False mit verständlichem Fehler. Ergebnis im Commit vermerken.

- [ ] **Step 5: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen/verwalten.py tests/test_anlernen_verwalten.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Probelauf mit Summenabgleich und Mustang, Aktivieren mit eigener Prüfung, Export" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
