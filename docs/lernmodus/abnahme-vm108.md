# Abnahme E-Rechnung-Konverter 0.2.1 (Lernmodus) auf VM 108

Rückmeldung an Claude je Punkt: ok / nicht ok, Uhrzeit, bei Auffälligkeit Screenshot. Alles, was mit "ERLEDIGT (Claude)" markiert ist, nicht wiederholen.

## Vorab (von Claude erledigt, per NetLock, 03.11.2026 07:40)

- ERLEDIGT: gm-update auf VM 108 von 0.1.7 auf **0.2.1** gebracht (`stand.json`: version 0.2.1, vorige 0.1.7, fehler leer; `gm-update.log`: "aktualisiert auf 0.2.1"). Überwacher läuft (pythonw als SYSTEM, Log "Überwachung gestartet" mit Pfad versionen\0.2.1). `python -m erechnung --version` = 0.2.1.
- ERLEDIGT: `python314._pth` ohne `import site`.
- ERLEDIGT: `einrichten.ps1` (aus 0.2.1) einmal erneut als SYSTEM gelaufen, Exit 0, keine Fehler. Damit ist Punkt 11 erledigt. Es hat die Startmenü-Verknüpfung `GM-IT\E-Rechnung anlernen.lnk` (für alle Benutzer) und die Ordner `vorlagen\angelernt`, `vorlagen\angelernt\deaktiviert`, `ergebnisse` angelegt. Vorher fehlten sie, weil nur gm-update die App aktualisiert hatte, nicht das Einrichtungsskript.
- ERLEDIGT: `icacls` auf `vorlagen\angelernt` und `ergebnisse`: Benutzer nur `(RX)`; Vollzugriff nur TrustedInstaller, SYSTEM, Administratoren (und ERSTELLER-BESITZER nur vererbt). Entspricht der Erwartung aus `docs/einrichten.md`.
- ERLEDIGT: Testdateien liegen auf der VM in `C:\Users\Public\lernmodus\` (für alle Benutzer lesbar) und `C:\Users\gmdrucktest\Desktop\lernmodus\` (Profil von gmdrucktest ist ein verwaistes Profil, das Konto gibt es in der Domäne nicht mehr; nicht benutzen). Dateien:
  - `Werkstatt-1.pdf` (BW-2026-15, 2 Positionen + Zeile "inkl. Probefahrt", netto 240,00 / USt 45,60 / brutto 285,60)
  - `Werkstatt-2.pdf` (BW-2026-16, 3 Positionen, leicht verschoben, netto 250,00 / 47,50 / 297,50)
  - `Werkstatt-3.pdf` (BW-2026-18, 4 Positionen, netto 268,00 / 50,92 / 318,92) = dritte Rechnung für Punkt 5
  - `B-1.pdf`, `B-2.pdf`, `B-3.pdf` (fremdes Layout "Online-Tool-Stil", erfundene Daten; B-3 ist die dritte Rechnung)
  - Alle Daten erfunden. Entscheide dich für EIN Layout (Empfehlung: zuerst Werkstatt, danach B als zweiter Durchlauf, falls Zeit).

Benutzer (per NetLock geprüft): `SSPR\test.admin` ist trotz Namen nur Mitglied von "Domänen-Benutzer" und kein lokaler Admin (lokale Administratoren sind nur `SSPR-SRV2\Administrator` und die Gruppe Domänen-Admins). Er ist an der Konsole angemeldet und der **Testbenutzer ohne Adminrechte**. Als UAC-Admin-Konto dient `SSPR-SRV2\Administrator` (lokal). Zweiter Benutzer für Punkt 6: `SSPR\test.aktiv`. `testsvc` und `testsvc2` nicht benutzen (keine Domänenkonten, Rechte ungeprüft).

Zugang zur VM: Proxmox-Konsole von VM 108 (gm-pve-02) oder RDP auf 10.190.1.119. Passwörter: Passwortmanager (nicht in diese Datei).

## 0. Anmelden (VM 108, Benutzer test.admin)

Als `SSPR\test.admin` anmelden bzw. in der laufenden Konsolensitzung bleiben (Konsole in Proxmox oder RDP). PowerShell öffnen (normal, nicht als Admin):

```powershell
whoami
whoami /groups | findstr /i "S-1-5-32-544"
```

Erwartet: `sspr\test.admin` und bei der zweiten Zeile keine Ausgabe (kein Admin). Kommt eine Zeile mit "Aktiviert", ist der Benutzer Admin: anderen Benutzer nehmen und mir sagen.

Dateien auf den Desktop holen:

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Desktop\lernmodus" | Out-Null
Copy-Item C:\Users\Public\lernmodus\*.pdf "$env:USERPROFILE\Desktop\lernmodus\"
Get-ChildItem "$env:USERPROFILE\Desktop\lernmodus" | Select Name,Length
```

Erwartet: sechs PDFs.

## 1. Version, Startmenü, Prozess-Benutzer

Das Versions-/Stand-Prüfen ist ERLEDIGT (Claude). Du prüfst nur die Oberfläche, Benutzer test.admin:

1. Start, Suche "anlernen" -> **E-Rechnung anlernen** (Ordner GM-IT) anklicken.
2. Erwartet: Edge öffnet sich mit der Anlern-Oberfläche (GM-IT-Look, Seitenleiste "Vorlagen", "Anlernen").
3. PowerShell:

```powershell
Get-Process pythonw -IncludeUserName | Select Id,UserName
```

Erwartet: zwei Zeilen: ein pythonw als `NT-AUTORITÄT\SYSTEM` (der Überwacher) und ein pythonw als `SSPR\test.admin` (die Oberfläche). Nicht SYSTEM für die Oberfläche.

Melde: ok/nicht ok, Screenshot der Oberfläche.

## 2. Muster laden

Oberfläche -> **Neue Vorlage**, Name z. B. `werkstatt`.

a) Erstes Muster: Dateiauswahl -> `Desktop\lernmodus\Werkstatt-1.pdf`.

b) Zweites Muster über Druck (Edge-Druck, Bild-PDF mit Texterkennung):
1. `Werkstatt-2.pdf` mit Doppelklick in Edge öffnen (falls ein anderes Programm öffnet: Rechtsklick -> Öffnen mit -> Edge).
2. Strg+P -> Drucker **E-Rechnung** -> Drucken.
3. Nach ca. 10 bis 30 s liegt in `C:\E-Rechnung\Fehler\` ein PDF mit `.fehler.txt` ("keine Vorlage passt"). Prüfen:

```powershell
Get-ChildItem C:\E-Rechnung\Fehler | Sort LastWriteTime | Select -Last 4 Name
```

4. In der Oberfläche -> **Aus Fehler-Ordner übernehmen** -> das neue PDF wählen.

Erwartet: beide Muster als Seitenbild sichtbar. Melde: ok/nicht ok, ob der Fehler-Eintrag wie beschrieben entstand, Dauer bis zum Fehlerordner.

## 3. Markieren und Probelauf

1. Auf Muster 1 alle Pflichtfelder (Rechnungsnummer, Datum, Käufer, Summen netto/USt/brutto) und die Positionstabelle mit Rahmen markieren. Rahmen nicht knapp ziehen (Hinweis in der Oberfläche).
2. Bei den Mustern die Häkchen "Nummer, Datum und Käufer stimmen" setzen, wenn sie stimmen.
3. **Probelauf** klicken, Stoppuhr mitlaufen lassen.

Erwartet: beide Muster bestanden (grün), Summenabgleich ok, Mustang valid, Zeile "inkl. Probefahrt" ohne Fehler. Melde: ok/nicht ok, **Dauer des Probelaufs in Sekunden**, Screenshot des Ergebnisses.

## 4. Vorlage aktivieren (UAC)

1. **Vorlage aktivieren** klicken.
2. UAC-Abfrage erscheint, zeigt "Python". **Details anzeigen** klicken: Die Befehlszeile muss lauten `…\GM-IT\erechnung-konverter\…\python.exe -m erechnung vorlage aktivieren …`. Steht etwas anderes (anderes Programm, `-c`, fremde Datei): **Nein** und mir melden.
3. Admin-Konto wählen: `SSPR-SRV2\Administrator` (Passwort Passwortmanager; bei "Weitere Optionen" ggf. Benutzernamen eintippen) -> Ja.
4. Erwartet: Meldung "aktiv".

Prüfen (PowerShell, kein Admin nötig, Benutzer dürfen lesen):

```powershell
Get-Content "C:\Program Files\GM-IT\erechnung-konverter\vorlagen\angelernt\protokoll.txt"
Get-ChildItem "C:\Program Files\GM-IT\erechnung-konverter\vorlagen\angelernt"
```

Erwartet im Protokoll: Zeit, Benutzer `test.admin`, Admin `Administrator`, Aktion aktivieren, Name, SHA-256, Anzahl Muster 2. Melde: ok/nicht ok, Protokollzeile (ohne Kennwörter, davon gibt es keine), Screenshot der UAC-Details.

## 5. Dritte Rechnung ohne Neustart der Aufgabe

Beide Wege mit `Werkstatt-3.pdf`:

a) "Senden an": Rechtsklick auf `Werkstatt-3.pdf` -> Senden an -> **E-Rechnung**. (Fehlt der Eintrag, weil das Profil neu ist: abmelden, wieder anmelden und erneut versuchen; sonst als nicht ok melden.)

b) Edge-Druck: `Werkstatt-3.pdf` in Edge öffnen -> Strg+P -> Drucker **E-Rechnung**.

Nach ca. 30 bis 60 s prüfen:

```powershell
Get-ChildItem C:\E-Rechnung\E-Rechnungen | Sort LastWriteTime | Select -Last 6 Name,LastWriteTime
Get-ChildItem C:\E-Rechnung\Originale | Sort LastWriteTime | Select -Last 6 Name
Select-String -Path "C:\Program Files\GM-IT\erechnung-konverter\erechnung.log" -Pattern "Vorlagen neu geladen|Mustang: valid" | Select -Last 6
```

Erwartet: zwei neue E-Rechnungen (je PDF und XML) in `E-Rechnungen`, im Log "Vorlagen neu geladen" und "Mustang: valid"; beim Edge-Druck in `Originale` eine `.ocr.txt`. Melde: ok/nicht ok, ggf. Fehlerdatei aus `Fehler`.

## 6. Zweiter Benutzer (kurz)

1. Als test.admin: Port der Oberfläche holen:

```powershell
netstat -ano | findstr "127.0.0.1" | findstr LISTENING
```

(Der Port gehört zum pythonw der Oberfläche, PID aus Punkt 1.) Bei test.admin angemeldet lassen.
2. Schnelle Benutzerumschaltung (Windows-Taste, Benutzer wechseln) zu `SSPR\test.aktiv`, PowerShell, Port einsetzen:

```powershell
Invoke-WebRequest http://127.0.0.1:<port>/api/stand -UseBasicParsing
Invoke-WebRequest "http://127.0.0.1:<port>/start?t=falsch" -UseBasicParsing
```

Erwartet: beide mit Fehler 403. Melde: ok/nicht ok (je Aufruf der Statuscode).

## 7. Leerlauf 30 Minuten

Wieder zu test.admin. Notiere die Uhrzeit des letzten Klicks in der Oberfläche. Nichts mehr anfassen. Nach 31 Minuten:

```powershell
Get-Process pythonw -IncludeUserName | Select Id,UserName
```

Erwartet: nur noch der pythonw als SYSTEM. Wenn du nicht warten willst: Uhrzeit melden, ich schaue dann per NetLock nach (`Get-Process pythonw -IncludeUserName`). Melde: Uhrzeit letzter Klick.

## 8. Deaktivieren und Reaktivieren

Oberfläche neu starten (Startmenü "E-Rechnung anlernen").
1. Vorlage `werkstatt` -> **Deaktivieren** -> UAC (Details prüfen wie Punkt 4, hier `vorlage deaktivieren`) -> SSPR-SRV2\Administrator.
2. `Werkstatt-3.pdf` erneut per Edge-Druck auf **E-Rechnung** drucken. Erwartet: neuer Eintrag in `C:\E-Rechnung\Fehler` ("keine Vorlage passt"), keine neue E-Rechnung.
3. **Reaktivieren** -> UAC (`vorlage reaktivieren`) -> SSPR-SRV2\Administrator. Nochmal drucken. Erwartet: wieder eine E-Rechnung in `E-Rechnungen`.

Melde: ok/nicht ok je Schritt (1, 2, 3).

## 9. Update-Überleben (so knapp wie möglich)

Nicht jetzt: Claude braucht dafür eine weitere Freigabe (z. B. 0.2.2). Ich sage dir, wann du freigeben sollst. Danach nur:

```powershell
Get-Content "C:\Program Files\GM-IT\erechnung-konverter\stand.json"
Get-ChildItem "C:\Program Files\GM-IT\erechnung-konverter\vorlagen\angelernt" -Filter *.yml
```

und `Werkstatt-3.pdf` per Edge-Druck drucken. Erwartet: neue Version in stand.json, die yml ist noch da, neue E-Rechnung entsteht. Melde: ok/nicht ok.

## 10. Export

Oberfläche (Startmenü neu starten) -> Vorlage `werkstatt` -> **Für GM IT exportieren**.

```powershell
Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "erechnung-vorlage-*"
Get-Content (Get-ChildItem "$env:USERPROFILE\Downloads" -Filter "erechnung-vorlage-*.yml" | Select -Last 1).FullName -TotalCount 25
```

Erwartet: genau eine Datei `erechnung-vorlage-werkstatt-<datum>.yml`, keine PDFs im Download-Ordner, Inhalt nur Koordinaten, Ankertexte, Schlüsselwörter (keine Rechnungsdaten). Melde: ok/nicht ok, Dateiname.

## 11. einrichten.ps1 erneut

ERLEDIGT (Claude): Lauf aus `versionen\0.2.1\einrichten\einrichten.ps1` als SYSTEM, Exit 0, Ausgabe "Fertig. Drucker 'E-Rechnung' …; Startmenü: E-Rechnung anlernen". Einzige Meldung: "Senden an … gmdrucktest … fehlt - übersprungen" (verwaistes Profil, harmlos). Nichts zu tun.

## Am Ende an Claude zurück

Eine Zeile je Punkt 1 bis 8 und 10: `Punkt N: ok/nicht ok, HH:MM, Besonderheit`, dazu die Probelauf-Dauer (Punkt 3) und die Uhrzeit des letzten Klicks (Punkt 7). Punkt 9 kommt nach der nächsten Freigabe.
