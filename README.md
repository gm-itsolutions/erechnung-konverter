# erechnung-konverter

Rechnung drucken -> E-Rechnung (ZUGFeRD/XRechnung), Windows, Open Source

## Generische Erkennung (Vorschlag)

Passt keine Vorlage, liest `erechnung.generisch` die Rechnung layoutunabhängig und liefert einen **Vorschlag**
(Nummer, Datum, Käufer, Positionen, Summen). Er landet als Hinweis in der `.fehler.txt` und füllt im Lernmodus
Felder vor; eine E-Rechnung entsteht daraus nie. Aufruf: `python -m erechnung vorschlag rechnung.pdf` (JSON,
Exit 0 = bestätigt). Messwerte und Grenzen: [docs/generisch/messung.md](docs/generisch/messung.md).
