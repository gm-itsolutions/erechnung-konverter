# Generische Erkennung – Plan (Nachtlauf 02./03.11.2026)

Auftrag Marvin (02.11.2026): Den Konverter mit möglichst vielen Rechnungsformaten „trainieren“. Ziel ist eine
**layoutunabhängige Erkennung** als **Vorschlagsquelle für den Lernmodus** (`docs/lernmodus/`).

## Global Constraints

- Die Erkennung erzeugt **keine** E-Rechnung. Der produktive Weg (`vorlagen.lies_rechnung` → Summenabgleich →
  CII → Mustang) bleibt der einzige Weg zur E-Rechnung. Ohne Vorlage weiter „keine Vorlage passt“.
- Ein Vorschlag gilt nur als **bestätigt**, wenn `modell.summenabgleich` besteht und Rechnungsnummer + Datum
  gefunden sind. Sonst ist er ein unbestätigter Vorschlag mit Grund.
- Echte Lexware-Rechnungen (`ERECHNUNG_TESTDATEN=/root/erechnung-testdaten`, `tests/test_lexware_echt.py`) bleiben
  exakt wie heute; die ganze Testsuite bleibt grün:
  `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest -q`.
- Testdaten nur unter `/root/erechnung-testdaten/` (Ordner 0700), **nie ins Repo**. Keine echten Personen- oder
  Firmendaten im Repo; Generator nur mit erfundenen Firmen, Test-IBANs.
- Keine neuen Laufzeit-Abhängigkeiten im Windows-Paket (nur stdlib + vorhandene: pdfplumber, lxml, factur-x, pyyaml).
  Werkzeuge unter `werkzeuge/` dürfen vorhandene Dev-Abhängigkeiten nutzen (reportlab, Pillow).
- Python 3.14, `Decimal` für Beträge, Stil wie im Repo (deutsche Namen, knappe Docstrings).
- Öffentliche Korpora nur mit offener Lizenz (Apache-2.0, MIT, CC-BY o. ä.); Lizenz und Quelle in
  `/root/erechnung-testdaten/korpus/QUELLEN.md` notieren.

## Task 1: Korpus erweitern

- `werkzeuge/fremdrechnungen.py`: mindestens 8 weitere Layouts (H …), die echte Programmstile nachahmen
  (Kassen-/Warenwirtschafts-Stil, Tabellen mit „Pos | Art.-Nr. | Bezeichnung | Menge | ME | EP | Rabatt % | Gesamt“,
  Steuerzeilen „MwSt 19 % auf 1.234,56“, ISO-Datum, Datum TT.MM.JJ, Monatsnamen, „Rechnung Nr.“, „Beleg-Nr.“,
  „Invoice No.“ englisch, Beträge mit „EUR“ hinten, ohne Tausenderpunkt, Brutto-Positionen mit enthaltener MwSt,
  Gutschrift-Hinweis, Positions-Rabatt, 7 %/19 % gemischt, mehrseitig, Kleinunternehmer). Je Layout 3 Exemplare +
  1 Bild-PDF (wie bisher), Sollwerte im bestehenden `.soll.json`-Format.
- Neuer Schalter `--varianten`: zusätzlich je Layout N weitere Exemplare (Seed-variiert), damit ein großer Korpus
  (≥ 200 PDFs) entsteht. Ziel `/root/erechnung-testdaten/fremd/`.
- `werkzeuge/korpus_holen.py`: lädt öffentliche Beispiel-Rechnungen (ZUGFeRD/Factur-X-PDFs mit eingebetteter XML,
  z. B. ZUGFeRD-Corpus, Mustang-Testdateien) nach `/root/erechnung-testdaten/korpus/`, erzeugt `.soll.json` aus der
  eingebetteten CII/UBL-XML (nummer, datum, netto, steuern, brutto, positionen soweit vorhanden), Lizenz prüfen.
  Bei fehlendem Netzzugang: sauber mit Meldung beenden.
- Tests: Generator erzeugt neue Layouts deterministisch; Soll-Summen konsistent; Sollwert-Ableitung aus einer
  kleinen eingebetteten Beispiel-XML (im Test erzeugt, nicht heruntergeladen).

## Task 2: Messwerkzeug + Ausgangswert

- `werkzeuge/korpus_messen.py`: läuft über alle `*.soll.json` unter einem oder mehreren Ordnern, liest das PDF
  (Text; Bild-PDF über `ocr.erkenne`, wenn Tesseract verfügbar, sonst als „übersprungen“ zählen) und vergleicht
  je Feld (nummer, datum, netto, ust je Satz, brutto, käufer-name, positionen-anzahl, positionen-netto) mit dem Soll.
- Zwei Verfahren: `vorlage` (heutiger Weg `lies_rechnung` + Summenabgleich) und `generisch` (Task 3,
  importiert, wenn vorhanden). Ausgabe: Tabelle je Feld/Layout + JSON-Bericht (`--json DATEI`).
- Kennzahlen: Trefferquote je Feld, „vollständig richtig“, „bestätigt“ (Summenabgleich ok), und
  **„bestätigt, aber falsch“** (muss 0 sein – sonst ist die Bestätigung wertlos).
- Ausgangswert messen (`vorlage`) und in `docs/generisch/messung.md` festhalten.

## Task 3: Generische Erkennung

- `erechnung/generisch.py`: `erkenne(text: str) -> Vorschlag` mit Feldern nummer, datum, leistungsdatum, faellig,
  kaeufer (Partei), positionen, summe_netto, steuern {satz: betrag}, summe_ust, summe_brutto, nachlaesse,
  je Feld die Fundstelle (Zeile) und `bestaetigt: bool`, `grund: str`.
- Verfahren (heuristisch, nur stdlib): Schlüsselwort-Wörterbuch (de/en) für Felder, Datumsformate
  (TT.MM.JJJJ, TT.MM.JJ, ISO, „2. November 2026“), Beträge über `modell.betrag`, Steuerzeilen mit Satz,
  Summenblock von unten, Positionszeilen = Zeilen mit Menge/Einzelpreis/Betrag; Auswahl der Kandidaten so,
  dass `summenabgleich` aufgeht. Käufer = Anschriftenblock mit PLZ-Zeile, der nicht der Verkäufer ist
  (Lieferanschrift nicht als Käufer).
- `vorschlag_aus_pdf(pdf, ocr=None)`: Text bzw. OCR-Lesarten wie `lies_rechnung`, erste bestätigte Lesart gewinnt.
- Iterativ gegen den Korpus (Task 2) verbessern; Unit-Tests mit kleinen Texten je Regel.

## Task 4: Einbindung + Doku

- CLI: `python -m erechnung vorschlag <pdf>` gibt den Vorschlag als JSON aus (ohne Konfig, ohne OCR-Pflicht).
- Fehlerdatei: Bei „keine Vorlage passt“ hängt `bearbeite` an die `.fehler.txt` einen Abschnitt
  „Vorschlag der generischen Erkennung (nicht verwendet)“ an (nummer, datum, brutto, bestätigt ja/nein). Fehler
  darin dürfen die Verarbeitung nie stören.
- Doku: `docs/generisch/messung.md` (Korpus, Ausgangswert, Endwert, Fehlklassen, Grenzen), README-Abschnitt,
  Verweis in `docs/lernmodus/spezifikation.md` (Vorschläge zum Vorbefüllen).
- Version `erechnung/__init__.py` → 0.1.8.
