# Testprotokoll

## VM 108 (Windows Server 2025), 0.1.0 über gm-update – 02.11.2026

Tasks 10 und 12 in einem Durchgang: 0.1.0 und gm-update 0.1.4 waren bereits freigegeben, deshalb hat `einrichten.ps1` die App gleich über gm-update installiert (keine Handinstallation). Steuerung als SYSTEM über NetLock → gm-pve-02 → `qm guest exec`. DNS über einen befristeten hosts-Eintrag (VM 105 nicht gestartet).

| Prüfpunkt | Ergebnis | Beleg |
|---|---|---|
| Setup-Material | bestanden | ZIP-SHA-256 `d50ebcdc…` = release.json; `einrichten\` im ZIP = Repo-Stand; gm-update.exe 0.1.4 SHA-256 `dffd462e…` = release.json |
| PowerShell-Syntax `einrichten.ps1` | bestanden | `Parser::ParseFile` → 0 Fehler |
| Einrichtung `einrichten.ps1 -TokenDatei … -Konfig …` | bestanden | keine Warnung, „Fertig. Drucker 'E-Rechnung' -> C:\E-Rechnung\Eingang\rechnung.pdf …“ |
| Drucker und Port | bestanden | `E-Rechnung`, Treiber „Microsoft Print To PDF“, Port `C:\E-Rechnung\Eingang\rechnung.pdf` (Lokaler Port), nicht freigegeben |
| Aufgabe `\GM-IT\E-Rechnung` | bestanden | SYSTEM, ServiceAccount, Highest; `aktuell\python\pythonw.exe -m erechnung ueberwachen --konfig "…\konfig.json"`; Auslöser Systemstart + alle 5 Min.; IgnoreNew, kein Zeitlimit, Neustart 999×/1 Min., Akku egal |
| Aufgabe `\GM-IT\Update erechnung-konverter` | bestanden | SYSTEM, täglich 03:00, `gm-update.exe lauf --konfig "…\gm-update.json" --verzoegerung 60m`, Limit 2 h, IgnoreNew |
| Installation über gm-update | bestanden | `stand.json` `"version": "0.1.0"`, `fehler` leer; `aktuell` = Junction → `versionen\0.1.0`; `gm-update.log` „aktualisiert auf 0.1.0“ |
| Überwacher | bestanden | `pythonw` läuft, `erechnung.log` „Überwachung gestartet: C:\E-Rechnung\Eingang“ |
| Rechte `C:\E-Rechnung` | bestanden | Besitzer Administratoren, Vererbung aus; SYSTEM/Admins Vollzugriff, Benutzer Lesen; `Eingang` zusätzlich Benutzer Ändern; Unterordner erben |
| Rechte `token`, `gm-update.json` | bestanden | nur SYSTEM und Administratoren, nicht geerbt |
| Eingang direkt (RE0146.pdf) | bestanden | `E-Rechnungen\RE0146.pdf` (269 446 B, factur-x XSD gültig) und `RE0146.xml`; Original in `Originale`. Beträge = Lexware-XML: Netto 1878.05, Steuer 356.83, Brutto 2234.88, 4 Positionen gleich |
| Druck als Benutzer (Out-Printer) | bestanden | Standardbenutzer per geplanter Aufgabe (Batch-Anmeldung): PDF kommt an, wird abgeholt, `Fehler\…rechnung.fehler.txt` „keine Vorlage passt zu diesem Layout“, Text im PDF erhalten |
| 5 Drucke direkt hintereinander | bestanden | 5 Fehlerpaare, Text „Auftrag 1“ … „Auftrag 5“ je einmal; kein Verlust, kein Überschreiben (Spooler arbeitet die Aufträge nacheinander ab, ca. 3,6 s Abstand) |
| Kontext und Eigentümer | geklärt | Der Spooler schreibt im Kontext des druckenden Benutzers: Besitzer der PDF ist der Benutzer, die `.fehler.txt` gehört SYSTEM (Überwacher). Benutzer brauchen also Ändern in `Eingang` (Abweichung A4 bestätigt) |
| Druck als SYSTEM | nicht möglich | Auftrag bleibt „Error, Printing, Retained“, keine Datei, Druckerstatus Fehler; ebenso mit Port in einem anderen Ordner. `PrintToFile` mit demselben Treiber geht als SYSTEM. Für Kunden ohne Bedeutung (Benutzer drucken), aber: Testdruck nie aus der RMM-Shell; hängende Aufträge mit `Remove-PrintJob` löschen |
| stopp/start aus `gm-update.json` | bestanden | stopp bei laufender und bei gestoppter Aufgabe Exit 0, `schtasks /End` bei gestoppter Aufgabe Exit 0, start Exit 0 → neuer `pythonw` |
| PDF aus einem Viewer drucken | nicht geprüft | ohne fremde Software nicht möglich; Druck aus einem echten Programm prüft Marvin |

### Update-Aufgabe per `schtasks /Run`

`schtasks /Run /TN "GM-IT\Update erechnung-konverter"` um 13:58:05 → Exit 0. Der Lauf endete erst nach rund 60 Min. (Zufallsverzögerung, siehe Befunde): `LastTaskResult 0`, `gm-update.log` „aktuell (0.1.0)“, `stand.json` unverändert 0.1.0 ohne Fehler. Ohne neue Version ruft gm-update stopp/start nicht auf, der Überwacher lief durchgehend weiter (gleiche PID). stopp/start selbst sind oben einzeln geprüft. Gegenprobe ohne Verzögerung: `gm-update.exe lauf --konfig …` direkt → Exit 0 nach 1 s, „aktuell (0.1.0)“.

### Befunde

- Der Handstart der Update-Aufgabe wartet ebenfalls zufällig bis 60 Min.: `--verzoegerung 60m` steht in der Aktion, nicht im Auslöser (gm-update `update/aufgabe_xml.go`). Task 12 Step 3 ging vom Gegenteil aus. Runbook ergänzt.
- Druck als SYSTEM über Microsoft Print to PDF auf einen Dateiport scheitert (siehe Tabelle). Runbook ergänzt.
- `einrichten.ps1` lief ohne Änderung durch.
