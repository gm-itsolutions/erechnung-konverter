# Task 13: Vorlage mit gedruckten PDFs verfeinern, `v0.1.1`

Spezifikation: Abschnitt 3.2, 5. Global Constraints in `index.md`.

**Wer:** Subagent (Vorlage, Tests); Tag durch die Hauptsitzung oder den Subagenten nach grünem Mustang.

**Hintergrund:** Ein über „Microsoft Print to PDF“ gedrucktes PDF hat oft eine andere Textreihenfolge, andere Leerzeichen oder Ligaturen als das Lexware-Original. Die Vorlage aus Task 04 ist nur am Original geprüft.

**Eingaben:** `/root/erechnung-testdaten/vm/*gedruckt*.pdf` aus Task 10 (SumatraPDF) und – sobald vorhanden – ein von Marvin aus einem normalen Programm gedrucktes PDF (Frage im Bericht). Gibt es kein gedrucktes PDF mit Text: Task nur mit den Erkenntnissen aus Task 10 abschließen (Protokoll) und `v0.1.1` trotzdem aus dem aktuellen `main` taggen, damit Task 14 den Update-Weg prüfen kann.

**Files:**
- Modify: `erechnung/vorlagen/lexware-gm-it.yml`, `tests/test_lexware_echt.py` (zusätzliche Parameter), ggf. `tests/daten/lexware-synthetisch-gedruckt.txt` + Test in `tests/test_vorlagen.py`

- [ ] **Step 1: Text der gedruckten PDFs ansehen**

```bash
/root/.venvs/erechnung/bin/python -c "import sys; from erechnung.vorlagen import pdf_text; from pathlib import Path; print(pdf_text(Path(sys.argv[1])))" /root/erechnung-testdaten/vm/RE0146-gedruckt-sumatra.pdf
```
(cwd `/root/erechnung-konverter`). Mit `RE0146.txt` vergleichen (`diff`), Unterschiede notieren.

- [ ] **Step 2: Failing test** – `tests/test_lexware_echt.py` um die gedruckten Varianten erweitern:

```python
@pytest.mark.parametrize("datei,nummer", [
    (p.name, p.name.split("-")[0]) for p in sorted(Path(DATEN or ".").glob("vm/*-gedruckt-*.pdf"))])
def test_gedruckt_wie_lexware(datei, nummer):
    r = lies_rechnung(Path(DATEN) / "vm" / datei, lade_vorlagen(STANDARD), VERKAEUFER)
    steuern = summenabgleich(r)
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert (r.nummer, r.summe_netto, sum(s for _, s in steuern.values()), r.summe_brutto) == \
           (soll["nummer"], soll["netto"], soll["steuer"], soll["brutto"])
```
Run: `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_lexware_echt.py -q` → neue Fälle FAIL (oder PASS, dann ist nichts zu tun).

- [ ] **Step 3: Vorlage anpassen**, bis Original **und** gedruckte Variante passen. Regexe toleranter machen (`\s+` statt fester Leerzeichen, optionale `€`, getrennte Zeilen für Beträge), nicht eine zweite Vorlage für dasselbe Layout anlegen (würde „mehrere Vorlagen“ auslösen). Zeigt der Druck strukturell anderen Text (Spalten vertauscht), `layout: true` prüfen.

- [ ] **Step 4: Synthetische Variante** – entspricht der gedruckte Text nicht mehr `tests/daten/lexware-synthetisch.txt`, eine anonymisierte Kopie als `lexware-synthetisch-gedruckt.txt` mit Test analog `test_lexware_synthetisch` ergänzen (Regeln aus Task 04 Step 6: keine echten Kundendaten).

- [ ] **Step 5: Alles grün inkl. Mustang** – `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q`

- [ ] **Step 6: Commit, Push, Tag**

```bash
git -C /root/erechnung-konverter add erechnung/vorlagen/lexware-gm-it.yml tests
git -C /root/erechnung-konverter commit -m "Vorlage lexware-gm-it für gedruckte PDFs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
CI grün abwarten, dann Task 09 Steps 3–7 sinngemäß für `v0.1.1` (Tag, Release-Workflow, Artefakt prüfen, Cockpit-Punkt „Freigabe erechnung-konverter 0.1.1“).
