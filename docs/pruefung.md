# Prüfung der erzeugten E-Rechnungen

Ab 0.1.6 prüft die App **jede** Rechnung selbst mit Mustang (XSD + EN16931-Schematron), bevor sie im Ausgabeordner landet (Spezifikation 3.4). Diese Seite beschreibt die Prüfung in den Tests. Echte Testdaten liegen nur auf gm-claude in `/root/erechnung-testdaten/` (0700), nie im Repo.

## Mustang lokal (gm-claude)

Version und Prüfsummen stehen in `release/mustang.env`. Das Jar liegt in der Paketablage; einmal holen:

```sh
mkdir -p /root/.cache/mustang
```

```sh
curl -fsSL -H "Authorization: token <Paket-Token>" -o /root/.cache/mustang/Mustang-CLI-2.26.0.jar https://git.gm-itsolutions.de/api/packages/gm-itsolutions/generic/mustang-cli/2.26.0/Mustang-CLI-2.26.0.jar
```

```sh
sha256sum /root/.cache/mustang/Mustang-CLI-2.26.0.jar
```

Muss `MUSTANG_SHA256` aus `release/mustang.env` ergeben. Java 21 ist auf gm-claude installiert (`java` im PATH); die Tests finden Mustang über `MUSTANG_JAR`.

## Automatisch (pytest)

```sh
MUSTANG_JAR=/root/.cache/mustang/Mustang-CLI-2.26.0.jar ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q -rs
```

- `tests/test_mustang.py`: Auswertung des Berichts mit ersetztem Aufruf (gültig, ungültig mit Regel-IDs, Fehlercode, kein Bericht, nicht startbar, Frist) und – wenn `java` und `MUSTANG_JAR` da sind – echte Mustang-Läufe auf synthetische Rechnungen (gültig, mit Rabatt gültig, falsche Summe → `BR-CO-15`).
- `tests/test_ueberwachen.py`: Ablage nur nach gültiger Prüfung, Fehlerdatei bei ungültig oder fehlendem Mustang; `test_cli_umwandeln` läuft als eigener Prozess mit echtem Mustang (ohne Mustang: muss im Fehlerordner enden).
- `tests/test_lexware_echt.py` (nur mit `ERECHNUNG_TESTDATEN`): RE0146, RE0148, RE0149, RE0158 über die Vorlage einlesen; Nummer, Netto, Steuer, Brutto und Positionsbeträge gleich der Lexware-XML, XSD gültig, **Mustang gültig** (`test_mustang_gueltig`). Die erzeugte XML landet zusätzlich in `/tmp/erechnung-pruefung/<nummer>.xml`.

Ohne `MUSTANG_JAR` werden die echten Mustang-Läufe übersprungen (`-rs` zeigt das). Die CI holt Mustang (und bei Bedarf die Linux-JRE) aus der Paketablage (`release/mustang_holen.sh`) und bricht ab, wenn Mustang nicht gefunden wird – dort wird also nie still übersprungen.

**Schematron ohne Mustang:** factur-x bringt die EN16931-Schematron-Regeln nur als XSLT 2.0 mit; lxml kann nur XSLT 1.0. Deshalb Mustang.

## Von Hand

```sh
java -Xmx512m -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -jar /root/.cache/mustang/Mustang-CLI-2.26.0.jar --no-notices --action validate --source /tmp/erechnung-pruefung/RE0146.xml
```

Gültig, wenn der Bericht `<summary status="valid"/>` enthält und der Exit-Code 0 ist (ungültig: 255). Auf das ZUGFeRD-PDF angewandt meldet Mustang den PDF-Teil als `invalid`, weil das PDF kein PDF/A-3 ist (Abweichung A2) – deshalb prüft die App nur die XML.

## Ergebnis 02.11.2026 (Mustang 2.26.0, Temurin 21.0.13 und OpenJDK 21.0.12)

| Rechnung | XML | Regeln geprüft / verletzt | PDF (nur zur Info) |
|---|---|---|---|
| RE0146 | valid | 123 / 0 | PDF-Teil invalid (ISO 19005-3 6.8, kein PDF/A-3), XML valid |
| RE0148 | valid | 72 / 0 | wie oben |
| RE0149 | valid | 123 / 0 | wie oben |
| RE0158 (Rabatt) | valid | 82 / 0 | wie oben |

Keine Warnungen oder Hinweise im Bericht. `cii.py` musste nicht geändert werden.
