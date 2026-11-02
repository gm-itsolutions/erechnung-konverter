# Task 12: VM 108 – Erstinstallation über gm-update

Spezifikation: Abschnitt 9, 12 (Punkt 3–4). Steuerweg, DNS und Dateiübertragung wie `task-10-vm-test-app.md` Abschnitt „Steuerweg“. Global Constraints in `index.md`.

**Wer:** Subagent. **Voraussetzung:** Task 10 (Einrichtung auf der VM) und Task 11 (Marvin hat `0.1.0` freigegeben).

**Ziel:** Die von Hand gelegte Version ist weg; gm-update lädt die freigegebene `0.1.0` selbst, prüft Signatur und Prüfsumme, legt `versionen\0.1.0` und `aktuell` an, startet den Überwacher. Danach wird wieder eine E-Rechnung erzeugt.

- [ ] **Step 1: hosts-Eintrag** für `git.gm-itsolutions.de` wie in Task 10 (Original sichern).

- [ ] **Step 2: Handinstallation entfernen**

```powershell
$p = "$env:ProgramFiles\GM-IT\erechnung-konverter"
Stop-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung'
cmd /c rmdir "$p\aktuell"
Remove-Item -Recurse -Force "$p\versionen\0.1.0"
Remove-Item -Force "$p\stand.json" -ErrorAction SilentlyContinue
```
(Jede Zeile als eigener `qm guest exec`-Aufruf oder als ein EncodedCommand-Skript – innerhalb von PowerShell sind mehrere Zeilen erlaubt.)

- [ ] **Step 3: Update-Lauf auslösen** – `Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'Update erechnung-konverter'`; Aufgabe hat bis 60 Min. Zufallsverzögerung nur beim Zeitauslöser, nicht beim Handstart. Warten bis `(Get-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'Update erechnung-konverter').State` wieder `Ready` ist (Abfrage alle 15 s, höchstens 10 Min.).

- [ ] **Step 4: Prüfen**
  - `Get-Content "$p\stand.json"` → `"version": "0.1.0"`, `fehler` leer.
  - `Get-Content "$p\gm-update.log" -Tail 5` → „aktualisiert auf 0.1.0“ o. ä.
  - `(Get-Item "$p\aktuell").Target` → `…\versionen\0.1.0`.
  - `Get-Process pythonw` läuft (gm-update hat `start` ausgeführt).
  - `icacls "$p\gm-update.json"` und `"$p\token"` → nur SYSTEM und Administratoren.

- [ ] **Step 5: Funktion** – `RE0148.pdf` (in Teilen übertragen, wie Task 10) nach `C:\E-Rechnung\Eingang` → `E-Rechnungen\RE0148.pdf/.xml` (bei Namensgleichheit aus Task 10: `RE0148-2.*`). Ein `Out-Printer`-Test → Fehlerpaar „keine Vorlage passt“.

- [ ] **Step 6: Aufräumen** – hosts zurück, übertragene Dateien in `C:\gm-setup` löschen.

- [ ] **Step 7: Protokoll** – Abschnitt „VM 108, 0.1.0 über gm-update“ in `docs/testprotokoll.md`, Commit `Testprotokoll VM 108: Erstinstallation über gm-update` (mit Co-Authored-By-Zeile), `pull --rebase`, Push.

**Scheitert der Lauf:** `stand.json`/`gm-update.log` lesen, mit den Fehlerbildern im ai-os-Runbook `release-und-update.md` abgleichen (z. B. HTTP 401 → Token/Team, `freigabe ungültig` → nicht übergehen, Hauptsitzung informieren). Die App dann wie in Task 10 Step 4 von Hand legen, damit der Termin nicht gefährdet ist, und den Fehler als Blocker melden.
