# Task 14: Merge, Release 0.2.0, Freigabe, Abnahme auf VM 108

Spezifikation: `docs/lernmodus/spezifikation.md` 6.5, 12. Ablauf Release und Freigabe wie `docs/plan/task-09-release-010.md` und `task-11-freigabe-010.md` (Runbook ai-os `40-wissen/runbooks/release-und-update.md`); VM-Zugang wie `docs/plan/task-10-vm-test-app.md`. Global Constraints in `index.md`.

**Wer:** Hauptsitzung (Merge, Tag), **Marvin** (Freigabe per YubiKey, UAC-Admin-Konto auf der VM bereitstellen), Subagent (VM-Abnahme, meldet nur das Ergebnis).

**Voraussetzungen:** Tasks 01–13 erledigt, Branch `lernmodus` gepusht, alle Tests grün; Task 12 Browserprüfung ohne offene Mängel; Fragen F1–F3 der Spezifikation beantwortet (F1 bestimmt, ob UAC so bleibt).

- [ ] **Step 1: Gesamtprüfung auf gm-claude**
  - `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/ek-wt-lern/tests -q` → alles grün, keine `echt`-Tests übersprungen (Regex-Weg der Lexware-Vorlage unverändert).
  - Secret- und Kundendaten-Prüfung wie `docs/plan/task-09-release-010.md` Step 3, zusätzlich: keine `.pdf` außerhalb `tests/daten/` (`git -C /root/ek-wt-lern ls-files '*.pdf'`).
  - Code-Review des Branches gegen `main` (Skill `superpowers:requesting-code-review` oder `/code-review`), Schwerpunkt Server-Sicherheit (Spezifikation 3.3) und erhöhter Aufruf (4).

- [ ] **Step 2: Merge nach `main`** (Hauptsitzung) – PR auf Forgejo von `lernmodus` nach `main`, CI grün, selbst mergen (Regel „PRs selbst mergen“). Haupt-Klon danach `git -C /root/erechnung-konverter pull`.

- [ ] **Step 3: Tag `v0.2.0`**, Release-Workflow grün, Artefakt prüfen (ZIP enthält `app/erechnung/anlernen/statisch/index.html`, `gm.css`, `fonts/`); danach **Marvin**: Freigabe `v0.2.0` per YubiKey.

- [ ] **Step 4: Testrechnung im fremden Layout auf die VM** – `tests/hilfen_bereiche.py` erzeugt auf gm-claude zwei Muster (`werkstatt_pdf(MUSTER1, SUMMEN1)` und die Variante mit drei Positionen) plus eine dritte Rechnung (vier Positionen, andere Nummer `BW-2026-18`) für den Echtlauf; per bekanntem Weg (Task 10 alt: NetLock/Relay) nach `C:\Users\<testbenutzer>\Desktop\lernmodus\` kopieren.

- [ ] **Step 5: Abnahme VM 108** (Spezifikation 12), Benutzer **ohne** Adminrechte, Ergebnis je Punkt mit Zeit, Beleg (Logzeile/Screenshot) und ok/nicht ok in `docs/testprotokoll.md`, neuer Abschnitt „Lernmodus 0.2.0“:
  1. gm-update hat 0.2.0 installiert (`stand.json`); Startmenü „E-Rechnung anlernen“ vorhanden, öffnet Edge mit der Oberfläche; Taskmanager: `pythonw.exe` läuft als Testbenutzer, nicht als SYSTEM.
  2. Erstes Muster per Dateiauswahl; zweites Muster: dieselbe Rechnung in Edge öffnen und auf „E-Rechnung“ drucken → landet in `Fehler` („keine Vorlage passt“) → in der Oberfläche „Aus Fehler-Ordner übernehmen“ (Bild-PDF, Texterkennung).
  3. Alle Felder und die Tabelle markieren, Probelauf: beide bestanden, Mustang valid; Zeit für den Probelauf notieren.
  4. „Vorlage aktivieren“ → UAC → Admin-Konto (Marvin bzw. vorbereitetes Testkonto) → Meldung aktiv; `protokoll.txt` mit Benutzer, Admin, SHA-256.
  5. Ohne Neustart der Aufgabe: dritte Rechnung als PDF per „Senden an“ und als Edge-Druck → zwei E-Rechnungen in `E-Rechnungen`, `erechnung.log` „Vorlagen neu geladen“, „Mustang: valid“, beim Edge-Druck `.ocr.txt` in `Originale`.
  6. Zweiter Benutzer per schneller Benutzerumschaltung: `Invoke-WebRequest http://127.0.0.1:<port>/api/stand` → 403; `…/start?t=falsch` → 403. Port aus `netstat -ano | findstr 127.0.0.1` beim Testbenutzer.
  7. Oberfläche 30 Minuten unbenutzt → Prozess beendet (oder Leerlauf-Zeit für den Test nicht ändern, sondern Zeitpunkt protokollieren und später prüfen).
  8. Deaktivieren (UAC) → dritte Rechnung erneut drucken → `Fehler` „keine Vorlage passt“; Reaktivieren → wieder E-Rechnung.
  9. Update-Überleben: neue Freigabe (z. B. `v0.2.1` mit Doku-Änderung oder erneute Freigabe laut Runbook) → nach dem Update ist die Vorlage weiter aktiv und wandelt um.
  10. „Für GM IT exportieren“ → ZIP im Download-Ordner mit `vorlage.yml` und Mustern.
  11. Startmenü-Verknüpfung mit `pwsh`-Syntaxprüfung nicht möglich gewesen? Dann hier `einrichten.ps1` einmal erneut als Admin ausführen (wiederholbar, keine Fehler).

- [ ] **Step 6: Nacharbeit** – Gefundene Fehler als Fix-Commits auf einem Branch `lernmodus-fix`, neue Version; Projektstand in ai-os `30-projekte/erechnung-konverter.md` zieht die **Hauptsitzung** nach (nicht der Subagent). Index-Status aller Tasks auf „erledigt (Commit …)“ setzen.

- [ ] **Step 7: Commit Testprotokoll**

```bash
git -C /root/erechnung-konverter add docs/testprotokoll.md docs/lernmodus/plan/index.md
git -C /root/erechnung-konverter commit -m "Lernmodus 0.2.0: Abnahme auf VM 108" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter push origin main
```
