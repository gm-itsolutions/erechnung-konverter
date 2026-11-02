# Task 08: Mustang-Prüfung und Abgleich mit Lexware-XML

Spezifikation: Abschnitt 4.1 (Validierung), 12 (Abnahme 1–2). Global Constraints in `index.md`.

**Entscheidung:** Mustang-CLI läuft auf gm-claude (Java 21 vorhanden: `java -version` → 21.0.12). Die CI prüft nur XSD (factur-x in den Tests). Mustang-Lauf ist Pflicht vor jeder Freigabe (Task 09, 13).

**Files:**
- Create: `werkzeuge/pruefen.sh` (ausführbar), `tests/test_lexware_echt.py`, `tests/test_ende_zu_ende_echt.py`
- Erzeugt (nicht im Repo): `/root/.cache/mustang/Mustang-CLI-<v>.jar`, Prüfberichte unter `/tmp/erechnung-pruefung/`

**Interfaces:**
- Consumes: `lade_konfig`, `pruefe_ordner`, `verarbeite` (Task 05), `betraege` (Task 02), Testdaten (Task 02).
- Produces: `werkzeuge/pruefen.sh <datei.xml>...` → Exit 0 nur, wenn Mustang jede Datei als gültig meldet.

- [ ] **Step 1: Mustang-CLI holen und pinnen**

1. Neueste stabile Version: `curl -fsS https://api.github.com/repos/ZUGFeRD/mustangproject/releases/latest` (Feld `tag_name`, Asset `Mustang-CLI-<v>.jar`).
2. In leeren Ordner laden: `mkdir -p /root/.cache/mustang`, dann `curl -fsSL -o /root/.cache/mustang/Mustang-CLI-<v>.jar <browser_download_url>`.
3. Prüfsumme gegen Maven Central gegenprüfen, falls dort vorhanden (`https://repo1.maven.org/maven2/org/mustangproject/Mustang-CLI/<v>/Mustang-CLI-<v>.jar.sha1` mit `sha1sum`). Fehlt Maven: nur GitHub, im Skript vermerken.
4. SHA-256 berechnen und in `pruefen.sh` eintragen.

- [ ] **Step 2: `werkzeuge/pruefen.sh`**

```sh
#!/bin/sh
# Prüft E-Rechnungs-XML mit Mustang-CLI (XSD + EN16931-Schematron). Nur gm-claude (Java 21).
# Aufruf: werkzeuge/pruefen.sh datei.xml [...]   Bericht je Datei: <datei>.mustang.xml
set -eu
V=MUSTANG_VERSION_HIER                      # aus Step 1
SHA256=MUSTANG_SHA256_HIER                  # aus Step 1
JAR=/root/.cache/mustang/Mustang-CLI-$V.jar
echo "$SHA256  $JAR" | sha256sum -c --quiet -
fehler=0
for f in "$@"; do
  java -Xmx1g -jar "$JAR" --no-notices --action validate --source "$f" > "$f.mustang.xml" 2>&1 || true
  if grep -q 'status="valid"' "$f.mustang.xml"; then
    echo "gültig: $f"
  else
    echo "UNGÜLTIG: $f (Bericht $f.mustang.xml)"
    fehler=1
  fi
done
exit $fehler
```

Die beiden Platzhalter **müssen** in Step 1 ersetzt werden (sonst bricht `sha256sum` ab – gewollt). Prüft Mustang mit `--source` eine XML ohne Rückfrage? Falls die CLI interaktiv nachfragt, Optionen mit `java -jar … --help` nachsehen und ergänzen. Das Ausgabeformat (`status="valid"`) an einer bekannt gültigen Datei prüfen: der Lexware-XML (`/root/erechnung-testdaten/RE0146.lexware.xml`, Kopie nach `/tmp/erechnung-pruefung/`, damit kein Bericht in die Testdaten fällt – oder dort ist er unkritisch, da außerhalb des Repos).

- [ ] **Step 2b: Vorlagen-Test mit echten Daten** – `tests/test_lexware_echt.py`

```python
import os
from pathlib import Path
import pytest
from erechnung.betraege import betraege
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER

DATEN = os.environ.get("ERECHNUNG_TESTDATEN")
pytestmark = [pytest.mark.echt, pytest.mark.skipif(not DATEN, reason="ERECHNUNG_TESTDATEN nicht gesetzt")]

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_wie_lexware(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    steuern = summenabgleich(r)
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert r.nummer == soll["nummer"]
    assert (r.summe_netto, sum(s for _, s in steuern.values()), r.summe_brutto) == (soll["netto"], soll["steuer"], soll["brutto"])
    assert [p.netto for p in r.positionen] == soll["positionen"]
```

Run: `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q` → alle PASS (ohne Variable: echt-Tests SKIPPED).

- [ ] **Step 3: Ende-zu-Ende-Test mit echten Daten** – `tests/test_ende_zu_ende_echt.py`

```python
import json, os, shutil, subprocess
from pathlib import Path
import pytest
from erechnung.betraege import betraege
from erechnung.ueberwachen import lade_konfig, pruefe_ordner, verarbeite

DATEN = os.environ.get("ERECHNUNG_TESTDATEN")
pytestmark = [pytest.mark.echt, pytest.mark.skipif(not DATEN, reason="ERECHNUNG_TESTDATEN nicht gesetzt")]
REPO = Path(__file__).parents[1]

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_wie_lexware_und_mustang(nummer, tmp_path):
    for n in ("ein", "aus", "orig", "fehl", "prog"):
        (tmp_path / n).mkdir()
    konfig = tmp_path / "prog" / "konfig.json"
    konfig.write_text(json.dumps({"eingang": str(tmp_path / "ein"), "ausgabe": str(tmp_path / "aus"),
        "originale": str(tmp_path / "orig"), "fehler": str(tmp_path / "fehl"),
        "verkaeufer": {"name": "GM IT Solutions", "strasse": "Musterstraße 1", "plz": "16928", "ort": "Pritzwalk",
                       "ust_id": "DE123456789", "iban": "DE02120300000000202051"}}), encoding="utf-8")
    k = lade_konfig(konfig)
    pruefe_ordner(k)
    pdf = k.arbeit / f"{nummer}.pdf"
    shutil.copyfile(Path(DATEN) / f"{nummer}.pdf", pdf)
    ergebnis = verarbeite(pdf, k)
    xml = ergebnis.with_suffix(".xml")
    ist, soll = betraege(xml.read_bytes()), betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert ist == soll
    if shutil.which("java"):
        lauf = subprocess.run(["sh", str(REPO / "werkzeuge/pruefen.sh"), str(xml)], capture_output=True, text=True)
        assert lauf.returncode == 0, lauf.stdout + (xml.parent / (xml.name + ".mustang.xml")).read_text()
```

Sonderfall: Ist das Lexware-PDF selbst schon eine ZUGFeRD-Datei (eingebettete XML), kann `bette_ein` scheitern oder die vorhandene XML ersetzen. Dann im Test vor `verarbeite` den Anhang entfernen (nur Test, z. B. mit pypdf `PdfWriter(clone_from=…)` und Entfernen des `/EmbeddedFiles`-Eintrags im `/Names`-Baum) – im echten Betrieb kommen gedruckte PDFs ohne Anhang.

- [ ] **Step 4: Ausführen**

Run: `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q`
Expected: alle PASS, inklusive 3× `test_wie_lexware` und 3× `test_wie_lexware_und_mustang`.

Schlägt Mustang fehl: Bericht lesen, Regel-ID (z. B. `BR-CO-25`, `BR-S-08`) notieren, Ursache in `erechnung/cii.py` beheben (Test in `tests/test_cii.py` ergänzen, der den Fall abdeckt), erneut laufen lassen. Hinweise, die nur PDF/A betreffen, tauchen bei reiner XML-Prüfung nicht auf; eine gemeldete fehlende Leitweg-ID/BT-10 (XRechnung-Regeln BR-DE-*) ist für Profil EN16931 kein Fehler – dann prüfen, ob Mustang als XRechnung statt EN16931 validiert hat, und das in der Rückmeldung nennen.

- [ ] **Step 5: Commit und Push**

```bash
git -C /root/erechnung-konverter add werkzeuge/pruefen.sh tests/test_lexware_echt.py tests/test_ende_zu_ende_echt.py
git -C /root/erechnung-konverter update-index --chmod=+x werkzeuge/pruefen.sh
git -C /root/erechnung-konverter commit -m "Mustang-Prüfung und Ende-zu-Ende-Abgleich mit Lexware" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```

Rückmeldung: je Rechnung „Beträge gleich / Mustang gültig“, nur Nummern und Nettobeträge, keine Kundennamen.
