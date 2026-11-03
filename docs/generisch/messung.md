# Messung: Ausgangswert Verfahren `vorlage`

Stand 03.11.2026, vor der generischen Erkennung. Werkzeug: `werkzeuge/korpus_messen.py`.

```
/root/.venvs/erechnung/bin/python werkzeuge/korpus_messen.py /root/erechnung-testdaten/fremd /root/erechnung-testdaten/korpus --json /root/erechnung-testdaten/messung/vorlage.json
/root/.venvs/erechnung/bin/python werkzeuge/korpus_messen.py <leerer Ordner> --lexware   # echte Lexware-Rechnungen
```

Laufzeit rund 5,5 Minuten auf 2 Kernen (Bild-PDFs: je vier Lesarten Tesseract). JSON-Berichte liegen außerhalb des
Repos unter `/root/erechnung-testdaten/messung/`.

## Korpus

| Ordner | Rechnungen | davon Bild-PDF |
|---|---:|---:|
| `fremd` (Generator, Layouts A–O je 16) | 240 | 15 |
| `korpus/zugferd-corpus` (öffentlich) | 123 | 0 |
| `korpus/mustang` (öffentlich) | 8 | 0 |

Alle 371 wurden gemessen (Tesseract vorhanden, keine übersprungen). Felder, die im Soll fehlen (korpus: 28 ohne
Steuern, 11 ohne Positionen), zählen als „nicht bewertbar“, nicht als falsch. Beträge und Sätze werden numerisch
verglichen, Käufername ohne Groß-/Kleinschreibung und Mehrfachleerzeichen.

## Ergebnis `vorlage`

| Feld | fremd (240) | zugferd-corpus (123) | mustang (8) |
|---|---:|---:|---:|
| nummer, datum, netto, ust, brutto, käufer, Positionen (Anzahl, netto) | 0 | 0 | 0 |

Jede Rechnung scheitert mit „keine Vorlage passt zu diesem Layout“: Die mitgelieferte Vorlage `lexware-gm-it.yml`
erkennt nur Lexware-Rechnungen von GM IT Solutions, andere Layouts kennt der heutige Weg (bewusst) nicht.

| Kennzahl | Wert |
|---|---:|
| vollständig richtig | 0 von 371 |
| bestätigt (Summenabgleich ok) | 0 |
| **bestätigt, aber falsch** | **0** |

## Echte Lexware-Rechnungen (Gegenprobe)

RE0146, RE0148, RE0149, RE0158: Vorlage liest, Summenabgleich besteht, Nummer, Netto, Brutto und Positionsbeträge
stimmen mit `RE*.lexware.xml` überein: **4 von 4 ok**.

## Verfahren `generisch`: Endstand

Stand 03.11.2026, Modul `erechnung.generisch`. Messung wie oben mit `--verfahren generisch`, Berichte
`generisch-final.json` (mit Texterkennung, alle 371) und `generisch-r12.json` (`--ohne-ocr`, 356 Text-PDFs).
Die Erkennung dient nur als Vorschlag (Fehlerdatei, Lernmodus); sie erzeugt keine E-Rechnung.

### Vorher / Nachher

| Kennzahl | `vorlage` (Ausgangswert) | `generisch` ohne OCR (356) | `generisch` mit OCR (371) |
|---|---:|---:|---:|
| vollständig richtig | 0 | 267 | **276** |
| bestätigt (Summenabgleich ok) | 0 | 196 | **204** |
| bestätigt, Kernfeld falsch | 0 | 0 | **0** |
| bestätigt, aber ein anderes Feld falsch | 0 | 3 | **3** |

Je Ordner (vollständig richtig / bestätigt / Kern falsch / aber falsch), mit OCR:

| Ordner | gemessen | Ergebnis |
|---|---:|---|
| `fremd` | 240 | 234 / 171 / 0 / 0 |
| `korpus/zugferd-corpus` | 123 | 41 / 33 / 0 / 3 |
| `korpus/mustang` | 8 | 1 / 0 / 0 / 0 |

Feldtreffer mit OCR (richtig von bewertbar): Nummer 331/371, Datum 327/371, Netto 340/370, USt 338/362,
Brutto 345/371, Käufer 308/371, Positionen (Anzahl) 311/360, Positionen (netto) 304/360.
Echte Lexware-Rechnungen: unverändert 4 von 4 über die Vorlage (der produktive Weg wurde nicht angefasst).

### Sicherheitskennzahlen

- **Bestätigt mit falschem Kernfeld** (Nummer, Datum, Netto, USt, Brutto): 0 von 204, mit und ohne OCR.
  Das ist die Zahl, auf die es ankommt: Ein bestätigter Vorschlag hatte im Korpus nie eine falsche Summe, Nummer
  oder falsches Datum.
- Bestätigt Bedingung: Nummer und Datum gefunden, Nummer beschriftet oder an zwei Stellen belegt, Steuerzeilen
  arithmetisch stimmig, `modell.summenabgleich` besteht.
- Nur 3 von 204 bestätigten haben ein Nicht-Kernfeld falsch (Fehlklassen unten).
- **Abweichung vom Planziel „bestätigt, aber falsch = 0“:** Für die Kernfelder ist es erreicht
  (`bestaetigt_kern_falsch` = 0), der Gesamtwert ist 3. Alle drei betreffen Nicht-Kernfelder (Käufername ohne
  Leerzeichen im PDF-Text; ein öffentliches Muster ohne Netto je Zeile im Soll). Akzeptiert, weil die Erkennung nur
  Vorschläge macht und nie eine E-Rechnung erzeugt.

### Fehlklassen

Bestätigt, aber falsch (3):
- Soll ohne Positionsnetto (`…Intarsys_ZUGFeRD_1p0_BASIC_Einfach.pdf`): Das XML hat kein `netto` je Position.
- PDF-Text ohne Leerzeichen, Käufer „KundenAGMitte“ statt „Kunden AG Mitte“ (zwei symtrax-Beispiele, Block richtig).

Nicht bestätigt, bewusst:
- Grenzen des Summenabgleichs, siehe unten.
- Zerrissener PDF-Text („Nr. 4 71102 vom 0 5.03.2018“): Nummer und Datum werden nicht geraten.
- Nummer nur einmal und ohne Beschriftung, oder mehrdeutig (Vertragsnummer neben Rechnungsnummer).
- Positionen unvollständig: Betrag passt nicht zu Menge × Preis, Zusatzzeilen, mehrseitige Kostenrechnung, Rechnung
  ohne Positionstabelle.
- Französische Datumsangaben ohne erkanntes Datumsfeld.

### Grenzen

- **Layouts F, K, L, O werden nie bestätigt**, weil `modell.summenabgleich` sie nicht abbildet: Steuersatz 0 % (F, O;
  auch innergemeinschaftliche Lieferung u. ä. im öffentlichen Korpus), Bruttopreise je Position (K), Gutschrift/Storno
  mit negativen Summen (L). Der Vorschlag wird trotzdem angezeigt, mit Grund „nicht bestätigt“.
- Positiv gedruckte Gutschriften (Betrag ohne Minus) erkennt das Verfahren nicht als solche und bestätigt sie nicht.
- Käufer ist das schwächste Feld (Anschriftenblöcke über die PLZ-Zeile); ein falscher Käufer verhindert die
  Bestätigung nicht. Nummer, Datum und Käufer sichert kein Summenabgleich, sie bleiben Prüfung durch den Menschen.
- Passt eine falsch gelesene Kombination zufällig zum Summenabgleich, wäre sie bestätigt; im Korpus kam das nicht vor.
- Stimmen PDF und eingebettetes XML nicht überein (öffentliches Muster: PDF zeigt „RE-20190121/507“, XML eine andere
  Rechnung), ist das aus dem PDF allein nicht erkennbar. Das Muster bleibt unbestätigt, weil die Nummer nur einmal
  und unbeschriftet vorkommt.
- Texterkennung bei Bild-PDFs: nur im CLI mit `--ocr` und im Lernmodus; in der Fehlerdatei bewusst nicht (würde die
  Verarbeitung verdoppeln).

## Bedienung

Vorschlag für ein PDF ausgeben (ohne Konfiguration, JSON auf stdout, Beträge und Daten als Text):

```
python -m erechnung vorschlag rechnung.pdf [--ocr]
```

Exit-Code 0 = bestätigt, 1 = nicht bestätigt (Grund im Feld `grund`). `--ocr` nutzt bei Bild-PDFs Tesseract, falls
gefunden.

Fehlerdatei: Landet ein PDF mit „keine Vorlage passt zu diesem Layout“ im Ordner `Fehler`, hängt der Überwacher an die
`.fehler.txt` den Abschnitt „Vorschlag der generischen Erkennung (nicht verwendet)“ mit Rechnungsnummer, Datum,
Brutto und „bestätigt: ja/nein“ an. Bei Bild-PDFs steht dort „kein Vorschlag: PDF ohne Text“. Fehler in diesem
Schritt werden nur ins Log geschrieben; die Verarbeitung (Fehlerdatei, Verschieben) läuft wie bisher. Es entsteht
nie eine E-Rechnung aus dem Vorschlag.
