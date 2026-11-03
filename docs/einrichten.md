# Runbook: E-Rechnung-Konverter einrichten

## Zweck

Einrichtung, Prüfung, Pflege und Rückbau des E-Rechnung-Konverters auf einem Windows-PC des Kunden. Nach der Einrichtung gibt es den Drucker **E-Rechnung**: Was darauf gedruckt wird, landet als ZUGFeRD-E-Rechnung (EN16931, XML im PDF eingebettet) in `C:\E-Rechnung\E-Rechnungen`, vorher mit Mustang geprüft. Updates kommen signiert über gm-update. Hintergrund: `docs/spezifikation.md` (Abschnitte 3, 6, 7, 9).

| Was | Wo |
|---|---|
| Programmordner | `%ProgramFiles%\GM-IT\erechnung-konverter` (gm-update, `konfig.json`, `vorlagen\`, `arbeit\`, `erechnung.log`, `stand.json`) |
| Daten | `C:\E-Rechnung\` mit `Eingang`, `E-Rechnungen`, `Originale`, `Fehler` |
| Aufgaben | `\GM-IT\E-Rechnung` (Überwacher, SYSTEM), `\GM-IT\Update erechnung-konverter` (gm-update, täglich 03:00) |
| Drucker / Port | `E-Rechnung` (Microsoft Print to PDF) → `C:\E-Rechnung\Eingang\rechnung.pdf` |
| Senden an | Rechtsklick auf ein PDF → **Senden an → E-Rechnung** (Verknüpfung auf `C:\E-Rechnung\Eingang`, in jedem Profil) |
| Texterkennung | `aktuell\tesseract\tesseract.exe` mit `tessdata\deu.traineddata`, nur für PDFs ohne Text |

## Voraussetzungen

- Windows 10/11 oder Server, 64 Bit, PowerShell 5.1, Administratorkonto (Einrichtung nur durch GM IT).
- HTTPS-Zugang zu `git.gm-itsolutions.de`.
- Eine freigegebene Version von `erechnung-konverter` (sonst richtet das Skript alles ein, die App kommt mit dem ersten gm-update-Lauf nach der Freigabe).
- Lesetoken des Kunden `update-<kunde>` (ai-os Runbook `40-wissen/runbooks/release-und-update.md`, Abschnitt C). Im Test: `update-test`.

## Schritte

### 1. Setup-Ordner zusammenstellen

Ein Ordner, z. B. `C:\Setup\erechnung`, mit:

| Datei | Herkunft |
|---|---|
| `einrichten.ps1`, `gm-update.json`, `konfig.beispiel.json` | Ordner `einrichten\` aus dem freigegebenen ZIP oder aus dem Repo |
| `gm-update.exe` | gm-update **0.1.4** (oder neuer, freigegeben) aus der Paketablage, umbenannt |
| `token` | Lesetoken des Kunden (nur `read:package`), eine Zeile |
| `konfig.json` | Verkäuferdaten des Kunden, nach `konfig.beispiel.json` |

gm-update laden (PowerShell):

```powershell
cd C:\Setup\erechnung
Invoke-WebRequest -UseBasicParsing -OutFile .\gm-update.exe `
  https://git.gm-itsolutions.de/api/packages/gm-itsolutions/generic/gm-update/0.1.4/gm-update-0.1.4-windows-amd64.exe
Get-FileHash .\gm-update.exe -Algorithm SHA256
```

Den Hash mit dem Eintrag `gm-update-0.1.4-windows-amd64.exe` in der **freigegebenen** `release.json` von gm-update 0.1.4 vergleichen. Die erste gm-update-Datei liegt außerhalb der Signaturkette, dieser Abgleich ist der Ausgleich. Passt er nicht: abbrechen.

`konfig.json`:
- Pflicht: `verkaeufer.name`, `ust_id` **oder** `steuernummer`, `iban`. Übrige Felder (`strasse`, `plz`, `ort`, `land`, `email`, `bic`) so vollständig wie möglich, sie gehen in die E-Rechnung.
- Im Block `verkaeufer` nur diese Felder, keine Kommentar- oder Zusatzfelder (sonst startet der Überwacher nicht).
- Die vier Ordnerpfade setzt `einrichten.ps1` aus `-Daten`; Werte in der Datei werden überschrieben.
- Optional `"xml_einzeln": true` (oberste Ebene, nicht im Block `verkaeufer`): zusätzlich `<Nummer>.xml` in `E-Rechnungen`, z. B. wenn der Kunde Behörden über ein XRechnung-Portal beliefert. Standard (Schlüssel fehlt oder `false`): nur `<Nummer>.pdf`. Nachträglich ändern: `konfig.json` im Programmordner als Administrator bearbeiten, dann Aufgabe `E-Rechnung` stoppen und starten (wie Schritt 4).
- Datei als UTF-8 speichern. Keine Zugangsdaten hinein.

### 2. Einrichten

PowerShell **als Administrator** (64 Bit):

```powershell
cd C:\Setup\erechnung
Set-ExecutionPolicy -Scope Process Bypass
.\einrichten.ps1 -TokenDatei .\token -Konfig .\konfig.json
```

Optionen: `-Daten D:\E-Rechnung` (anderer Datenordner), `-Drucker <Name>`, `-GmUpdateExe <Pfad>`, `-KonfigErsetzen` (vorhandene `konfig.json` im Programmordner ersetzen).

Das Skript ist wiederholbar und macht der Reihe nach:
1. Datenordner anlegen bzw. Besitzer und Rechte nachziehen (Besitzer Administratoren, Vererbung aus; SYSTEM/Admins Vollzugriff, Benutzer Lesen, in `Eingang` Ändern). Bricht ab, wenn ein Ordner eine Junction/ein Symlink ist.
2. Programmordner (unter `ProgramFilesDir` aus HKLM), `konfig.json`, `arbeit\`, `vorlagen\`.
3. Drucker und Dateiport; fehlt „Microsoft Print to PDF“, wird das Windows-Feature aktiviert.
4. „Senden an → E-Rechnung“ in jedem vorhandenen Benutzerprofil und im Default-Profil (neue Benutzer bekommen es bei der ersten Anmeldung). Profile ohne SendTo-Ordner werden übersprungen. Wer nach der Einrichtung ein neues Profil anlegt, hat den Eintrag automatisch; Profile mit umgeleitetem AppData (Ordnerumleitung) nicht.
5. Aufgabe `\GM-IT\E-Rechnung` (SYSTEM, beim Start und alle 5 Min., nie doppelt).
6. `gm-update installieren`: Token und `gm-update.json` nur SYSTEM/Admins, Aufgabe `\GM-IT\Update erechnung-konverter`, erster Lauf (lädt, prüft und installiert die freigegebene Version, startet den Überwacher).
7. Überwacher starten, falls schon eine Version da ist.

Danach die Token-Datei im Setup-Ordner löschen:

```powershell
Remove-Item .\token
```

Eine Warnung „gm-update installieren endete mit …“ heißt meist: noch keine Freigabe. Die Einrichtung ist trotzdem fertig; die App kommt mit dem nächsten täglichen Lauf oder mit `Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'Update erechnung-konverter'`. Auch der Handstart wartet zufällig bis zu 60 Minuten (`--verzoegerung 60m` steht in der Aktion der Aufgabe, nicht im Auslöser). Sofort geht es als Administrator mit `& "$env:ProgramFiles\GM-IT\erechnung-konverter\gm-update.exe" lauf --konfig "$env:ProgramFiles\GM-IT\erechnung-konverter\gm-update.json"`.

### 3. Prüfen

```powershell
Get-ScheduledTask -TaskPath '\GM-IT\'                        # E-Rechnung und Update erechnung-konverter
Get-Process pythonw                                          # Überwacher läuft
Get-Content "$env:ProgramFiles\GM-IT\erechnung-konverter\stand.json"
Get-Printer -Name 'E-Rechnung' | Format-List Name, DriverName, PortName
```

- `stand.json`: `version` gesetzt, `fehler` leer.
- Testdruck: eine Rechnung aus dem Programm des Kunden auf **E-Rechnung** drucken, angemeldet als Benutzer. Nicht als SYSTEM (RMM-Shell, geplante Aufgabe als SYSTEM): Dann bleibt der Auftrag mit „Fehler – Wird gedruckt“ in der Warteschlange hängen, es entsteht keine Datei, der Drucker steht auf Fehler. Solche Aufträge mit `Get-PrintJob -PrinterName 'E-Rechnung' | Remove-PrintJob` löschen. Der Spooler schreibt die Datei im Kontext des druckenden Benutzers (Besitzer der Datei ist der Benutzer), deshalb brauchen Benutzer in `Eingang` das Recht Ändern. Nach wenigen Sekunden (Mustang-Prüfung rund 3–8 s) liegt `<Rechnungsnummer>.pdf` in `C:\E-Rechnung\E-Rechnungen` (mit `xml_einzeln` zusätzlich `.xml`), das Original in `Originale`. Im Log steht je Rechnung `Mustang: valid, Profil urn:cen.eu:en16931:2017, … 0 verletzt`, beim Start „Mustang: …\java\bin\java.exe …\Mustang-CLI-2.26.0.jar“.
- Senden an: als Benutzer im Explorer Rechtsklick auf eine Lexware-PDF → **Senden an → E-Rechnung**. Ergebnis wie beim Druck; die Datei im Ausgangsordner des Benutzers sollte erhalten bleiben (Explorer kopiert; auf VM 108 noch zu bestätigen).
- Texterkennung: eine Rechnung aus **Edge** auf **E-Rechnung** drucken (Edge druckt PDFs als Bild). Nach etwa 10 s je Seite liegt `<Nummer>.pdf` in `E-Rechnungen`; der Vermerk `<stempel>-<name>.ocr.txt` (Hinweis + erkannter Text) liegt neben dem Original in `Originale` und steht auch im Log, dazu „per Texterkennung gelesen“ und beim Start „Texterkennung: …\tesseract.exe“.
- Log: `%ProgramFiles%\GM-IT\erechnung-konverter\erechnung.log` (je Datei Eingang, Vorlage, Ergebnis/Fehler), gm-update: `gm-update.log` daneben.

### 4. Neue Vorlage ohne Release

Für einen Rechnungsaufbau, den die mitgelieferten Vorlagen nicht kennen:

```powershell
Copy-Item .\meine-vorlage.yaml "$env:ProgramFiles\GM-IT\erechnung-konverter\vorlagen\"
```

Der Überwacher lädt Vorlagen in `vorlagen\` und `vorlagen\angelernt\` binnen einer Sekunde neu (Logzeile „Vorlagen neu geladen“). Eine fehlerhafte Datei wird mit Warnung übersprungen.

Danach das betroffene PDF aus `Fehler` erneut nach `Eingang` kopieren. Bewährt sich die Vorlage, ins Repo übernehmen und mit dem nächsten Release ausliefern (dann die Kopie im Ordner `vorlagen\` entfernen).

### 5. Neue Vorlage anlernen (Lernmodus)

Der Kunde bringt dem Konverter ein neues Rechnungslayout selbst bei, ohne Release. Spezifikation: `docs/lernmodus/spezifikation.md`.

**Wer:** Der Kunde am PC. Aktivieren, Deaktivieren, Reaktivieren und Löschen einer Vorlage braucht ein Administrator-Konto (UAC, Entscheidung F1), sonst GM IT per Fernwartung. Die erste Vorlage beim Kunden lernt GM IT gemeinsam mit dem Kunden an (F3, Prignitz Markt).

**Ablauf:**

1. Startmenü → **GM-IT → E-Rechnung anlernen** (öffnet die Oberfläche im Browser) → **Neue Vorlage**.
2. Mindestens zwei Muster laden (Datei oder aus `Fehler`), möglichst das Original-PDF **und** einen Druck über „E-Rechnung“.
3. Felder und Tabelle auf dem Muster markieren.
4. **Probelauf** über alle Muster; alle Häkchen müssen grün sein.
5. **Vorlage aktivieren** → UAC-Abfrage.

**UAC-Abfrage prüfen (Administrator):** Die Abfrage zeigt allgemein „Python“, nicht den Namen der Anwendung. Vor „Ja“ auf **Details anzeigen** klicken. Die Befehlszeile muss lauten:

```text
…\GM-IT\erechnung-konverter\…\python.exe -m erechnung vorlage (aktivieren|deaktivieren|reaktivieren|loeschen) …
```

Steht dort etwas anderes (anderes Programm, andere Argumente, `-c`, eine fremde Skriptdatei), mit **Nein** ablehnen. Die UAC-Freigabe ist die Sicherheitsgrenze; jeder angemeldete Benutzer kann dieselbe Abfrage auslösen.

**Wo liegt was:**

| Was | Wo |
|---|---|
| Entwürfe, Muster-PDFs (Rechnungskopien) | `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen\entwuerfe\<name>\` (Benutzerprofil) |
| Log der Oberfläche | `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen\anlernen.log` |
| Aktive angelernte Vorlagen | `%ProgramFiles%\GM-IT\erechnung-konverter\vorlagen\angelernt\<name>.yml` |
| Deaktivierte und ersetzte | `…\vorlagen\angelernt\deaktiviert\` |
| Protokoll (Zeit, Benutzer, Admin-Konto, Aktion, Name, SHA-256, Anzahl Muster) | `…\vorlagen\angelernt\protokoll.txt` |
| Ergebnis des Administrator-Laufs (JSON, nach 24 h aufgeräumt) | `…\erechnung-konverter\ergebnisse\<id>.json` |
| Arbeitsordner des Administrator-Laufs | `…\erechnung-konverter\aktivieren-*` (neben `konfig.json`, wird nach dem Lauf gelöscht) |

**Rechte prüfen:** Benutzer dürfen in `vorlagen\angelernt\` und `ergebnisse\` nur lesen (Program-Files-Standard, `einrichten.ps1` ändert sie nicht). Sonst könnte jeder Benutzer Vorlagen des SYSTEM-Dienstes ändern.

```powershell
icacls "$env:ProgramFiles\GM-IT\erechnung-konverter\vorlagen\angelernt"
icacls "$env:ProgramFiles\GM-IT\erechnung-konverter\ergebnisse"
```

Erwartet (Windows-Standard, auf VM 108 noch zu bestätigen): `BUILTIN\Users:(I)(OI)(CI)(RX)`, Schreibrechte (`F`, `M`, `W`) nur für `NT SERVICE\TrustedInstaller`, `NT AUTHORITY\SYSTEM`, `BUILTIN\Administrators`. Steht `Users` oder `Authenticated Users` mit `M`/`W`/`F`: Vererbung wurde verändert; Ursache klären, nicht mit `icacls /grant` überdecken.

**Prüfen:** `erechnung.log` zeigt binnen einer Sekunde nach dem Aktivieren „Vorlagen neu geladen: …“ (kein Neustart nötig). Danach eine Testrechnung im neuen Layout über **E-Rechnung** drucken; `<Nummer>.pdf` liegt in `E-Rechnungen`.

**Export an GM IT:** In der Oberfläche **Für GM IT exportieren** → `erechnung-vorlage-<name>-<datum>.yml` im Download-Ordner (nur die Vorlage, keine Rechnungen, F2) → per Mail an GM IT. Übernahme ins Release: YAML nach `erechnung/vorlagen/` im Repo. Eine Prüfrechnung des Layouts fordert GM IT gesondert an (nur nach `/root/erechnung-testdaten/`, nie ins Repo). Nach dem Release die angelernte Datei beim Kunden **löschen** (Oberfläche **Löschen**, UAC). Die mitgelieferte Vorlage gewinnt ohnehin, im Log steht die Warnung „gleichnamig“.

## Fehlerbilder

Fehler stehen je Datei in `C:\E-Rechnung\Fehler\<stempel>-<name>.fehler.txt`, das PDF daneben.

| Meldung / Bild | Ursache | Abhilfe |
|---|---|---|
| keine Vorlage passt | Rechnungsaufbau unbekannt oder Schlüsselwörter geändert | Vorlage ergänzen (Schritt 4), PDF erneut nach `Eingang` |
| kein Text im PDF (als Bild gedruckt?), Texterkennung nicht verfügbar | Programm druckt Seiten als Bild (Edge, SumatraPDF) und `tesseract\` fehlt im Paket | Original-PDF per **Senden an → E-Rechnung** übergeben; Paket prüfen (`aktuell\tesseract\tesseract.exe`) |
| … (per Texterkennung gelesen), darunter „Versuchte Lesarten: …“ | PDF ohne Text, Texterkennung hat in **keiner** Lesart (psm 6, ohne Linien, psm 4) stimmig gelesen (Nummer, Betrag, Position); der Grund stammt aus der ersten Lesart. Es entsteht bewusst keine E-Rechnung. Dauert bis zu viermal so lange wie eine erfolgreiche Erkennung | Original-PDF per **Senden an** übergeben (dann ohne Texterkennung). Häuft es sich: PDF aus `Fehler` an GM IT, Vorlage anpassen |
| Texterkennung fehlgeschlagen (Seite …) | `tesseract.exe` startet nicht (fehlende DLL), Frist 120 s überschritten | `erechnung.log`; als Administrator `& "$env:ProgramFiles\GM-IT\erechnung-konverter\aktuell\tesseract\tesseract.exe" --version` |
| zu viele Seiten für die Texterkennung | Bild-PDF mit mehr als 20 Seiten | Original-PDF mit Text übergeben |
| Summenfehler (z. B. „Netto: Positionen … ≠ Rechnung …“) | Vorlage liest einen Betrag falsch oder die Rechnung ist rechnerisch falsch | PDF prüfen; Rechnung korrigieren oder Vorlage anpassen. Es entsteht bewusst keine E-Rechnung |
| PDF unvollständig | Druckauftrag abgebrochen | Erneut drucken |
| E-Rechnung laut Mustang ungültig, darunter Zeilen wie `BR-CO-15: …` | Die erzeugte XML verletzt eine EN16931-Regel (Regel-ID und Text stehen in der Fehlerdatei). Es entsteht bewusst keine E-Rechnung | PDF und Fehlerdatei an GM IT; Ursache liegt in Vorlage oder Konverter (`cii.py`), nicht beim Kunden |
| Mustang-Prüfung nicht verfügbar / Mustang nicht startbar / Frist 60 s überschritten / Mustang-Prüfung ohne Bericht | `aktuell\java\` oder `aktuell\mustang\` fehlt oder ist beschädigt, Java startet nicht (Speicher, Virenscanner), PC stark ausgelastet | `erechnung.log` (Startzeile „Mustang: …“); als Administrator `& "$env:ProgramFiles\GM-IT\erechnung-konverter\aktuell\java\bin\java.exe" -version`. Danach PDF aus `Fehler` erneut nach `Eingang` |
| Nichts passiert, `pythonw` läuft nicht | Überwacher beendet oder App fehlt | `erechnung.log` lesen; fehlt `aktuell` im Programmordner: `stand.json` und `gm-update.log` lesen (keine Freigabe, Token, Netz). Aufgabe startet einen beendeten Überwacher binnen 5 Min. neu |
| `stand.json`: „… übersprungen bis zu einer höheren Freigabe“ | Probe der neuen Version gescheitert, gm-update blieb auf der vorigen | Ursache im `gm-update.log`, Fehler beheben, höhere Version freigeben |
| Anker „…“ nicht gefunden (Probelauf oder Rechnung in `Fehler`) | Layout hat sich geändert oder der Druckweg verschiebt die Seite stark (Original-PDF gegen Druck über „E-Rechnung“) | Muster dieses Druckwegs hinzufügen, Vorlage neu anlernen und aktivieren |
| Tabellenkopf … nicht gefunden | Spaltenüberschriften stehen anders (Texterkennung, anderer Druckweg) | Muster dieses Druckwegs ergänzen, Tabellenkopf neu markieren |
| Käuferblock ohne Name, Straße, PLZ/Ort | Käuferbereich zu klein oder verschoben markiert | Bereich im Muster größer ziehen, Probelauf wiederholen |
| Start-Link ungültig oder schon benutzt | Die Oberfläche wurde mit einem alten oder bereits verwendeten Link geöffnet (Link gilt einmal) | Oberfläche über das Startmenü neu öffnen |
| Administratorfreigabe abgebrochen | UAC mit „Nein“ beantwortet oder geschlossen | Aktion erneut starten, Admin-Konto wählen; Befehlszeile unter „Details“ prüfen (Abschnitt 5) |

## Rückbau

Als Administrator:

```powershell
Stop-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung'
Unregister-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung' -Confirm:$false
Unregister-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'Update erechnung-konverter' -Confirm:$false
Remove-Printer -Name 'E-Rechnung'
Remove-PrinterPort -Name 'C:\E-Rechnung\Eingang\rechnung.pdf'
# Senden an: Verknüpfung aus allen Profilen und dem Default-Profil entfernen
$profilordner = @(Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special -and $_.LocalPath } | ForEach-Object { $_.LocalPath })
$profilordner += (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList').Default
foreach ($pr in $profilordner) {
  Remove-Item -LiteralPath (Join-Path $pr 'AppData\Roaming\Microsoft\Windows\SendTo\E-Rechnung.lnk') -ErrorAction SilentlyContinue
}
# Startmenü "E-Rechnung anlernen" (alle Benutzer)
Remove-Item -LiteralPath "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\GM-IT\E-Rechnung anlernen.lnk"
Remove-Item -Recurse -Force "$env:ProgramFiles\GM-IT\erechnung-konverter"
```

Den Datenordner `C:\E-Rechnung` **nur nach Rücksprache mit dem Kunden** löschen: Er enthält die erzeugten E-Rechnungen und Originale.

Entwürfe der Benutzer liegen in `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen` (jedes Benutzerprofil, enthalten Rechnungskopien). Mit dem Kunden klären, dann löschen.

## Wiederherstellung

Neuinstallation mit denselben Schritten (Abschnitt 2). Den Ordner `vorlagen\angelernt` vorher sichern (z. B. `Copy-Item -Recurse "$env:ProgramFiles\GM-IT\erechnung-konverter\vorlagen\angelernt" C:\Sicherung\`) und danach zurückkopieren. Ersatzweise die exportierten `.yml` bei GM IT nach `vorlagen\angelernt\<name>.yml` legen. Eine fehlerhafte neue Version stellt gm-update selbst auf die vorige zurück; die Originale bleiben in `Originale`.
