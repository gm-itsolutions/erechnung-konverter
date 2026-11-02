# erechnung-konverter – Spezifikation

- **Stand:** 02.11.2026, Version 1 (Durchstich für den Kundentermin am 03.11.2026); Ergänzung 02.11.2026: Senden an (3.3), Texterkennung (3.2)
- **Projekt:** ai-os `30-projekte/erechnung-konverter.md`, Teilprojekt 2 von gm-update
- **Repo:** `git.gm-itsolutions.de/gm-itsolutions/erechnung-konverter` (privat), Klon `/root/erechnung-konverter`
- **Plan:** `docs/plan/index.md`

## 1. Ziel

Marvin, wörtlich: „dass man eine blanke Rechnung als PDF drucken kann zum E-Rechnungs-Dienst und die E-Rechnung rauskommt“.

Ein Windows-PC hat einen Drucker **„E-Rechnung“**. Wer darauf eine Rechnung druckt, findet kurz danach im Ordner `E-Rechnungen` zwei Dateien:
- `<Rechnungsnummer>.pdf`: ZUGFeRD-PDF mit eingebetteter CII-XML, Profil EN16931
- `<Rechnungsnummer>.xml`: dieselbe XML einzeln

Passen die Summen nicht oder ist das Layout unbekannt, entsteht **keine** E-Rechnung. Das Original kommt dann mit einer Fehlerdatei samt Grund in den Ordner `Fehler`.

Getestet wird mit Marvins Lexware-Rechnungen. Das Layout von Prignitz Markt folgt nach dem Termin als **weitere Vorlage** (eine YAML-Datei, kein Code).

## 2. Abgrenzung erster Wurf

| Enthalten | Nicht enthalten (offen, Abschnitt 11) |
|---|---|
| Rechnung (Typ 380), EUR, Umsatzsteuer Kategorie S (z. B. 19 % und 7 %, auch gemischt), Rabatt auf Rechnungsebene (Betrag) | Gutschrift, Storno, Abschlag, Prozent-Rabatt, Rabatt/Zuschlag je Position, steuerfrei/Reverse Charge (§ 13b), Kleinunternehmer |
| ZUGFeRD-PDF (EN16931) + XML, XSD-Prüfung | PDF/A-3 (Ghostscript), XRechnung-Syntax mit Leitweg-ID |
| Vorlage je Layout (YAML) | Empfang/Prüfung eingehender E-Rechnungen |
| Installation und Update über gm-update | Versand per Mail, Monitoring-Anbindung |

## 3. Ablauf auf dem PC

```
Programm des Kunden ── druckt ──> Drucker "E-Rechnung" (Microsoft Print to PDF)
                                   │ lokaler Port = Datei C:\E-Rechnung\Eingang\rechnung.pdf
                                   ▼
Überwacher (pythonw.exe -m erechnung ueberwachen, geplante Aufgabe als SYSTEM)
  1. alle 0,5 s: *.pdf in Eingang → os.replace nach <Programmordner>\arbeit\<Zeitstempel>-<name>.pdf
  2. Text lesen (pdfplumber) → Vorlage wählen (Schlüsselwörter) → Felder/Positionen per Regex
  3. Verkäuferdaten aus konfig.json ergänzen
  4. Summenabgleich (Pflicht) ── Fehler ──> Fehler\<stempel>-<name>.pdf + .fehler.txt
  5. CII-XML (EN16931) bauen, XSD prüfen, mit factur-x ins PDF einbetten
  6. E-Rechnungen\<Nummer>.pdf + .xml, Original nach Originale\
```

### 3.1 Drucker und Port

- Treiber „Microsoft Print to PDF“, lokaler Port mit einem **Dateipfad** als Portname (`Add-PrinterPort -Name 'C:\E-Rechnung\Eingang\rechnung.pdf'`). Der Spooler schreibt jeden Auftrag ohne Rückfrage in genau diese Datei und **überschreibt** sie beim nächsten Auftrag.
- **Lösung:** Der Überwacher verschiebt die Datei sofort per `os.replace` in den Arbeitsordner (gleiches Laufwerk, atomar). Solange der Spooler die Datei noch schreibt, hält er sie offen; das Umbenennen scheitert dann unter Windows mit einer Freigabeverletzung (`PermissionError`) und wird beim nächsten Takt wiederholt. Ein gelungenes Verschieben heißt also: Auftrag fertig geschrieben. Zusätzlich muss das PDF auf `%%EOF` enden (letzte 1024 Byte), sonst Fehler „PDF unvollständig“.
- **Warum nicht anders:** Ein Port mit `PORTPROMPT:` fragt nach einem Namen (nicht unbeaufsichtigt). Ein eigener Port-Monitor oder Treiber wäre C-Code bzw. kostenpflichtig (Entscheidung 30.10.: nur Open Source). Je Auftrag eindeutige Namen kann der lokale Port nicht.
- **Restrisiko:** Zwei Aufträge direkt hintereinander: Der Spooler rendert den zweiten erst nach dem ersten (Sekunden), der Überwacher verschiebt binnen 0,5 s. Geprüft wird das auf der VM mit fünf Aufträgen in Folge (Task 10). Annahme **[auf VM prüfen]**: Der Spooler öffnet die Datei ohne `FILE_SHARE_DELETE`.
- Ob der Spooler die Datei als SYSTEM oder im Kontext des druckenden Benutzers schreibt, ist nicht belegt **[auf VM prüfen]**. Deshalb haben Benutzer im Ordner `Eingang` vorerst Ändern-Rechte (Abschnitt 6). Braucht der Spooler sie nicht, werden sie in Task 10 entfernt.
- Jedes PDF, das auf anderem Weg in `Eingang` landet (Kopieren, „Senden an“, Abschnitt 3.3), wird genauso verarbeitet: jede Datei mit Endung `.pdf` (Groß-/Kleinschreibung egal), nicht nur `rechnung.pdf`. Andere Dateien bleiben liegen.

### 3.2 Textlage beim Drucken

Ein Programm, das Text als Text druckt (GDI, Office, `Out-Printer`), liefert ein PDF mit Text. Programme, die Seiten als Bild drucken, liefern ein PDF ohne Text: belegt für **PDFs aus Edge** auf VM 108 (Marvin, 02.11.2026), ebenso SumatraPDF. Dafür gibt es zwei Wege:

1. **Senden an → E-Rechnung** (Abschnitt 3.3): Das Original-PDF mit Text kommt an, keine Texterkennung nötig. Bevorzugter Weg für vorhandene PDFs.
2. **Texterkennung (OCR) als Rückfall** (`erechnung/ocr.py`), wenn das PDF weniger als 20 Buchstaben/Ziffern enthält (`vorlagen.MIN_ZEICHEN`):
   - Jede Seite mit pypdfium2 (Abhängigkeit von pdfplumber, schon im Paket) als Graustufenbild mit 300 dpi rendern (längste Kante höchstens 6000 px), höchstens 20 Seiten.
   - `tesseract.exe <bild> <ausgabe> -l deu --psm 6 --dpi 300` per `subprocess` ohne Shell, ohne Konsolenfenster, Frist 120 s je Seite. Bilder und Text in einem temporären Ordner `ocr-*` im Arbeitsordner der App, danach gelöscht (Reste beim Start des Überwachers).
   - Text bereinigen: Tabellenrahmen `|`, doppelte Leerzeichen, Leerzeilen. **Ziffern werden nie geändert.**
   - Danach dieselbe Vorlagenlogik und derselbe Pflicht-Summenabgleich. Jeder Fehler endet mit „(per Texterkennung gelesen)“ in der Fehlerdatei.
   - Erfolg: Die E-Rechnung bettet die XML in das **Original-PDF (Bild)** ein, es bleibt die Sichtkomponente. Daneben `<Nummer>.ocr.txt` mit Hinweis und erkanntem Text; im Log „per Texterkennung gelesen“.
   - Tesseract fehlt (z. B. Entwicklung ohne Tesseract): Fehler „kein Text im PDF …, Texterkennung nicht verfügbar“.
   - **Grenze:** Der Summenabgleich sichert die Beträge, nicht Nummer, Daten und Käufer. Deshalb in der Vorlage: Nummer nur `RE\d+` und eine zweite Fundstelle (`nummer_kontrolle`, Überschrift „Rechnung RE…“) muss übereinstimmen; `O` statt `0` wird nur in Datumsangaben ersetzt. Mit `tessdata_fast` las Tesseract bei zwei von drei echten Rechnungen „REO0146“ statt „RE0146“ (beide Fundstellen gleich falsch) – darum `tessdata_best` (4.1) und das enge Nummernmuster, das so einen Fall zum Fehler macht.

Ergebnis auf gm-claude (Tesseract 5.5.0, `tessdata_best`): Die drei echten Lexware-Rechnungen RE0146, RE0148, RE0149 als Bild-PDF ohne Text (300 und 200 dpi) liefern Nummer, Netto, Steuer, Brutto, alle Positionsbeträge und Fälligkeit **identisch mit der Lexware-XML** (`tests/test_lexware_echt.py::test_ocr_wie_lexware`). Laufzeit rund 7 s je Seite.

### 3.3 Senden an

`einrichten.ps1` legt in jedem vorhandenen Benutzerprofil (`Win32_UserProfile`, ohne Systemprofile) und im Default-Profil (für neue Benutzer, Pfad aus `HKLM\…\ProfileList\Default`) die Verknüpfung `AppData\Roaming\Microsoft\Windows\SendTo\E-Rechnung.lnk` → `<Daten>\Eingang` an. Wiederholbar (wird überschrieben). Ist ein SendTo-Ordner eine Junction/ein Symlink, wird er mit Warnung übersprungen. Umgeleitete AppData-Ordner (Ordnerumleitung im Netz) werden nicht erfasst.

Halb kopierte Dateien: Der Explorer schreibt die Zieldatei unter ihrem endgültigen Namen und hält sie bis zum Ende offen (CopyFileEx, ohne `FILE_SHARE_DELETE` **[auf VM prüfen]**). `os.replace` scheitert dann wie beim Spooler mit einer Freigabeverletzung, der nächste Takt versucht es erneut. Greift das nicht, fehlt am Dateiende `%%EOF` (CopyFileEx legt die Zielgröße vorab an, das Ende ist noch leer) → Fehlerdatei „PDF unvollständig“; die Quelldatei des Benutzers bleibt unberührt. Ob „Senden an“ auf demselben Laufwerk kopiert oder verschiebt, ist **[auf VM prüfen]** (erwartet: kopieren). Namenskollisionen: Arbeitsdateien bekommen einen Zeitstempel mit Mikrosekunden, Ziele in `E-Rechnungen`, `Originale`, `Fehler` ein `-2`, `-3` … (`_frei`).

## 4. Komponenten

| Datei | Aufgabe |
|---|---|
| `erechnung/__init__.py` | `__version__` (setzt der Bau aus dem Tag) |
| `erechnung/__main__.py` | CLI: `--version`, `ueberwachen --konfig`, `umwandeln <pdf> --konfig` |
| `erechnung/modell.py` | Datenklassen `Partei`, `Position`, `Rechnung`; `betrag()`, `datum()`; `summenabgleich()` |
| `erechnung/vorlagen.py` | `pdf_text()`, `lade_vorlagen()`, `finde_vorlage()`, `lies_rechnung(…, ocr=None)` |
| `erechnung/ocr.py` | `tesseract()` (Aufruf finden), `erkenne(pdf, arbeit, aufruf)`, `bereinige()` |
| `erechnung/cii.py` | `erzeuge_cii()` (CII-XML, EN16931); Nachlass/Zuschlag als Kopf-`SpecifiedTradeAllowanceCharge` mit Steuersatz, `LineTotalAmount` = Σ Positionen, `Charge-`/`AllowanceTotalAmount`, `TaxBasisTotalAmount` = Netto (wie Lexware RE0158) |
| `erechnung/ueberwachen.py` | `Konfig`, `lade_konfig()`, `verarbeite()`, `schritt()`, `ueberwache()` |
| `erechnung/vorlagen/*.yml` | eine Vorlage je Layout |
| `release/bauen.sh`, `release/requirements-windows.txt` | Windows-ZIP auf Linux bauen |
| `einrichten/einrichten.ps1`, `einrichten/gm-update.json`, `einrichten/konfig.beispiel.json` | Einrichtung beim Kunden |
| `werkzeuge/` | nur gm-claude: Testdaten holen, Abgleich mit Lexware-XML, Mustang |

### 4.1 Technische Entscheidungen

| Entscheidung | Begründung |
|---|---|
| Windows-Embeddable-Python **3.14.10** (amd64) | 3.13 ist seit Oktober 2026 nur noch im Sicherheitsmodus und hat keine Windows-Binärdateien mehr (3.13.18 ohne Embed-ZIP, geprüft 02.11.2026); 3.14 bekommt Bugfixes bis Oktober 2027 und ist dieselbe Version wie auf gm-claude. Für 3.14 liegen win_amd64-Wheels für alle Abhängigkeiten vor (geprüft per `pip download --platform win_amd64 --python-version 3.14 --only-binary=:all:`: lxml 6.1.3, pillow 13.0.0, pypdfium2 5.14.0, cryptography 50.0.2, pyyaml 6.0.3). 3.15 ist zu jung. |
| **Eigene Regex-Vorlagen (YAML, Format angelehnt an invoice2data)** statt invoice2data | invoice2data ließe sich installieren (Wheel vorhanden), aber: Beträge werden als `float` gelesen (Feldnamen `amount*` automatisch), Pflichtfeld `amount`, zehn zusätzliche Pakete (requests, regex, stdnum, dateutil …). Für Geld und einen exakten Summenabgleich braucht es `Decimal`; die eigene Auswertung ist rund 100 Zeilen, voll unter Test und hängt nur an pyyaml. Die Schlüssel (Schlüsselwörter, Felder, Positionen mit start/ende/zeile) entsprechen invoice2data, Vorlagen lassen sich übertragen. |
| pdfplumber für den Text | reines Python (pdfminer.six), kein poppler; `layout` je Vorlage wählbar. |
| CII selbst mit lxml bauen, factur-x 7.9 nur zum Einbetten und für die XSD-Prüfung | factur-x erzeugt keine XML aus Daten. `generate_from_binary(..., flavor='factur-x', level='en16931', check_xsd=True)` prüft beim Einbetten. |
| Profil EN16931 (Comfort), Guideline-ID `urn:cen.eu:en16931:2017` | Vorgabe; reicht für B2B nach § 14 UStG. |
| Geplante Aufgabe als SYSTEM, Start beim Systemstart **und** alle 5 Min. (`MultipleInstances IgnoreNew`), dazu Neustart bei Fehler | „Neustart bei Fehler“ greift laut Aufgabenplanung nicht sicher, wenn der Prozess mit Exit-Code ≠ 0 endet **[n. o. b.]**. Der Wiederholungsauslöser startet einen beendeten Überwacher spätestens nach 5 Min. neu, ein laufender wird nicht doppelt gestartet. Kein NSSM, kein pywin32. |
| `pythonw.exe` als Aufgabe | kein Konsolenfenster. |
| Programm- und Konfigurationsdateien unter `%ProgramFiles%\GM-IT\erechnung-konverter` | wie gm-update: Benutzer können dort nichts vorab anlegen. `konfig.json`, `arbeit\` und `erechnung.log` liegen neben `versionen\`, ein Update ersetzt sie nicht. |
| Stopp/Start über PowerShell `Stop-/Start-ScheduledTask` statt `schtasks /End` | Scheitert `stopp`, verwirft gm-update die neue Version. `schtasks /End` meldet bei nicht laufender Aufgabe womöglich einen Fehler **[n. o. b.]**; `Stop-ScheduledTask` ist dann still. Auf der VM geprüft (Task 10). |
| Validierung mit **Mustang-CLI** auf gm-claude (Java 21 vorhanden), in der CI nur XSD über factur-x | Mustang prüft XSD **und** EN16931-Schematron. Der CI-Runner hat kein Java; Mustang je Lauf zu laden lohnt nicht. Mustang-Lauf ist Teil von Task 8 und vor jeder Freigabe. |
| **Tesseract 5.5.3 aus conda-forge (win-64)** statt UB-Mannheim-Installer | conda-forge: jede Datei (`.conda`) mit SHA-256 aus der Repodata, auf Linux mit der Python-Standardbibliothek entpackbar (zip + `tarfile` mit zstd, Python 3.14), Abhängigkeiten reproduzierbar aufgelöst (py-rattler) und in `release/tesseract-windows.txt` fest gepinnt. Der UB-Mannheim-Installer ist ein NSIS-Setup (7z im CI nötig), bündelt seine DLLs ohne einzelne Prüfsummen und hat keine von uns prüfbare Herkunftskette außer dem Hash der Gesamtdatei. `libarchive` in der lgpl-Variante (die gpl-Variante zieht lzo, GPL-2.0). Ins Paket kommt nur die Importhülle von `tesseract.exe` (31 Dateien, mit objdump bestimmt; `conda_entpacken.py` bricht ab, wenn eine fehlt) plus alle Lizenztexte. |
| **`deu.traineddata` aus `tessdata_best`** (Commit `e12c65a…`, 8,6 MB) statt `tessdata_fast` (1,5 MB) | Gemessen an den drei echten Rechnungen als Bild-PDF: `best` liest alle Nummern und Beträge richtig, `fast` liest „RE0146“ als „REO0146“ und verliert eine Position (Summenabgleich fängt es, aber dann gibt es keine E-Rechnung). Laufzeit `best` rund 7 s je Seite, für Einzelrechnungen unkritisch. |
| Echte Testdaten **außerhalb des Repos** in `/root/erechnung-testdaten/` (0700), synthetische im Repo | Die Lexware-Rechnungen enthalten Namen und Anschriften von Marvins Kunden. Tests mit echten Daten laufen nur, wenn `ERECHNUNG_TESTDATEN` gesetzt ist (gm-claude), sonst übersprungen. Die CI testet mit einem synthetischen Text im selben Layout (Namen ersetzt) und einem mit reportlab erzeugten PDF. |

## 5. Vorlagen

Eine YAML-Datei je Layout in `erechnung/vorlagen/`. Format (Beispiel, die echten Regexe entstehen in Task 4 aus dem echten Text):

```yaml
name: lexware-gm-it
schluesselwoerter: ["GM IT Solutions", "Rechnungsnr"]   # alle müssen vorkommen
layout: false                                           # pdfplumber extract_text(layout=...)
felder:                                                 # je eine Gruppe; Pflicht: nummer, datum, summe_netto, summe_brutto
  nummer: 'Rechnungsnr\.\s*(RE\d+)'
  datum: 'Rechnungsdatum\s+(\d{2}\.\d{2}\.\d{4})'
  leistungsdatum: 'Leistungsdatum\s+(\d{2}\.\d{2}\.\d{4})'     # optional
  faellig: 'zahlbar bis\s+(\d{2}\.\d{2}\.\d{4})'              # optional
  zahlungsziel_tage: '^Zahlungsziel (\d+) Tage'                # optional, ohne faellig: datum + N Tage
  summe_netto: 'Gesamtbetrag netto\s+([\d.,]+)'             # auch Liste: das erste Muster, das passt
  summe_ust: 'Umsatzsteuer \d+ %\s+([\d.,]+)'                  # optional, sonst aus steuern
  summe_brutto: 'Gesamtbetrag brutto\s+([\d.,]+)'
steuern: 'Umsatzsteuer (?P<satz>\d+) %\s+(?P<betrag>[\d.,]+)' # optional, alle Treffer
nachlaesse: '^abzgl\. (?P<grund>.+?)\s+-?(?P<betrag>[\d.,]+)$'   # optional, alle Treffer; satz optional
kaeufer: '(?s)^(?P<name>.+?)\n(?P<strasse>.+?)\n(?P<plz>\d{5}) (?P<ort>.+?)\n'
positionen:
  start: 'Pos\.\s+Beschreibung'
  ende: 'Gesamtbetrag netto'
  zeile: '^(?P<nr>\d+)\s+(?P<bezeichnung>.+?)\s+(?P<menge>[\d,]+)\s+(?P<einheit>\S+)\s+(?P<einzelpreis>[\d.,]+)\s*€\s+(?P<netto>[\d.,]+)\s*€$'
  ust_satz: 19                     # wenn die Zeile keine Gruppe ust_satz hat
  ignorieren: ['^Seite \d+']       # Zeilen, die nie Fortsetzung sind
einheiten: {Stunde: HUR, Std.: HUR, Stück: H87, Pauschal: C62}   # sonst C62
```

`nachlaesse`: Nachlässe auf Rechnungsebene (Betrag ohne Vorzeichen, Gruppe `grund`, optional `satz`). Lexware druckt „Zwischensumme (netto)“, „abzgl. Rabatt -71,00“, „Gesamt (netto)“ ohne Steuersatz; Netto ist dann „Gesamt (netto)“ (Liste in `summe_netto`). Prozent-Rabatte und Zuschläge erkennt die Lexware-Vorlage nicht (nicht belegt). Das Modell kennt auch Zuschläge (`Nachlass(zuschlag=True)`).

Optional `felder.nummer_kontrolle`: zweite Fundstelle der Nummer; ist der Schlüssel gesetzt, muss sie gefunden werden und gleich sein (sonst „Rechnungsnummer uneinheitlich gelesen“). Schlüsselwörter werden ohne Leerzeichen verglichen. `betrag()` liest `€`/`EUR`, Leerzeichen und einen Punkt vor genau zwei Endziffern als Dezimalzeichen (`1.557.21`), `datum()` ersetzt `O` durch `0`. Die Vorlage `lexware-gm-it.yml` ist auf Texterkennung abgestimmt (Abschnitt 3.2).

Regeln: Genau eine Vorlage muss passen, sonst Fehler („keine Vorlage“ / „mehrere Vorlagen: a, b“). Zeilen zwischen `start` und `ende`, die nicht auf `zeile` passen, nicht leer sind und nicht unter `ignorieren` fallen, werden an die Bezeichnung der vorigen Position angehängt. Endet die Bezeichnung auf Wort + `-`, gilt: Folgezeile beginnt klein → Silbentrennung, Strich entfällt („Dokumentenscan-“ + „ner“); beginnt sie mit „und/oder/bzw./sowie“ → Strich bleibt, mit Leerzeichen („Einzugs- und …“); sonst Strich bleibt ohne Leerzeichen („E-Mail-“ + „Postfach“). Ein mehrzeiliger Käufername (Zusatzzeile unter der Firma) wird nicht zusammengesetzt, nur die erste Zeile gilt als Name. Zusätzliche Vorlagen ohne Release: Ordner `vorlagen\` neben `konfig.json` (nur Administratoren schreiben).

## 6. Ordner und Rechte (Windows)

| Pfad | Inhalt | Rechte |
|---|---|---|
| `%ProgramFiles%\GM-IT\erechnung-konverter\` | gm-update (`gm-update.exe`, `gm-update.json`, `token`, `stand.json`, `versionen\`, `aktuell`), `konfig.json`, `vorlagen\`, `arbeit\`, `erechnung.log` | geerbt von Program Files (Benutzer lesen/ausführen); `gm-update.json`/`token` nur SYSTEM+Admins (macht gm-update) |
| `C:\E-Rechnung\` (konfigurierbar) | Wurzel | Besitzer Administratoren, Vererbung aus, SYSTEM/Admins Vollzugriff, Benutzer Lesen |
| `…\Eingang` | Port-Datei | zusätzlich Benutzer Ändern (bis Task 10 klärt, ob nötig) |
| `…\E-Rechnungen`, `…\Originale`, `…\Fehler` | Ergebnisse | Benutzer Lesen |

`einrichten.ps1` setzt Besitzer und ACL auch dann, wenn ein Ordner schon existiert (ein Standardbenutzer kann unter `C:\` Ordner vorab anlegen und wäre sonst Besitzer). Der Überwacher bricht ab, wenn einer der konfigurierten Ordner eine Junction/ein Symlink ist, legt Ergebnisdateien nur neu an (`open(..., 'xb')`) und verschiebt nur innerhalb desselben Laufwerks (beim Start geprüft).

## 7. `konfig.json`

```json
{
  "eingang": "C:\\E-Rechnung\\Eingang",
  "ausgabe": "C:\\E-Rechnung\\E-Rechnungen",
  "originale": "C:\\E-Rechnung\\Originale",
  "fehler": "C:\\E-Rechnung\\Fehler",
  "verkaeufer": {"name": "GM IT Solutions", "strasse": "…", "plz": "…", "ort": "Pritzwalk", "land": "DE",
                 "ust_id": "DE…", "steuernummer": "", "email": "…", "iban": "DE…", "bic": "…"}
}
```

`arbeit` ist immer `<Ordner der konfig.json>\arbeit`, das Log `<Ordner der konfig.json>\erechnung.log` (1 MB, 3 Dateien). Pflicht: `verkaeufer.name`, `ust_id` oder `steuernummer`, `iban`. Keine Zugangsdaten in der Datei.

## 8. Summenabgleich (Pflicht)

In `modell.summenabgleich(r)`, alle Beträge `Decimal`, Rundung kaufmännisch (`ROUND_HALF_UP`) auf 2 Stellen:

1. Mindestens eine Position.
2. Je Position: `|runde(menge × einzelpreis) − netto| ≤ 0,01`.
3. `Σ netto der Positionen − Σ Nachlässe + Σ Zuschläge == summe_netto` (exakt). Ein Nachlass ohne Steuersatz gilt nur bei genau einem Satz; bei mehreren → Fehler „ohne Steuersatz bei mehreren Steuersätzen: Aufteilung unklar“ (wie Lexware dann aufteilt, ist nicht belegt). Ein Satz, den keine Position hat → Fehler.
4. Je Steuersatz: `basis = Σ netto − Nachlässe + Zuschläge dieses Satzes`, `steuer = runde(basis × satz / 100)`. Steht der Satz auf der Rechnung (`steuern`), muss `|gedruckt − berechnet| ≤ 0,01` sein (Toleranz wie EN16931 BR-CO-17), in die XML geht der gedruckte Wert.
5. `Σ steuer == summe_ust` (wenn gedruckt) und `summe_netto + Σ steuer == summe_brutto` (exakt).
6. Steuersatz 0 % → Fehler „im ersten Wurf nicht unterstützt“.

Jede Verletzung → `SummenFehler` mit Klartext (z. B. „Netto: Positionen 1.190,00 ≠ Rechnung 1.200,00“) → Fehlerdatei, keine E-Rechnung.

## 9. Installation und Update (gm-update)

- Art `datei`, ZIP `erechnung-konverter-<v>-windows-amd64.zip` mit `python\` (Embeddable + `Lib\site-packages`), `app\erechnung\`, `einrichten\`, `tesseract\` (`tesseract.exe`, DLLs, `tessdata\deu.traineddata`, `lizenzen\`) und `THIRD-PARTY.txt`. Größe 0.1.x ohne Tesseract 45,8 MB, mit 76,5 MB (Bau 02.11.2026). `python314._pth` enthält `python314.zip`, `.`, `Lib\site-packages`, `..\app`.
- `gm-update.json` (in `einrichten/`):
  - `probe`: `["aktuell/python/python.exe", "-m", "erechnung", "--version"]` – importiert alle Abhängigkeiten, Frist 60 s
  - `stopp`/`start`: `Stop-`/`Start-ScheduledTask -TaskPath '\GM-IT\' -TaskName 'E-Rechnung'`
- Eigenes `gm-update.exe` als SYSTEM-Aufgabe `GM-IT\Update erechnung-konverter` (legt `gm-update installieren` an). Version **0.1.4** (mit PR #6: Token und Konfiguration mit eingeschränkter DACL angelegt, Ordnerprüfung vor dem Anlegen, ProgramFilesDir aus HKLM).
- Lesetoken je Kunde `update-<kunde>`, im Test `update-test` (`/root/.config/gm-it-os/update-test.token`).
- CI: `.forgejo/workflows/release.yml` nach gm-update-Vorlage, `release/bauen.sh` lädt Python-Embed mit fester SHA-256 und installiert Wheels mit `--require-hashes --no-deps --only-binary=:all: --platform win_amd64 --python-version 3.14 --target`, lädt die conda-Pakete aus `release/tesseract-windows.txt` und `deu.traineddata` (Commit und SHA-256 in `bauen.sh`) und bricht bei jeder abweichenden Prüfsumme ab.

## 10. Grundschutz-Abgleich

Maßstab: ai-os `40-wissen/bsi-grundschutz-plusplus.md`, GM-Arbeitsregel. **Katalogversion 2026-10-22** (Stand-der-Technik-Bibliothek, Commit `160c177`); vor der Abnahme auf neuere Version prüfen.

**Schutzbedarf** (je Geschäftsprozess „Rechnung stellen“ beim Kunden):
- Integrität **normal**: Ein falscher Betrag in der XML wäre ein steuerlich relevanter Fehler, wird aber durch den Pflicht-Summenabgleich und die Prüfung verhindert; das sichtbare PDF bleibt Teil der E-Rechnung. Die Update-Kette (Code als SYSTEM) erbt den Schutzbedarf **hoch** und die Maßnahmen aus gm-update (Spezifikation Abschnitt 10).
- Vertraulichkeit **normal**: Rechnungsdaten des Kunden, keine besonderen Kategorien personenbezogener Daten.
- Verfügbarkeit **normal**: Fällt der Dienst aus, verschickt der Kunde die Rechnung wie bisher bzw. später.

Berührte Praktiken: KONF, BER, DET, NOT, ASST, DEV, TEST. Grundlagen-Block `<P>.1.1`–`<P>.1.2` (Doku, Zuständigkeit): diese Spezifikation, Runbook `docs/einrichten.md`, Zuständigkeit GM IT (Marvin).

| ID | Anforderung | Umsetzung |
|---|---|---|
| KONF.8.1 / KONF.8.2 | Automatische Prüfung / Updates der Anwendung | gm-update täglich, signiert, Probe, Rückweg |
| DET.5.10 (GM-Standard E3) | Zeitnahes Patchmanagement | Freigabe → Gerät binnen ca. 25 h; Python/Pakete fest gepinnt, Aktualisierung = neue Version |
| DET.5.10.2 | Überwachung der Updates | `stand.json`; Anbindung ans Monitoring offen (A3) |
| BER.4.1 | Geringste Berechtigungen | Benutzer: Programmordner nur lesen, Ergebnisse nur lesen, Eingang ändern. Überwacher läuft als SYSTEM → Abweichung A1 |
| BER.5.10 | Zugriffsbeschränkung auf Authentifizierungsmittel | Update-Token nur SYSTEM/Admins (gm-update), nur `read:package` |
| KONF.7.9 | Einschränkung der Installation | Installation nur als Administrator, nur unter `%ProgramFiles%` |
| DLS.2.2 | Transportverschlüsselung | Downloads nur HTTPS mit Zertifikatsprüfung (gm-update, CI) |
| DET.3.1 | Protokollierung | `erechnung.log` je Datei: Eingang, Vorlage, Ergebnis/Fehler; `gm-update.log` |
| NOT.4.15 | Wiederherstellungsweg | Runbook `docs/einrichten.md`: Neuinstallation mit `einrichten.ps1`, vorige Version über gm-update-Rückweg; Originale bleiben in `Originale` |
| ASST.2.3 | Inventar der Anwendungen | Version in `stand.json`; Python- und Paketversionen in `release/requirements-windows.txt` |
| DEV / TEST (IDs im Katalog nachschlagen **[n. o. b.]**) | Sichere Entwicklung, Tests vor Freigabe | pytest in der CI, Mustang-Prüfung vor jeder Freigabe, Lieferkette: Hashes für Python-Embed, alle Wheels, alle Tesseract-Pakete und `deu.traineddata` |
| ASST.2.3 / DEV (Lieferkette) | **Neue Fremdsoftware Tesseract** (Freigabe Marvin, 02.11.2026) | Herkunft: conda-forge win-64 (`https://conda.anaconda.org/conda-forge/win-64/…`), 24 Pakete mit SHA-256 aus der Repodata in `release/tesseract-windows.txt`; Tesseract 5.5.3 (`he87eeb8_0`, SHA-256 `edbe2455…e024`); `deu.traineddata` aus `github.com/tesseract-ocr/tessdata_best`, Commit `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, SHA-256 `8407331d…f0d06e`. Lizenzen: Apache 2.0 (Tesseract, tessdata, OpenSSL, LERC), sonst BSD/MIT/zlib-artig, libiconv LGPL-2.1 als eigene DLL; Liste `THIRD-PARTY.txt`, Texte in `tesseract\lizenzen\`. Aktualisierung nur mit neuer Pinliste und neuem Release |
| X.1.1.2 / BER.3.6 | Zuständigkeiten, Admin-Konten | Einrichtung nur durch GM IT mit Admin-Konto; keine eigenen Konten der App |

**Abweichungen:**

| Nr | ID | Abweichung | Grund | Art |
|---|---|---|---|---|
| A1 | BER.4.1 | Überwacher läuft als SYSTEM und liest ungeprüfte PDFs (Parser pdfminer) | Vorgabe Marvin; als `LOCAL SERVICE` wäre das Restrisiko kleiner (eine Zeile in `einrichten.ps1` + Rechte auf Daten- und Arbeitsordner). Frage an Marvin | temporär |
| A2 | – (Archivierung, GoBD) | Keine PDF/A-3 | Ghostscript nicht im ersten Wurf; ZUGFeRD-Empfänger akzeptieren in der Praxis meist auch Nicht-PDF/A, Mustang meldet das als Fehler der PDF-Prüfung | temporär |
| A3 | DET.5.10.2 | Keine Monitoring-Anbindung von `stand.json` und Fehlern | Durchstich zuerst | temporär |
| A4 | BER.4.1 | Benutzer haben Ändern-Recht in `Eingang` | Spooler-Kontext unbelegt (3.1) | temporär, Klärung in Task 10 |

**Restrisiken:** Manipuliertes PDF könnte eine Lücke im Parser als SYSTEM ausnutzen (A1); mit der Texterkennung kommen pdfium (Rendern) und Tesseract/Leptonica (liest nur das selbst erzeugte PNG) hinzu, ebenfalls als SYSTEM. Begrenzung: höchstens 20 Seiten, 6000 px, 120 s je Seite. Per Texterkennung gelesene Nummer, Daten und Käufer sichert kein Summenabgleich (Gegenmaßnahmen 3.2, Hinweisdatei `.ocr.txt`). Jeder lokale Benutzer kann eine E-Rechnung aus einem beliebigen PDF erzeugen lassen (gewollt, entspricht dem Drucken).

## 11. Offene Punkte

1. PDF/A-3 mit Ghostscript (A2).
2. Prignitz-Markt-Vorlage nach dem Termin 03.11.2026 (Muster-PDFs, Rechnungsprogramm, Windows-Version).
3. Weitere Fälle: Gutschrift (381), Prozent-Rabatt, Rabatt bei gemischten Steuersätzen (Lexware-Aufteilung prüfen), Rabatt je Position, steuerfrei/Reverse Charge, Kleinunternehmer.
4. Monitoring (A3), Konto `LOCAL SERVICE` (A1).
5. XRechnung (UBL/CII mit Leitweg-ID) für öffentliche Auftraggeber.
6. Empfang eingehender E-Rechnungen (Projektziel Teil 2).
7. VM 108: Texterkennung mit dem gepackten `tesseract.exe` (DLL-Hülle, Laufzeit als SYSTEM), Druck aus Edge Ende-zu-Ende, „Senden an“ (kopiert oder verschiebt? Freigabeverletzung bei Explorer-Kopie?), Profil neuer Benutzer.

## 12. Abnahme Durchstich

1. pytest grün in der CI; Mustang auf gm-claude: XML der drei Lexware-Rechnungen ohne Fehler (XSD + Schematron).
2. Beträge der erzeugten XML für RE0146, RE0148, RE0149 identisch mit Lexware-XML (Netto, Steuer, Brutto, je Position netto).
3. Tag `v0.1.0`, CI lädt Release hoch, Marvin gibt frei.
4. Auf VM 108: `einrichten.ps1` richtet alles ein, Druck auf „E-Rechnung“ → `E-Rechnungen\RE….pdf/.xml`; falsche Summe → `Fehler\…fehler.txt`.
5. Update auf eine höhere Version über gm-update (Probe, Stopp, Start) läuft durch.
