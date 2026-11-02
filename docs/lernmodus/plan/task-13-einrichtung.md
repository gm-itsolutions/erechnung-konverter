# Task 13: Einrichtung, Paket, Runbook

Spezifikation: `docs/lernmodus/spezifikation.md` 3.2, 4, 10; Hauptspezifikation 6, 9. Global Constraints in `index.md`.

**Files:**
- Modify: `einrichten/einrichten.ps1`, `release/bauen.sh` (Selbstprüfung), `docs/einrichten.md`, `release/THIRD-PARTY.txt` (IBM Plex Sans/Mono, SIL Open Font License 1.1, Quelle github.com/IBM/plex; in `webui/fonts/` liegt kein Lizenztext: den OFL-1.1-Text aus dem IBM-Plex-Repository holen, Herkunft und Commit nennen, als `erechnung/anlernen/statisch/fonts/OFL.txt` mitliefern), `docs/spezifikation.md` (Abschnitt 4 Komponenten: Verweis auf `docs/lernmodus/spezifikation.md`; Abschnitt 6 Tabelle: Zeile `vorlagen\angelernt\`)

**Interfaces:**
- Consumes: CLI `python -m erechnung anlernen --konfig <konfig.json>` (Task 07), Ordner `vorlagen\angelernt\` (Task 06/09), Statische Dateien (Task 11).
- Produces: Startmenü-Verknüpfung `%ProgramData%\Microsoft\Windows\Start Menu\Programs\GM-IT\E-Rechnung anlernen.lnk`; Ordner `<Programmordner>\vorlagen\angelernt\deaktiviert`.

- [ ] **Step 1: `einrichten.ps1`** – In Schritt 2 (Programmordner) die Zeile `New-Item … 'arbeit', 'vorlagen'` erweitern und danach prüfen (Rechte erben von Program Files: Benutzer lesen, nur Admins/SYSTEM schreiben; nicht ändern):

```powershell
$angelernt = Join-Path $prog 'vorlagen\angelernt'
foreach ($p in (Join-Path $prog 'vorlagen'), $angelernt, (Join-Path $angelernt 'deaktiviert')) { Pruefe-KeineVerknuepfung $p }
New-Item -ItemType Directory -Force -Path (Join-Path $prog 'arbeit'), (Join-Path $prog 'vorlagen'), (Join-Path $angelernt 'deaktiviert') | Out-Null
foreach ($p in (Join-Path $prog 'vorlagen'), $angelernt, (Join-Path $angelernt 'deaktiviert')) { Pruefe-KeineVerknuepfung $p }
```

Neuer Schritt nach „Senden an“ (Schritt 4), als **4b**:

```powershell
# 4b. Startmenü "E-Rechnung anlernen" für alle Benutzer (Lernmodus, läuft im Benutzerkontext, docs/lernmodus/spezifikation.md 3.2)
$startmenue = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\GM-IT'
Pruefe-KeineVerknuepfung $startmenue
New-Item -ItemType Directory -Force -Path $startmenue | Out-Null
$lnk = $shell.CreateShortcut((Join-Path $startmenue 'E-Rechnung anlernen.lnk'))
$lnk.TargetPath = Join-Path $prog 'aktuell\python\pythonw.exe'
$lnk.Arguments = "-m erechnung anlernen --konfig `"$ziel`""
$lnk.WorkingDirectory = $prog
$lnk.Description = 'Neue Rechnungsvorlage für den E-Rechnung-Konverter anlernen'
$lnk.Save()
```

`$env:ProgramData` kommt hier aus der Umgebung des Administrators; zur Härtung wie bei `ProgramFilesDir` aus HKLM lesen: `$hklm.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList').GetValue('ProgramData')` (Wert enthält `%SystemDrive%` → `[Environment]::ExpandEnvironmentVariables`). Die Schlussmeldung um „Startmenü: E-Rechnung anlernen“ ergänzen.

- [ ] **Step 2: PowerShell-Syntax prüfen** – auf gm-claude gibt es kein PowerShell 5.1; Syntax per `pwsh` prüfen, falls vorhanden (`which pwsh`): `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('/root/ek-wt-lern/einrichten/einrichten.ps1', [ref]$null, [ref]$e) | Out-Null; $e"` – das ist **ein** Befehl (das `;` steht im PowerShell-Code, nicht in der Shell). Fehlt pwsh: Prüfung auf VM 108 (Task 14).

- [ ] **Step 3: `release/bauen.sh`** – Selbstprüfung um `app/erechnung/anlernen/server.py`, `app/erechnung/anlernen/statisch/index.html`, `app/erechnung/anlernen/statisch/gm.css`, `app/erechnung/anlernen/statisch/anlernen.js` und `app/erechnung/bereiche.py` ergänzen. Bau lokal: `bash /root/ek-wt-lern/release/bauen.sh 0.2.0-test` im Worktree (nur, wenn die Paketablage erreichbar ist; sonst überspringen und im Commit vermerken). Danach `dist/` nicht committen.

- [ ] **Step 4: Runbook `docs/einrichten.md`** – neuer Abschnitt **„5. Neue Vorlage anlernen (Lernmodus)“** nach Abschnitt 4:
  - Wer: Kunde am PC; Aktivieren braucht ein Administrator-Konto (UAC), sonst GM IT per Fernwartung.
  - Ablauf in fünf Zeilen: Startmenü „E-Rechnung anlernen“ → „Neue Vorlage“ → mindestens zwei Muster (Datei oder aus `Fehler`, möglichst Original-PDF **und** Druck über „E-Rechnung“) → Felder und Tabelle markieren → Probelauf, Häkchen, „Vorlage aktivieren“.
  - Wo liegt was (Tabelle aus Spezifikation 4), Protokoll `vorlagen\angelernt\protokoll.txt`.
  - Prüfen: `erechnung.log` zeigt „Vorlagen neu geladen: …“; eine Testrechnung drucken.
  - Export an GM IT: „Für GM IT exportieren“ → ZIP im Download-Ordner → per Mail an GM IT. Übernahme ins Release: YAML nach `erechnung/vorlagen/`, Muster nur nach `/root/erechnung-testdaten/`; nach dem Release die angelernte Datei beim Kunden **löschen** (die mitgelieferte gewinnt ohnehin, Logwarnung „gleichnamig“).
  - Fehlerbilder ergänzen: „Anker ‚…‘ nicht gefunden“ (Layout geändert oder Druckweg verschiebt stark → Muster dieses Druckwegs hinzufügen, neu anlernen), „Tabellenkopf … nicht gefunden“, „Käuferblock ohne Name, Straße, PLZ/Ort“, „Start-Link ungültig oder schon benutzt“ (Oberfläche über das Startmenü neu öffnen), „Administratorfreigabe abgebrochen“.
  - **Rückbau** ergänzen: `Remove-Item -LiteralPath "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\GM-IT\E-Rechnung anlernen.lnk"`; Entwürfe der Benutzer liegen in `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen` (enthalten Rechnungskopien; mit dem Kunden klären, löschen).
  - **Wiederherstellung** ergänzen: Ordner `vorlagen\angelernt` vor einer Neuinstallation sichern und danach zurückkopieren; ersatzweise die Export-ZIPs bei GM IT (YAML nach `vorlagen\angelernt\<name>.yml`).

- [ ] **Step 5: Hauptspezifikation** – `docs/spezifikation.md`: Abschnitt 4 eine Zeile „Lernmodus: `erechnung/bereiche.py`, `erechnung/anlernen/` – siehe `docs/lernmodus/spezifikation.md`“; Abschnitt 6 Tabelle Zeile `…\vorlagen\angelernt\` (aktive angelernte Vorlagen, nur Admins schreiben); Abschnitt 5 Satz „Angelernte Vorlagen (`art: bereiche`) siehe Lernmodus-Spezifikation 5.“; Stand-Zeile um „0.2.0: Lernmodus“ ergänzen.

- [ ] **Step 6: Tests** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git -C /root/ek-wt-lern add einrichten/einrichten.ps1 release/bauen.sh release/THIRD-PARTY.txt erechnung/anlernen/statisch/fonts/OFL.txt docs/einrichten.md docs/spezifikation.md
git -C /root/ek-wt-lern commit -m "Lernmodus: Startmenü, Vorlagenordner, Paketprüfung, Runbook" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
