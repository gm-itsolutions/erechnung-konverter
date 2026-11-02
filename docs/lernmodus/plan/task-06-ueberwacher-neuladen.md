# Task 06: Überwacher – Ordner `angelernt`, tolerant laden, ohne Neustart neu laden

Spezifikation: `docs/lernmodus/spezifikation.md` 4 (Überwacher lädt ohne Neustart), 5 (Namensgleichheit). Global Constraints in `index.md`.

**Files:**
- Modify: `erechnung/ueberwachen.py`, `tests/test_ueberwachen.py` (nur neue Tests anhängen), `docs/einrichten.md` (Abschnitt „4. Neue Vorlage ohne Release“)

**Interfaces:**
- Consumes: `vorlagen.lade_vorlagen(*ordner, tolerant=False)` (Task 01), `vorlagen.STANDARD`.
- Produces:
  - `ANGELERNT = "angelernt"`
  - `lade_konfig(datei: Path, arbeit: Path | None = None) -> Konfig` (`arbeit` ersetzt `<konfig-ordner>\arbeit`, für die Oberfläche im Benutzerkontext, Task 07 und 09)
  - `Konfig.vorlagen_ordner: list[Path]` (= `[<konfig>\vorlagen, <konfig>\vorlagen\angelernt]`), `Konfig.vorlagen_stand: tuple`
  - `vorlagen_stand(ordner: list[Path]) -> tuple`
  - `lade_alle_vorlagen(ordner: list[Path]) -> list[dict]` (mitgeliefert streng, Zusatzordner tolerant, Namensgleichheit: mitgeliefert gewinnt)
  - `aktualisiere_vorlagen(k: Konfig) -> bool` (in `schritt()` vor der Verarbeitung)

- [ ] **Step 1: Failing tests** – an `tests/test_ueberwachen.py` anhängen (Fixture `k` und Hilfen der Datei benutzen; vorher `grep -n "def k\b\|def k(" tests/test_ueberwachen.py` lesen, wie `k` gebaut wird, und `vorlagen_ordner` dort auf zwei `tmp_path`-Ordner setzen)

```python
import os, shutil
from erechnung.ueberwachen import aktualisiere_vorlagen, lade_alle_vorlagen, vorlagen_stand
BEISPIEL = Path(__file__).parent / "daten" / "bereiche-beispiel.yml"
def test_lade_alle_tolerant(tmp_path, caplog):
    zusatz, angelernt = tmp_path / "vorlagen", tmp_path / "vorlagen" / "angelernt"
    angelernt.mkdir(parents=True)
    shutil.copy(BEISPIEL, angelernt / "test-bereiche.yml")
    (angelernt / "kaputt.yml").write_text("name: x\nart: bereiche\n", encoding="utf-8")
    namen = [v["name"] for v in lade_alle_vorlagen([zusatz, angelernt])]
    assert namen == ["lexware-gm-it", "test-bereiche"] and "kaputt.yml" in caplog.text
def test_mitgeliefert_gewinnt(tmp_path, caplog):
    angelernt = tmp_path / "angelernt"
    angelernt.mkdir()
    (angelernt / "lexware-gm-it.yml").write_text(
        BEISPIEL.read_text(encoding="utf-8").replace("name: test-bereiche", "name: lexware-gm-it"), encoding="utf-8")
    assert [v["name"] for v in lade_alle_vorlagen([angelernt])] == ["lexware-gm-it"]
    assert "gleichnamig" in caplog.text
def test_neuladen_im_takt(k, tmp_path):
    angelernt = tmp_path / "neu-angelernt"
    angelernt.mkdir()
    k.vorlagen_ordner = [angelernt]
    k.vorlagen_stand = vorlagen_stand(k.vorlagen_ordner)
    assert aktualisiere_vorlagen(k) is False
    shutil.copy(BEISPIEL, angelernt / "test-bereiche.yml")
    assert aktualisiere_vorlagen(k) is True
    assert "test-bereiche" in [v["name"] for v in k.vorlagen]
    (angelernt / "test-bereiche.yml").unlink()
    assert aktualisiere_vorlagen(k) is True
    assert "test-bereiche" not in [v["name"] for v in k.vorlagen]
def test_kaputte_mitgelieferte_behaelt_alte(k, monkeypatch, caplog):
    alt = list(k.vorlagen)
    k.vorlagen_stand = ("geändert",)
    monkeypatch.setattr("erechnung.ueberwachen.lade_alle_vorlagen", lambda o: (_ for _ in ()).throw(ValueError("kaputt")))
    assert aktualisiere_vorlagen(k) is False and k.vorlagen == alt and "kaputt" in caplog.text
def test_lade_konfig_arbeit(tmp_path, konfig_datei):
    k = lade_konfig(konfig_datei, arbeit=tmp_path / "eigene-arbeit")
    assert k.arbeit == tmp_path / "eigene-arbeit"
    assert k.vorlagen_ordner == [konfig_datei.parent / "vorlagen", konfig_datei.parent / "vorlagen" / "angelernt"]
```

`konfig_datei`: Gibt es in `test_ueberwachen.py` schon eine Fixture, die eine `konfig.json` schreibt, diese nehmen; sonst hier eine kleine Fixture anlegen, die `konfig.json` mit `VERKAEUFER`-Daten (aus `hilfen`) und vier `tmp_path`-Ordnern schreibt.

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_ueberwachen.py -q`

- [ ] **Step 3: Implementieren** – `erechnung/ueberwachen.py`

```python
ANGELERNT = "angelernt"
@dataclass
class Konfig:
    ...  # bisherige Felder unverändert
    vorlagen_ordner: list[Path] = field(default_factory=list)   # Zusatz und angelernt, im Takt geprüft
    vorlagen_stand: tuple = ()
def vorlagen_stand(ordner: list[Path]) -> tuple:
    return tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size)
                 for o in ordner if o.is_dir() for f in sorted(o.glob("*.yml")))
def lade_alle_vorlagen(ordner: list[Path]) -> list[dict]:
    """Mitgelieferte streng (Paketfehler → Abbruch), Zusatz/angelernt tolerant; bei gleichem Namen gewinnt die mitgelieferte."""
    vorlagen = lade_vorlagen(STANDARD)
    namen = {v["name"] for v in vorlagen}
    for v in lade_vorlagen(*ordner, tolerant=True):
        if v["name"] in namen:
            log.warning("Vorlage %s übersprungen: gleichnamige Vorlage ist mitgeliefert bzw. schon geladen", v["name"])
            continue
        namen.add(v["name"])
        vorlagen.append(v)
    return vorlagen
def aktualisiere_vorlagen(k: Konfig) -> bool:
    stand = vorlagen_stand(k.vorlagen_ordner)
    if stand == k.vorlagen_stand:
        return False
    try:
        neu = lade_alle_vorlagen(k.vorlagen_ordner)
    except Exception as e:                      # alte Vorlagen behalten, nächster Takt versucht es nicht erneut
        log.error("Vorlagen nicht neu geladen, bisherige bleiben aktiv: %s", e)
        k.vorlagen_stand = stand
        return False
    k.vorlagen, k.vorlagen_stand = neu, stand
    log.info("Vorlagen neu geladen: %s", ", ".join(v["name"] for v in neu))
    return True
```

In `lade_konfig(datei, arbeit=None)`: `arbeit = arbeit or datei.parent / "arbeit"`, `ordner = [datei.parent / "vorlagen", datei.parent / "vorlagen" / ANGELERNT]`, `vorlagen=lade_alle_vorlagen(ordner)`, `vorlagen_ordner=ordner`, `vorlagen_stand=vorlagen_stand(ordner)`. In `schritt(k)` als erste Zeile `aktualisiere_vorlagen(k)`. `from dataclasses import dataclass, field`.

Der Test `test_kaputte_mitgelieferte_behaelt_alte` erwartet `False` und unveränderte Vorlagen; danach ist der Stand gemerkt, damit der Fehler nicht jeden Takt (0,5 s) ins Log läuft.

Hinweis: Bestehende Tests, die `Konfig(...)` direkt bauen, funktionieren weiter (neue Felder haben Standardwerte, `vorlagen_ordner=[]` → `vorlagen_stand == ()` → kein Neuladen).

- [ ] **Step 4: Runbook** – `docs/einrichten.md` Abschnitt „4. Neue Vorlage ohne Release“: Die beiden Zeilen `Stop-/Start-ScheduledTask` entfallen; Satz ergänzen: „Der Überwacher lädt Vorlagen in `vorlagen\` und `vorlagen\angelernt\` binnen einer Sekunde neu (Logzeile ‚Vorlagen neu geladen‘). Eine fehlerhafte Datei wird mit Warnung übersprungen.“

- [ ] **Step 5: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/ueberwachen.py tests/test_ueberwachen.py docs/einrichten.md
git -C /root/ek-wt-lern commit -m "Lernmodus: Überwacher lädt angelernte Vorlagen ohne Neustart" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
