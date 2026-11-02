#Requires -RunAsAdministrator
<#
  Richtet den E-Rechnung-Konverter ein (GM IT Solutions). Als Administrator im Setup-Ordner ausführen:
  .\einrichten.ps1 -TokenDatei .\token -Konfig .\konfig.json [-GmUpdateExe .\gm-update.exe] [-Daten C:\E-Rechnung]
  Wiederholbar: vorhandene Teile werden geprüft bzw. nachgezogen. -Konfig ist nur Pflicht, solange
  im Programmordner noch keine konfig.json liegt (oder mit -KonfigErsetzen).
  Runbook: docs/einrichten.md
#>
param(
  [Parameter(Mandatory = $true)][string]$TokenDatei,
  [string]$Konfig,
  [string]$GmUpdateExe = (Join-Path $PSScriptRoot 'gm-update.exe'),
  [string]$Daten = 'C:\E-Rechnung',
  [string]$Drucker = 'E-Rechnung',
  [switch]$KonfigErsetzen
)
$ErrorActionPreference = 'Stop'
$SYSTEM = '*S-1-5-18'
$ADMINS = '*S-1-5-32-544'
$BENUTZER = '*S-1-5-32-545'

# %ProgramFiles% wie gm-update aus HKLM (64-Bit-Sicht), nicht aus der Umgebung des Aufrufers
$hklm = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry64)
$pf = $hklm.OpenSubKey('SOFTWARE\Microsoft\Windows\CurrentVersion').GetValue('ProgramFilesDir')
if (-not $pf) { throw 'ProgramFilesDir in HKLM nicht lesbar - abgebrochen.' }
$gmit = Join-Path $pf 'GM-IT'
$prog = Join-Path $gmit 'erechnung-konverter'

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
Pruefe-KeineVerknuepfung $Daten
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

# 2. Programmordner (erbt von Program Files) mit Konfiguration, Arbeitsordner, Zusatzvorlagen.
#    Vor gm-update, damit der erste Start nach dem ersten Update schon eine konfig.json vorfindet.
#    Erst prüfen, dann anlegen, dann noch einmal prüfen (wie gm-update).
foreach ($p in $gmit, $prog) { Pruefe-KeineVerknuepfung $p }
New-Item -ItemType Directory -Force -Path $prog | Out-Null
foreach ($p in $gmit, $prog) { Pruefe-KeineVerknuepfung $p }
$ziel = Join-Path $prog 'konfig.json'
if ($KonfigErsetzen -or -not (Test-Path -LiteralPath $ziel)) {
  if (-not $Konfig) { throw "-Konfig fehlt: $ziel gibt es noch nicht." }
  $k = Get-Content -LiteralPath $Konfig -Raw -Encoding UTF8 | ConvertFrom-Json
  $ordner = @{ eingang = 'Eingang'; ausgabe = 'E-Rechnungen'; originale = 'Originale'; fehler = 'Fehler' }
  foreach ($n in $ordner.Keys) { $k | Add-Member -Force -NotePropertyName $n -NotePropertyValue (Join-Path $Daten $ordner[$n]) }
  [IO.File]::WriteAllText($ziel, ($k | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
}
New-Item -ItemType Directory -Force -Path (Join-Path $prog 'arbeit'), (Join-Path $prog 'vorlagen') | Out-Null

# 3. Drucker "E-Rechnung" auf Dateiport
if (-not (Get-PrinterDriver -Name 'Microsoft Print to PDF' -ErrorAction SilentlyContinue)) {
  Enable-WindowsOptionalFeature -Online -FeatureName 'Printing-PrintToPDFServices-Features' -NoRestart | Out-Null
}
$port = Join-Path $Daten 'Eingang\rechnung.pdf'
if (-not (Get-PrinterPort -Name $port -ErrorAction SilentlyContinue)) { Add-PrinterPort -Name $port }
$d = Get-Printer -Name $Drucker -ErrorAction SilentlyContinue
if (-not $d) { Add-Printer -Name $Drucker -DriverName 'Microsoft Print to PDF' -PortName $port }
elseif ($d.PortName -ne $port) { Set-Printer -Name $Drucker -PortName $port }

# 4. "Senden an -> E-Rechnung": Verknüpfung auf den Eingang für alle vorhandenen Profile und das Default-Profil
#    (neue Benutzer). PDFs aus Edge werden gerastert gedruckt (kein Text); per Senden an kommt das Original-PDF an.
#    Wiederholbar: Save() überschreibt die Verknüpfung.
$eingang = Join-Path $Daten 'Eingang'
$profilordner = @(Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and $_.LocalPath } | ForEach-Object { $_.LocalPath })
$profilordner += (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList').Default
$shell = New-Object -ComObject WScript.Shell
foreach ($pr in $profilordner) {
  $sendto = Join-Path $pr 'AppData\Roaming\Microsoft\Windows\SendTo'
  if (-not (Test-Path -LiteralPath $sendto -PathType Container)) { Write-Host "Senden an: $sendto fehlt - übersprungen"; continue }
  if ((Get-Item -LiteralPath $sendto -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    Write-Warning "Senden an: $sendto ist eine Verknüpfung (Junction/Symlink) - übersprungen"; continue
  }
  $lnk = $shell.CreateShortcut((Join-Path $sendto 'E-Rechnung.lnk'))
  $lnk.TargetPath = $eingang
  $lnk.Description = 'PDF-Rechnung an den E-Rechnung-Konverter übergeben'
  $lnk.Save()
}

# 5. Überwachungsaufgabe: SYSTEM, beim Start und alle 5 Min. (startet einen beendeten Überwacher neu), nie doppelt.
#    Vor gm-update anlegen: dessen erster Lauf ruft stopp/start dieser Aufgabe auf und verwirft die Version,
#    wenn stopp scheitert (gm-update-Spezifikation Abschnitt 7, A-Datei Schritt 5).
$py = Join-Path $prog 'aktuell\python\pythonw.exe'
$aktion = New-ScheduledTaskAction -Execute $py -Argument "-m erechnung ueberwachen --konfig `"$ziel`"" -WorkingDirectory $prog
$ausloeser = @((New-ScheduledTaskTrigger -AtStartup),
               (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)))
$einst = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
$wer = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung' -Action $aktion -Trigger $ausloeser -Settings $einst -Principal $wer -Force | Out-Null

# 6. gm-update (ab 0.1.4): Token/Konfiguration nur SYSTEM+Admins, Update-Aufgabe, erster Lauf (lädt die freigegebene Version,
#    stoppt/startet dabei die Aufgabe aus Schritt 5)
if (-not (Test-Path -LiteralPath $GmUpdateExe)) { throw "gm-update.exe fehlt: $GmUpdateExe" }
& $GmUpdateExe installieren --konfig (Join-Path $PSScriptRoot 'gm-update.json') --token-datei $TokenDatei
if ($LASTEXITCODE -ne 0) {
  Write-Warning "gm-update installieren endete mit $LASTEXITCODE (z. B. noch keine Freigabe). Details: $prog\gm-update.log, $prog\stand.json"
}
if (-not (Test-Path -LiteralPath (Join-Path $prog 'gm-update.json'))) { throw "gm-update hat $prog nicht eingerichtet." }

# 7. Überwacher starten (gm-update hat ihn nach dem ersten Update meist schon gestartet; IgnoreNew verhindert Doppelte)
if (Test-Path -LiteralPath $py) { Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung' }
else { Write-Warning "Noch keine App-Version installiert ($py fehlt). Die Aufgabe startet, sobald gm-update sie geladen hat." }

Write-Host "Fertig. Drucker '$Drucker' -> $port; Senden an -> E-Rechnung; E-Rechnungen: $(Join-Path $Daten 'E-Rechnungen'); Log: $prog\erechnung.log"
