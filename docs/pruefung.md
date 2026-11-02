# Prüfung der erzeugten E-Rechnungen

Nur gm-claude. Echte Testdaten liegen in `/root/erechnung-testdaten/` (0700), nie im Repo.

## Automatisch (pytest)

```sh
ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q
```

`tests/test_lexware_echt.py` liest RE0146, RE0148, RE0149 über die Vorlage ein und prüft:

- Nummer, Netto, Steuer, Brutto und Positionsbeträge gleich der Lexware-XML,
- erzeugte CII-XML gültig gegen das XSD (factur-x, Profil EN16931).

Die erzeugte XML landet dabei in `/tmp/erechnung-pruefung/<nummer>.xml` (für Mustang, unten).

Ohne `ERECHNUNG_TESTDATEN` werden diese Tests übersprungen (CI).

**Schematron:** factur-x bringt die EN16931-Schematron-Regeln mit, aber als XSLT 2.0; lxml kann nur XSLT 1.0, factur-x braucht dafür einen Saxon-Server. Den gibt es hier nicht – die Schematron-Prüfung deckt Mustang ab.

## Offen: Mustang-Prüfung durch Marvin

Pflicht vor jeder Freigabe (Spezifikation 12.1). Prüft XSD und EN16931-Schematron. Bisher nicht gelaufen, weil Mustang nicht automatisch heruntergeladen werden soll.

1. **Bezugsquelle:** `Mustang-CLI-<v>.jar` der neuesten stabilen Version von https://github.com/ZUGFeRD/mustangproject/releases, Prüfsumme gegen Maven Central (`https://repo1.maven.org/maven2/org/mustangproject/Mustang-CLI/<v>/Mustang-CLI-<v>.jar.sha1`) vergleichen.
2. **Ablage:** `/root/.cache/mustang/Mustang-CLI-<v>.jar` (außerhalb des Repos).
3. **Befehl** (nach dem pytest-Lauf oben, je Rechnung):

```sh
java -Xmx1g -jar /root/.cache/mustang/Mustang-CLI-<v>.jar --no-notices --action validate --source /tmp/erechnung-pruefung/RE0146.xml
```

Gültig, wenn der Bericht `status="valid"` enthält. Meldet Mustang eine fehlende Leitweg-ID (BR-DE-*), hat es als XRechnung statt EN16931 geprüft – kein Fehler für dieses Profil.

Danach kann `werkzeuge/pruefen.sh` aus Task 08 (Version und SHA-256 gepinnt) und der Ende-zu-Ende-Test nachgezogen werden.
