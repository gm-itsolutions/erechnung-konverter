# Task 07: `einrichten.ps1`, `gm-update.json`, Runbook

Spezifikation: Abschnitt 3.1, 6, 7, 9. gm-update-Spezifikation `/root/gm-update/docs/spezifikation.md` Abschnitt 7 (nur lesen: `sed -n 115,177p`). Global Constraints in `index.md`.

**Files:**
- Create: `einrichten/einrichten.ps1`, `einrichten/gm-update.json`, `einrichten/konfig.beispiel.json`, `docs/einrichten.md`

**Interfaces:**
- Consumes: CLI `python -m erechnung ueberwachen --konfig <pfad>` (Task 05), ZIP-Aufbau `python\`, `app\` (Task 06), `gm-update.exe installieren --konfig --token-datei` (gm-update 0.1.3).
- Produces: Aufgabe `\GM-IT\E-Rechnung`, Drucker `E-Rechnung`, Port `<Daten>\Eingang\rechnung.pdf`, Ordner nach Spezifikation Abschnitt 6, `konfig.json` im Programmordner.

Kein PowerShell auf gm-claude: Syntax wird erst in Task 10 auf der VM geprüft. Deshalb nur PowerShell-5.1-Sprachmittel (kein `??`, kein `?.`, kein ternärer Operator), Datei **UTF-8 mit BOM** speichern (PowerShell 5.1 liest sonst Umlaute falsch): nach dem Schreiben `printf '\xef\xbb\xbf' | cat - einrichten/einrichten.ps1 > /tmp/e.ps1` und zurückkopieren, Zeilenenden CRLF (`sed -i 's/$/\r/'`).

- [ ] **Step 1: `einrichten/gm-update.json`**

```json
{
  "produkt": "erechnung-konverter",
  "kanal": "stabil",
  "art": "datei",
  "basis_url": "https://git.gm-itsolutions.de",
  "benutzer": null,
  "probe": ["aktuell/python/python.exe", "-m", "erechnung", "--version"],
  "stopp": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Stop-ScheduledTask -TaskPath '\\GM-IT\\' -TaskName 'E-Rechnung'"],
  "start": ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Start-ScheduledTask -TaskPath '\\GM-IT\\' -TaskName 'E-Rechnung'"],
  "compose_ordner": null,
  "health_sekunden": 60
}
```

Mit `python3 -m json.tool einrichten/gm-update.json` prüfen. gm-update ersetzt nur das Präfix `aktuell/` (in der Probe → `versionen\<v>\python\python.exe`).

- [ ] **Step 2: `einrichten/konfig.beispiel.json`** – wie Spezifikation Abschnitt 7, Verkäuferdaten als Platzhalter `"…"`. Im Block `verkaeufer` nur Felder von `Partei` (sonst `TypeError` in `lade_konfig`), keine Kommentarfelder; Hinweise gehören in `docs/einrichten.md`. Die vier Ordnerpfade setzt `einrichten.ps1` aus `-Daten`.

- [ ] **Step 3: `einrichten/einrichten.ps1`**

```powershell
#Requires -RunAsAdministrator
<#
  Richtet den E-Rechnung-Konverter ein (GM IT Solutions). Als Administrator im Setup-Ordner ausführen:
  .\einrichten.ps1 -TokenDatei .\token -Konfig .\konfig.json [-GmUpdateExe .\gm-update.exe] [-Daten C:\E-Rechnung]
  Wiederholbar: vorhandene Teile werden geprüft bzw. nachgezogen.
#>
param(
  [Parameter(Mandatory = $true)][string]$TokenDatei,
  [Parameter(Mandatory = $true)][string]$Konfig,
  [string]$GmUpdateExe = (Join-Path $PSScriptRoot 'gm-update.exe'),
  [string]$Daten = 'C:\E-Rechnung',
  [string]$Drucker = 'E-Rechnung',
  [switch]$KonfigErsetzen
)
$ErrorActionPreference = 'Stop'
$prog = Join-Path ([Environment]::GetFolderPath('ProgramFiles')) 'GM-IT\erechnung-konverter'
$SYSTEM = '*S-1-5-18'; $ADMINS = '*S-1-5-32-544'; $BENUTZER = '*S-1-5-32-545'

function Pruefe-KeineVerknuepfung([string]$pfad) {
  if ((Test-Path -LiteralPath $pfad) -and ((Get-Item -LiteralPath $pfad -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "$pfad ist eine Verknüpfung (Junction/Symlink) - abgebrochen."
  }
}
function Icacls([string[]]$argumente) {
  & icacls.exe @argumente | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "icacls $($argumente -join ' ') fehlgeschlagen ($LASTEXITCODE)" }
}

# 1. Datenordner: Besitzer Administratoren, Vererbung aus, Rechte explizit (auch wenn vorab von jemandem angelegt)
Pruefe-KeineVerknuepfung $Daten
New-Item -ItemType Directory -Force -Path $Daten | Out-Null
Icacls @($Daten, '/setowner', $ADMINS, '/T', '/C')
Icacls @($Daten, '/inheritance:r', '/grant:r', "${SYSTEM}:(OI)(CI)F", "${ADMINS}:(OI)(CI)F", "${BENUTZER}:(OI)(CI)RX")
foreach ($n in 'Eingang', 'E-Rechnungen', 'Originale', 'Fehler') {
  $o = Join-Path $Daten $n
  Pruefe-KeineVerknuepfung $o
  New-Item -ItemType Directory -Force -Path $o | Out-Null
  Icacls @($o, '/reset', '/T', '/C')   # erbt von $Daten
}
# Eingang: Benutzer ändern (Spooler-Kontext unklar, Spezifikation 3.1 / Abweichung A4)
Icacls @((Join-Path $Daten 'Eingang'), '/grant', "${BENUTZER}:(OI)(CI)M")

# 2. gm-update: Programmordner, Token, Update-Aufgabe, erster Lauf (lädt die freigegebene Version)
if (-not (Test-Path -LiteralPath $GmUpdateExe)) { throw "gm-update.exe fehlt: $GmUpdateExe" }
& $GmUpdateExe installieren --konfig (Join-Path $PSScriptRoot 'gm-update.json') --token-datei $TokenDatei
if ($LASTEXITCODE -ne 0) {
  Write-Warning "gm-update installieren endete mit $LASTEXITCODE (z. B. noch keine Freigabe). Details: $prog\gm-update.log, $prog\stand.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $prog 'gm-update.json'))) { throw "gm-update hat $prog nicht eingerichtet." }

# 3. Konfiguration (Verkäuferdaten), Arbeitsordner, Zusatzvorlagen
$ziel = Join-Path $prog 'konfig.json'
if ($KonfigErsetzen -or -not (Test-Path -LiteralPath $ziel)) {
  $k = Get-Content -LiteralPath $Konfig -Raw -Encoding UTF8 | ConvertFrom-Json
  $ordner = @{ eingang = 'Eingang'; ausgabe = 'E-Rechnungen'; originale = 'Originale'; fehler = 'Fehler' }
  foreach ($n in $ordner.Keys) { $k | Add-Member -Force -NotePropertyName $n -NotePropertyValue (Join-Path $Daten $ordner[$n]) }
  [IO.File]::WriteAllText($ziel, ($k | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
}
New-Item -ItemType Directory -Force -Path (Join-Path $prog 'arbeit'), (Join-Path $prog 'vorlagen') | Out-Null

# 4. Drucker "E-Rechnung" auf Dateiport
if (-not (Get-PrinterDriver -Name 'Microsoft Print to PDF' -ErrorAction SilentlyContinue)) {
  Enable-WindowsOptionalFeature -Online -FeatureName 'Printing-PrintToPDFServices-Features' -NoRestart | Out-Null
}
$port = Join-Path $Daten 'Eingang\rechnung.pdf'
if (-not (Get-PrinterPort -Name $port -ErrorAction SilentlyContinue)) { Add-PrinterPort -Name $port }
$d = Get-Printer -Name $Drucker -ErrorAction SilentlyContinue
if (-not $d) { Add-Printer -Name $Drucker -DriverName 'Microsoft Print to PDF' -PortName $port }
elseif ($d.PortName -ne $port) { Set-Printer -Name $Drucker -PortName $port }

# 5. Überwachungsaufgabe: SYSTEM, beim Start und alle 5 Min. (startet einen beendeten Überwacher neu), nie doppelt
$py = Join-Path $prog 'aktuell\python\pythonw.exe'
$aktion = New-ScheduledTaskAction -Execute $py -Argument "-m erechnung ueberwachen --konfig `"$ziel`"" -WorkingDirectory $prog
$ausloeser = @((New-ScheduledTaskTrigger -AtStartup),
               (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)))
$einst = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$wer = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung' -Action $aktion -Trigger $ausloeser -Settings $einst -Principal $wer -Force | Out-Null
if (Test-Path -LiteralPath $py) { Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung' }
else { Write-Warning "Noch keine App-Version installiert ($py fehlt). Die Aufgabe startet, sobald gm-update sie geladen hat." }

Write-Host "Fertig. Drucker '$Drucker' -> $port; E-Rechnungen: $(Join-Path $Daten 'E-Rechnungen'); Log: $prog\erechnung.log"
```

icacls nimmt SIDs mit `*`. Bei `/grant` mit `${SYSTEM}:(OI)(CI)F` erzeugt PowerShell den String `*S-1-5-18:(OI)(CI)F` – richtig so.

- [ ] **Step 4: Runbook `docs/einrichten.md`** (Stil wie ai-os-Runbooks: Zweck, Voraussetzungen, Schritte mit Beispielbefehlen, Prüfen, Fehlerbilder, Rückbau). Inhalt mindestens:
  1. Setup-Ordner zusammenstellen: `einrichten\` aus dem freigegebenen ZIP bzw. Repo, `gm-update.exe` 0.1.3 aus der Paketablage (`…/api/packages/gm-itsolutions/generic/gm-update/0.1.3/gm-update-0.1.3-windows-amd64.exe`), SHA-256 gegen dessen freigegebene `release.json` prüfen (`Get-FileHash -Algorithm SHA256`), Datei `token` (Kunden-Lesetoken `update-<kunde>`, ai-os Runbook release-und-update Abschnitt C), `konfig.json` mit Verkäuferdaten des Kunden (Pflicht: name, ust_id oder steuernummer, iban; Beispiel `konfig.beispiel.json`).
  2. PowerShell als Administrator: `Set-ExecutionPolicy -Scope Process Bypass`, dann `.\einrichten.ps1 -TokenDatei .\token -Konfig .\konfig.json`. Danach `token` im Setup-Ordner löschen.
  3. Prüfen: `Get-ScheduledTask -TaskPath '\GM-IT\'` (zwei Aufgaben), `Get-Process pythonw`, Testdruck, `C:\E-Rechnung\E-Rechnungen`, Log `%ProgramFiles%\GM-IT\erechnung-konverter\erechnung.log`, `stand.json`.
  4. Neue Vorlage ohne Release: YAML nach `%ProgramFiles%\GM-IT\erechnung-konverter\vorlagen\`, Aufgabe neu starten (`Stop-ScheduledTask`/`Start-ScheduledTask`).
  5. Fehlerbilder: „keine Vorlage passt“, „kein Text im PDF (als Bild gedruckt?)“, Summenfehler, `pythonw` läuft nicht (Log, `aktuell` fehlt → `stand.json`).
  6. Rückbau: Aufgaben `\GM-IT\E-Rechnung` und `\GM-IT\Update erechnung-konverter` löschen, `Remove-Printer -Name E-Rechnung`, `Remove-PrinterPort -Name 'C:\E-Rechnung\Eingang\rechnung.pdf'`, Programmordner löschen; Datenordner nur nach Rücksprache (enthält Rechnungen).

- [ ] **Step 5: Commit und Push**

```bash
git -C /root/erechnung-konverter add einrichten docs/einrichten.md
git -C /root/erechnung-konverter commit -m "Einrichtungsskript, gm-update-Konfiguration und Runbook" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
