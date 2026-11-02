# Task 10: VM 108 – Einrichtung und Druck ohne Freigabe

Spezifikation: Abschnitt 3, 6, 12 (Punkt 4). Global Constraints in `index.md`. Steuerweg und Labor-Eigenheiten: ai-os `40-wissen/netlock-rmm.md` (Abschnitt „Grenzen der API“, Punkte zu `qm guest exec`, `systemd-run`, `pvesh … agent/file-write`) und ai-os `30-projekte/gm-update.md` Abschnitt „Ergebnis 02.11.2026“ (DNS, hosts-Eintrag). Beides **nur lesen**.

**Wer:** Subagent. **Ziel:** Auf VM 108 (sspr-srv2, Windows Server 2025) läuft die App aus dem Release-ZIP `0.1.0`; ein in den Eingang gelegtes Lexware-PDF wird zur E-Rechnung, ein Druck auf „E-Rechnung“ kommt im Überwacher an. gm-update ist eingerichtet, findet aber noch keine Freigabe (die kommt mit Task 11).

**Ergebnis-Datei:** `docs/testprotokoll.md` (Abschnitt „VM 108, 0.1.0, ohne Freigabe“): je Prüfpunkt bestanden/nicht bestanden, Befehl, gekürzte Ausgabe. Keine Kundennamen, kein Token.

## Steuerweg (Kurzfassung)

- NetLock `run-command` auf dem Proxmox-Host (gm-pve-02) → `qm guest exec 108 --synchronous 0 -- powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand <UTF-16LE-base64>`, Ergebnis mit `qm guest exec-status 108 <pid>`. `run-command` bricht nach 1 Min. ab → Längeres per `systemd-run --unit <name> --collect /bin/bash -c '…> log 2>&1'`.
- Dateien in die VM: `pvesh create /nodes/$(hostname)/qemu/108/agent/file-write --file 'C:\…' --content "$(base64 -w0 datei)" --encode 0`. **Grenze:** ein Argument höchstens ca. 128 KB → größere Dateien (PDFs) in base64-Teilen zu 60 KB als `C:\gm-setup\teil-NN.b64` schreiben, in der VM zusammensetzen: `[IO.File]::WriteAllBytes($ziel, [Convert]::FromBase64String((Get-Content C:\gm-setup\teil-*.b64 -Raw) -join ''))` (Reihenfolge über zweistellige Nummern).
- VM aus? Start per `systemd-run … qm start 108`. Meldet `qm start` „no quorum“: **abbrechen**, Cockpit-Punkt für Marvin (`pvecm expected 1` braucht seine Freigabe) – nicht selbst setzen.
- DNS: VM 108 hat ohne VM 105 kein DNS. Vorher `C:\Windows\System32\drivers\etc\hosts` nach `C:\gm-setup\hosts.orig` sichern, Eintrag für `git.gm-itsolutions.de` (IP auf gm-claude mit `getent hosts git.gm-itsolutions.de`) ergänzen; am Ende Original zurückspielen.
- Das Test-Token `update-test` (nur `read:package`) darf für das Labor über diesen Weg in die VM; Kunden-Tokens nie.

## Schritte

- [ ] **Step 1: Setup-Ordner `C:\gm-setup` füllen** – `einrichten.ps1`, `gm-update.json` (aus `git -C /root/erechnung-konverter show v0.1.0:einrichten/…`), `token` (Inhalt von `/root/.config/gm-it-os/update-test.token`), `konfig.json` (Beispiel mit Testwerten: Name „GM IT Solutions (Test)“, USt-IdNr. `DE123456789`, IBAN `DE02120300000000202051`). `gm-update.exe` 0.1.3 lädt die VM selbst: `Invoke-WebRequest -Headers @{Authorization = "token $(Get-Content C:\gm-setup\token)"} -Uri https://git.gm-itsolutions.de/api/packages/gm-itsolutions/generic/gm-update/0.1.3/gm-update-0.1.3-windows-amd64.exe -OutFile C:\gm-setup\gm-update.exe`, dann `Get-FileHash` gegen die `sha256` aus `…/gm-update/0.1.3/release.json`.

- [ ] **Step 2: PowerShell-Syntax prüfen** – `[System.Management.Automation.Language.Parser]::ParseFile('C:\gm-setup\einrichten.ps1', [ref]$null, [ref]$f); $f` → keine Fehler. Fehler: im Repo beheben (Task-07-Datei), committen, Tag `v0.1.1` ist dafür **nicht** nötig, solange nur `einrichten.ps1` betroffen ist – die VM nutzt die korrigierte Datei direkt; im Protokoll vermerken.

- [ ] **Step 3: Einrichten** – `cd C:\gm-setup; .\einrichten.ps1 -TokenDatei .\token -Konfig .\konfig.json` (als SYSTEM über guest exec; `#Requires -RunAsAdministrator` ist erfüllt). Expected: Warnung „gm-update installieren endete mit 1“ (HTTP 404, keine Freigabe), danach Drucker, Port, Aufgaben, Ordner angelegt, Warnung „Noch keine App-Version installiert“. Prüfen: `Get-Printer E-Rechnung | fl Name,DriverName,PortName`, `Get-ScheduledTask -TaskPath '\GM-IT\'`, `icacls C:\E-Rechnung`, `icacls C:\E-Rechnung\Eingang`, `icacls "$env:ProgramFiles\GM-IT\erechnung-konverter\token"` (nur SYSTEM/Admins).

- [ ] **Step 4: App von Hand aus dem Release legen (nur Labor, bis Task 11)** – ZIP `…/generic/erechnung-konverter/0.1.0/erechnung-konverter-0.1.0-windows-amd64.zip` mit Token laden, SHA-256 gegen `release.json` prüfen, `Expand-Archive` nach `%ProgramFiles%\GM-IT\erechnung-konverter\versionen\0.1.0`, `cmd /c mklink /J "%ProgramFiles%\GM-IT\erechnung-konverter\aktuell" "%ProgramFiles%\GM-IT\erechnung-konverter\versionen\0.1.0"`.
  - Probe wie gm-update: `& "$env:ProgramFiles\GM-IT\erechnung-konverter\aktuell\python\python.exe" -m erechnung --version` → `0.1.0`, Exit 0, Dauer messen (< 60 s).
  - `Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung'`, nach 10 s `Get-Process pythonw`, Log `erechnung.log` → „Überwachung gestartet“.

- [ ] **Step 5: Eingang direkt** – `RE0146.pdf` (aus `/root/erechnung-testdaten`, in Teilen übertragen) nach `C:\E-Rechnung\Eingang\` kopieren. Nach 10 s: `C:\E-Rechnung\E-Rechnungen\RE0146.pdf` und `.xml` vorhanden, Original in `Originale`. XML zurückholen (`[Convert]::ToBase64String([IO.File]::ReadAllBytes(…))` in der Ausgabe von `exec-status`), lokal nach `/root/erechnung-testdaten/vm/RE0146.xml`, mit `betraege()` gegen `RE0146.lexware.xml` vergleichen und mit `werkzeuge/pruefen.sh` prüfen. Danach RE0148 und RE0149 genauso.

- [ ] **Step 6: Druckweg** (als SYSTEM)
  1. `"Testseite E-Rechnung" | Out-Printer -Name 'E-Rechnung'` → nach 10 s liegt in `Fehler\` ein PDF mit `.fehler.txt` „keine Vorlage passt“ (Beleg: Port, Spooler, Verschieben, Fehlerweg; Text im PDF vorhanden).
  2. Fünf Aufträge direkt hintereinander (`1..5 | % { "Auftrag $_" | Out-Printer -Name 'E-Rechnung' }`) → genau 5 Fehlerpaare. Weniger = Überschreiben passiert → Protokoll, Risiko an Hauptsitzung.
  3. PDF drucken: SumatraPDF portable (offizielle Download-Seite, Host per `getent hosts` auf gm-claude auflösen und befristet in die hosts-Datei; nur auf der VM) → `SumatraPDF.exe -print-to "E-Rechnung" -silent C:\gm-setup\RE0146.pdf`. Ergebnis notieren: E-Rechnung entstanden, oder Fehler „kein Text“ (SumatraPDF druckt gerastert) bzw. Vorlagenfehler (Text anders als im Original). Das gedruckte PDF (aus `Fehler\` oder `Originale\`) nach `/root/erechnung-testdaten/vm/RE0146-gedruckt-sumatra.pdf` zurückholen.
  4. Lässt sich ein textbewahrender PDF-Druck ohne Benutzersitzung nicht auslösen: so protokollieren; den Druck aus einem echten Programm macht Marvin morgen (Frage im Index-Bericht).

- [ ] **Step 7: Dienstverhalten**
  - `Stop-ScheduledTask` (Befehl aus `gm-update.json` `stopp`) bei laufender **und** bei gestoppter Aufgabe → beide Exit 0? `start` → `pythonw` läuft. Zum Vergleich `schtasks /End /TN "GM-IT\E-Rechnung"` bei gestoppter Aufgabe: Exit-Code notieren.
  - `Stop-Process -Name pythonw -Force` → nach spätestens 6 Min. läuft wieder ein `pythonw` (Wiederholungsauslöser).
  - `Restart-Computer -Force` (per `systemd-run`, Wartezeit ~3 Min.) → `pythonw` läuft nach dem Start.

- [ ] **Step 8: Rechte-Frage A4** – Mit `icacls C:\E-Rechnung\Eingang` den Benutzer-Eintrag vorübergehend entfernen (`icacls … /remove:g *S-1-5-32-545`), Out-Printer-Test wiederholen (als SYSTEM gedruckt). Danach Eintrag wiederherstellen. Hinweis im Protokoll: Der Kontext eines druckenden **Benutzers** ist so nicht prüfbar; offen bis zum Druck durch Marvin.

- [ ] **Step 9: Aufräumen** – hosts-Datei zurückspielen, `C:\gm-setup\token` und `teil-*.b64` löschen, echte PDFs in `C:\gm-setup` löschen (die in `C:\E-Rechnung` bleiben für Task 12/14 liegen – Labor-VM). Installation **nicht** zurückbauen.

- [ ] **Step 10: Protokoll committen**

```bash
git -C /root/erechnung-konverter add docs/testprotokoll.md
git -C /root/erechnung-konverter commit -m "Testprotokoll VM 108: Einrichtung und Druck mit 0.1.0" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```

Rückmeldung an die Hauptsitzung: Tabelle der Prüfpunkte, Abweichungen, ob Spooler-Überschreiben auftrat, Ergebnis SumatraPDF (Text ja/nein), Exit-Codes Stopp/Start.
