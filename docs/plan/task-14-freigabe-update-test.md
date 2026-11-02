# Task 14: Freigabe `v0.1.1` (Marvin) und Update-Test auf VM 108

Spezifikation: Abschnitt 9, 12 (Punkt 5). Global Constraints in `index.md`.

**Voraussetzung:** Task 12 (VM hat `0.1.0` über gm-update), Task 13 (`v0.1.1` in der Paketablage).

## Teil A – Marvin

Wie `task-11-freigabe-010.md`, Version **0.1.1**. Auf der Detailseite zusätzlich prüfen: „Commits seit“ zeigt nur die Commits nach `v0.1.0` (Vorlage, Protokolle).

## Teil B – Subagent

Steuerweg wie `task-10-vm-test-app.md`.

- [ ] **Step 1:** hosts-Eintrag setzen (Original sichern).
- [ ] **Step 2:** `Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'Update erechnung-konverter'`, warten bis `Ready`.
- [ ] **Step 3: Prüfen**
  - `stand.json`: `version` `0.1.1`, `vorige` `0.1.0`, `fehler` leer.
  - `gm-update.log`: Probe vorher, Stopp, Umstellen, Start, Probe nachher.
  - `(Get-Item "$env:ProgramFiles\GM-IT\erechnung-konverter\aktuell").Target` → `versionen\0.1.1`; `versionen\` enthält `0.1.0` und `0.1.1`.
  - `Get-Process pythonw` läuft; Startzeit nach dem Update (`(Get-Process pythonw).StartTime`).
- [ ] **Step 4: Funktion** – Lexware-PDF in den Eingang → E-Rechnung; falls Task 13 eine gedruckte Variante erschlossen hat, diese ebenfalls drucken bzw. einlegen.
- [ ] **Step 5:** hosts zurück, übertragene Dateien löschen. Protokollabschnitt „VM 108, Update 0.1.0 → 0.1.1“ in `docs/testprotokoll.md`, Commit (mit Co-Authored-By-Zeile), `pull --rebase`, Push.
- [ ] **Step 6:** Status aller Tasks in `docs/plan/index.md` nachziehen und pushen. Der Hauptsitzung melden: Durchstich fertig, offene Punkte (Spezifikation Abschnitt 11) und Befunde aus den VM-Tests.
