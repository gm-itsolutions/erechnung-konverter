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

## Verfahren `generisch`

Noch nicht gemessen (Modul `erechnung.generisch` aus Task 3 fehlt). Das Werkzeug meldet das und läuft dann mit
`--verfahren generisch` bzw. `beide` weiter.
