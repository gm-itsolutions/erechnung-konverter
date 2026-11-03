# Lernmodus – Spezifikation

- **Stand:** 02.11.2026, Entwurf 2 (Fragen F1–F3 beantwortet, noch kein Code)
- **Gehört zu:** `docs/spezifikation.md` (Konverter 0.1.6). Diese Datei ergänzt sie; wo nichts Abweichendes steht, gilt die Hauptspezifikation (Summenabgleich Abschnitt 8, Mustang 3.4, Ordner und Rechte 6, Grundschutz 10).
- **Plan:** `docs/lernmodus/plan/index.md`
- **Zielversion:** 0.2.0

## 1. Ziel

Der **Kunde selbst** lernt am Windows-PC eine neue Rechnungsvorlage an, ohne GM IT und ohne Regex. Er öffnet „E-Rechnung anlernen“, lädt eine Muster-Rechnung, sieht sie als Bild und **zieht Rahmen um die Felder**, wie bei Scan-Software. Danach liest die App die Muster sofort aus und zeigt Summenabgleich und Mustang-Ergebnis. Erst wenn mindestens zwei Muster fehlerfrei durchlaufen, lässt sich die Vorlage aktivieren. Ab dann wandelt der Überwacher Rechnungen dieses Layouts um.

Fest (Marvin, 02.11.2026):
- Der Kunde lernt an, am Windows-PC.
- Verfahren: Felder im PDF markieren, nicht „Vorschlag und Bestätigen“.
- Summenabgleich und Mustang-Prüfung bleiben die Sicherung jeder erzeugten Rechnung, auch beim Anlernen.

## 2. Abgrenzung

| Enthalten | Nicht enthalten |
|---|---|
| Rechnung (380), EUR, Steuersätze wie Hauptspezifikation, ein Nachlass auf Rechnungsebene | alles, was Abschnitt 2 der Hauptspezifikation ausschließt |
| Text-PDF und Bild-PDF (Texterkennung) | Querformat, gedrehte Seiten, handschriftliche Rechnungen |
| Datum als `TT.MM.JJJJ` oder `TT.MM.JJ` | Datum mit Monatsnamen („5. November 2026“): Fehler, später nachrüstbar |
| Positionspreise netto | Positionstabellen mit Bruttopreisen (Kassenbelege): Summenabgleich schlägt fehl |
| mehrseitige Rechnungen mit wiederholtem Tabellenkopf oder ohne | Positionen in mehreren Tabellen je Rechnung |
| Vorlagen anlegen, prüfen, aktivieren, deaktivieren, löschen, exportieren | Bearbeiten der Regex-Vorlagen von GM IT (`lexware-gm-it.yml`) in der Oberfläche |

Verkäuferdaten kommen wie bisher aus `konfig.json`, sie werden nicht angelernt.

## 3. Oberfläche

### 3.1 Technik: lokaler Webserver der App

- `pythonw.exe -m erechnung anlernen --konfig <konfig.json>` startet einen `http.server.ThreadingHTTPServer` (Standardbibliothek) auf **127.0.0.1**, Port vom System zugeteilt (Port 0), und öffnet den Standardbrowser (`os.startfile`).
- **Warum kein Desktop-Fenster:** Das Windows-Embeddable-Python enthält kein tkinter; jede andere GUI (Qt, wx, pywebview) wäre eine neue Laufzeit von 30–100 MB. Ein Browser ist auf jedem Windows-PC vorhanden (Edge), Canvas und `fetch` reichen für das Rahmenziehen. Kein neues Paket: Seiten rendert pypdfium2, Bilder speichert pillow, beide sind schon im ZIP.
- **Läuft als der angemeldete Benutzer**, nie als SYSTEM. Der Prozess wird nur über die Verknüpfung gestartet und beendet sich nach **30 Minuten ohne Anfrage** oder über „Beenden“. Jeder Start ist ein eigener Server mit eigenem Port und Token.
- Oberfläche im GM-IT-Look (ai-os `50-vorlagen/webui`): `gm.css`, `fonts/`, `logo.png`, `favicon.svg` unverändert im Paket unter `erechnung/anlernen/statisch/`, Eigenes in `app.css` nur mit Tokens. Kein CDN, kein Framework, kein Build. Seiten: Gerüst `.app` mit `.sidebar` (Navigation „Vorlagen“, „Anlernen“), `.page-head`, `.card`, `.table-wrap`, `.pill`, `.alert`. Ein Primär-Button je Ansicht. Hell und dunkel. Handyansicht ist für diesen Zweck nicht nutzbar (Rahmen ziehen braucht Maus); unter 900 px zeigt die Markieren-Ansicht einen Hinweis, Vorlagenliste und Probelauf bleiben lesbar.

### 3.2 Start

`einrichten.ps1` legt **eine Startmenü-Verknüpfung für alle Benutzer** an: `%ProgramData%\Microsoft\Windows\Start Menu\Programs\GM-IT\E-Rechnung anlernen.lnk` → `<Programmordner>\aktuell\python\pythonw.exe -m erechnung anlernen --konfig "<Programmordner>\konfig.json"`, Arbeitsordner `<Programmordner>`. Eine Datei für alle Profile, kein Durchlauf durch Benutzerprofile wie bei „Senden an“, keine Desktop-Verknüpfung (der Kunde braucht die Funktion selten; im Startmenü findet die Suche „anlernen“ sie). `aktuell` bleibt über Updates gültig.

### 3.3 Absicherung

Bedrohung: andere lokale Prozesse und andere angemeldete Benutzer (Terminalserver, schnelle Benutzerumschaltung) erreichen 127.0.0.1 ebenfalls; Webseiten im Browser können Anfragen an 127.0.0.1 schicken (CSRF, DNS-Rebinding).

1. **Einmal-Token:** 32 Byte aus `secrets.token_urlsafe`. Der Browser öffnet `http://127.0.0.1:<port>/start?t=<token>`. Der Server prüft mit `hmac.compare_digest`, verwirft den Token sofort (gilt genau einmal, 60 s) und setzt das Sitzungs-Cookie `sitzung=<zufall>; HttpOnly; SameSite=Strict; Path=/`, dann `303` auf `/`. Jede weitere Anfrage ohne gültiges Cookie: `403`. Ein zweiter Browser (anderer Benutzer) bekommt keine Sitzung, auch wenn er den Port kennt.
   - Den Token sieht nur, wer die Befehlszeile des Browserprozesses lesen kann: der Benutzer selbst und Administratoren. Er ist nach dem ersten Aufruf wertlos.
   - `Secure` fehlt am Cookie, weil die Verbindung reines HTTP über Loopback ist (Abweichung L2).
2. **Host-Prüfung:** `Host` muss genau `127.0.0.1:<port>` sein, sonst `421` (gegen DNS-Rebinding).
3. **CSRF:** Jede ändernde Anfrage (`POST`, `PUT`, `DELETE`) braucht den Kopf `X-CSRF` gleich dem Sitzungs-CSRF-Wert (steht im ausgelieferten HTML als `<meta name="csrf">`) **und** `Origin: http://127.0.0.1:<port>`. Ein eigener Kopf erzwingt bei fremden Seiten einen CORS-Preflight, den der Server nie beantwortet (keine CORS-Köpfe). Formular-POSTs gibt es nicht, alles läuft über `fetch`.
4. **Antwortköpfe:** `Content-Security-Policy: default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` (nicht `no-referrer`, siehe webui-Regel 20), `Cache-Control: no-store`. Kein Inline-Skript.
5. **Eingaben:** Namen von Entwürfen und Vorlagen `^[a-z0-9][a-z0-9-]{1,39}$`, Muster-IDs `^m[0-9]{1,3}$`, Dateien aus dem Fehler-Ordner nur aus der Liste, die der Server selbst erzeugt (kein Pfad vom Browser). Anfragekörper höchstens 10 MB (PDF), JSON höchstens 64 KB. PDF muss mit `%PDF-` beginnen, höchstens 20 Seiten.
6. Keine Anmeldung mit Passwort und TOTP (webui-Regel 18): Die Oberfläche ist an den Benutzer gebunden, der sie startet, und von außen nicht erreichbar (Abweichung L1).

## 4. Daten und Ablage

| Was | Wo | Rechte |
|---|---|---|
| Entwürfe mit Muster-PDFs | `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen\entwuerfe\<name>\` (`vorlage.json`, `muster\m1.pdf …`, `muster\m1.woerter.json`) | Benutzerprofil, nur der Benutzer (und Admins) |
| Arbeitsordner für Probelauf (OCR, Mustang) | `%LOCALAPPDATA%\…\anlernen\arbeit\` | dto. |
| Log der Oberfläche | `%LOCALAPPDATA%\…\anlernen\anlernen.log` (1 MB, 3 Dateien) | dto. |
| **Aktive angelernte Vorlagen** | `<Programmordner>\vorlagen\angelernt\<name>.yml` | geerbt von Program Files: Benutzer lesen, **nur Administratoren schreiben** |
| Deaktivierte und ersetzte | `<Programmordner>\vorlagen\angelernt\deaktiviert\<name>[-<stempel>].yml` | dto. |
| Protokoll | `<Programmordner>\vorlagen\angelernt\protokoll.txt` | dto. |

- **Aktivieren braucht Administratorrechte (UAC).** Die Vorlage steuert den SYSTEM-Dienst und damit Rechnungen aller Benutzer des PCs. Die Oberfläche (Benutzerkontext) startet dafür `python.exe -m erechnung vorlage aktivieren …` per `ShellExecuteExW` mit dem Verb `runas`. Der erhöhte Prozess **vertraut dem Entwurf nicht**: Er prüft das Schema, führt den Probelauf mit allen Mustern selbst erneut aus, prüft Konflikte und schreibt erst dann (temporäre Datei, `os.replace`). Ergebnis als Exit-Code und JSON-Datei, die die Oberfläche anzeigt. Gleiches gilt für Deaktivieren, Reaktivieren und Löschen. Ist der Benutzer kein Administrator, fragt UAC nach einem Admin-Konto (GM IT oder der Admin des Kunden). Entschieden (F1): Aktivieren, Deaktivieren, Reaktivieren und Löschen nur mit Administrator-Freigabe.
- `protokoll.txt` je Aktion eine Zeile: Zeit, Windows-Benutzer der Oberfläche, Admin-Konto, Aktion, Name, SHA-256 der Datei, Anzahl Muster.
- **Updates:** `vorlagen\` liegt neben `versionen\`, gm-update ersetzt es nicht. Ein späteres Release liest `format: 1` weiter; ein unbekanntes `format` wird mit Logeintrag übersprungen (die Vorlage greift dann nicht, Rechnungen gehen nach `Fehler`, kein falsches Auslesen).
- **Überwacher lädt ohne Neustart:** Er prüft in jedem Takt Name, Größe und Änderungszeit der `*.yml` in `vorlagen\` und `vorlagen\angelernt\`. Ändert sich etwas, lädt er die Vorlagen neu. Eine ungültige Datei in diesen beiden Ordnern wird mit Warnung im Log übersprungen, der Überwacher läuft weiter (bisher: Abbruch beim Start).

## 5. Vorlagenformat (`art: bereiche`)

Erweiterung des bisherigen YAML. Die Regex-Vorlagen bleiben unverändert gültig; `lexware-gm-it.yml` hat kein `art` und wird wie bisher gelesen. Eine Vorlage mit `art: bereiche` enthält **keine Regex**, nur Texte, Koordinaten und feste Auswahlwerte.

```yaml
name: prignitz-markt
art: bereiche
format: 1
schluesselwoerter: ["Prignitz Markt GmbH", "Rechnungsnummer"]   # wörtlich, alle müssen vorkommen (wie bisher)
angelernt: {am: "2026-11-05", muster: 3}
felder:                       # Koordinaten relativ zur Seite: 0..1, Ursprung oben links, x0 < x1, y0 < y1
  nummer:       {seite: erste,  rahmen: [0.66, 0.205, 0.86, 0.222], anker: {text: "Rechnungsnummer", rahmen: [0.50, 0.205, 0.64, 0.222]}}
  nummer_kontrolle: {seite: erste, rahmen: [...], anker: {...}}   # optional, zweite Fundstelle (wie lexware-gm-it)
  datum:        {seite: erste,  rahmen: [...], anker: {text: "Datum", rahmen: [...]}}
  leistungsdatum: {...}       # optional
  faellig: {...}              # optional, Datum
  zahlungsziel_tage: {...}    # optional, erste ganze Zahl im Rahmen („14 Tage netto“)
  kaeufer:      {seite: erste,  rahmen: [0.08, 0.17, 0.45, 0.26]}  # ohne Anker: feste Lage
  summe_netto:  {seite: letzte, rahmen: [...], anker: {text: "Nettobetrag", rahmen: [...]}}
  summe_ust: {...}            # optional
  summe_brutto: {seite: letzte, rahmen: [...], anker: {text: "Gesamtbetrag", rahmen: [...]}}
  nachlass: {...}             # optional, ein Nachlass auf Rechnungsebene, Betrag ohne Vorzeichen
steuern:                      # optional; jede Zeile, die zum Anker passt, ist ein Steuersatz
  seite: letzte
  anker: {text: "zzgl. {satz} % MwSt.", rahmen: [...]}   # {satz} = Platzhalter für die Zahl
  rahmen: [...]               # Betrag der Steuerzeile
  satz: 19                    # nur ohne {satz} im Ankertext
positionen:
  kopf: {text: "Pos. Artikel Menge", rahmen: [...]}   # Tabellenkopf; Tabelle beginnt unter ihm
  ende: {text: "Nettobetrag", rahmen: [...]}          # optional; Tabelle endet über ihm
  unten: 0.90                 # Fußbereich ab hier auf jeder Seite ignorieren
  links: 0.06                 # linke Tabellenkante
  spalten:                    # rechte Kante je Spalte, aufsteigend
    - {bis: 0.12, art: nr}
    - {bis: 0.55, art: bezeichnung}
    - {bis: 0.63, art: menge}           # oder menge_einheit („2 Std“)
    - {bis: 0.70, art: einheit}
    - {bis: 0.80, art: einzelpreis}
    - {bis: 0.86, art: ust_satz}        # optional
    - {bis: 0.95, art: netto}
  ust_satz: 19                # wenn keine Spalte ust_satz
einheiten: {Std: HUR, Stk: H87}         # sonst C62 (wie bisher)
```

**Schema** (`bereiche.pruefe_bereichsvorlage`, fest im Code, unbekannte Schlüssel → Fehler):
- Datei höchstens 64 KB (gilt für alle Vorlagen), `yaml.safe_load`.
- `name` wie 3.3 Nr. 5; nicht gleich dem Namen einer mitgelieferten Vorlage. Bei gleichem Namen gewinnt die mitgelieferte, die angelernte wird mit Warnung übersprungen (GM IT hat sie dann ins Release übernommen).
- `schluesselwoerter` 1–5 Texte, je 3–80 Zeichen. `format` genau `1`.
- Pflichtfelder `nummer`, `datum`, `summe_netto`, `summe_brutto`, `kaeufer` und `positionen`. Feldnamen nur aus der Liste oben.
- `seite` ∈ {`erste`, `letzte`}; `rahmen` 4 Zahlen in [0, 1] mit x0 < x1, y0 < y1; `anker.text` 1–80 Zeichen, `{satz}` höchstens einmal und nur in `steuern.anker`.
- `spalten` 2–12, `bis` streng steigend, `links` < erstes `bis`; genau eine `bezeichnung`, genau eine `netto`, höchstens eine von `menge`/`menge_einheit`; `art` ∈ {`nr`, `bezeichnung`, `menge`, `einheit`, `menge_einheit`, `einzelpreis`, `ust_satz`, `netto`, `ignorieren`}.
- `einheiten` höchstens 50 Einträge, Schlüssel 1–20 Zeichen, Werte `^[A-Z0-9]{2,3}$`. `ust_satz`/`satz` aus {0 < x ≤ 30}.
- **Kein ReDoS möglich:** Der Code baut aus Ankertexten nur wörtliche Vergleiche (`re.escape` bzw. Normalisierung); Zahlen liest er mit wenigen festen Mustern ohne verschachtelte Wiederholung. Keine Ausführung, keine YAML-Tags (`safe_load`), keine Pfade in der Vorlage.

## 6. Auslesen

### 6.1 Wörter mit Lage

Beide Wege liefern dieselbe Struktur `Seite = list[Wort]`, `Wort(text, x0, top, x1, bottom)` relativ zur Seite (0..1, oben links):
- **Text-PDF:** `pdfplumber` `page.extract_words()`, Koordinaten geteilt durch Seitenbreite bzw. -höhe.
- **Bild-PDF:** Texterkennung wie bisher (3.2 Hauptspezifikation), aber Tesseract schreibt in **einem** Aufruf `txt` und `tsv` (`… --psm 6 --dpi N txt tsv`). Aus der TSV (Ebene 5 = Wort, `conf` ≥ 0) entstehen die Wörter, geteilt durch Bildbreite/-höhe. Kein zweiter OCR-Lauf je Bereich: Für die Anker braucht es ohnehin die ganze Seite, ein zweiter Lauf je Feld verdoppelte die Laufzeit (rund 7 s je Seite), und die Beträge sichert der Summenabgleich.

Die Vorlage wird wie bisher über `schluesselwoerter` im Fließtext gefunden (`finde_vorlage`, unverändert).

### 6.2 Anker statt fester Lage

- Ein Anker ist eine Folge benachbarter Wörter einer Zeile, deren Text ohne Leerzeichen und in Kleinschreibung dem Ankertext entspricht. Bei Bild-PDFs gilt zusätzlich eine Ähnlichkeit ≥ 0,85 (`difflib.SequenceMatcher`), wenn kein genauer Treffer da ist.
- Gesucht wird auf der ersten (`erste`) bzw. der letzten Seite, die den Anker enthält (`letzte`). Mehrere Treffer auf der Seite: der, dessen linke obere Ecke der angelernten Lage am nächsten ist.
- `anker.rahmen` ist der Umriss der Ankerwörter auf dem Muster (die Oberfläche setzt ihn aus den angeklickten Wörtern, nicht aus einem gezogenen Rahmen). **Verschiebung** = linke obere Ecke des gefundenen ersten Ankerworts minus angelernte linke obere Ecke. Der Feldrahmen wird um diese Verschiebung versetzt und je Seite um 0,005 vergrößert. Ein Wort gehört zum Feld, wenn sein Mittelpunkt im Rahmen liegt.
- Felder ohne Anker (z. B. Käuferblock im Fenster des Briefbogens) stehen fest auf der Seite, werden aber um die Verschiebung des Nummer-Ankers versetzt, wenn dieser auf derselben Seite gefunden wurde (ein anderer Druckweg verschiebt die ganze Seite).
- Anker fehlt → Pflichtfeld: Fehler „Anker ‚Gesamtbetrag‘ nicht gefunden (Vorlage x)“; optionales Feld: leer.

### 6.3 Werte

| Feld | Lesen |
|---|---|
| `nummer`, `nummer_kontrolle` | Wörter des Rahmens ohne Leerzeichen; muss `^[A-Za-z0-9./_-]{1,30}$` sein, sonst Fehler. Ist `nummer_kontrolle` angelernt, muss sie gleich sein (bei Texterkennung nach der Normalisierung `O0/O → 0` wie bisher). |
| Datum | erstes `\d{1,2}\.\d{1,2}\.\d{2,4}`, zweistelliges Jahr → 20JJ, `O` → `0` |
| `zahlungsziel_tage` | erste ganze Zahl 1–365; `faellig` = Datum + N |
| Beträge | letzter Treffer `-?\d[\d. ]*[,.] ?\d{2}` im Rahmen, dann `modell.betrag()` |
| `kaeufer` | Zeilen des Rahmens: erste = Name, letzte mit `^\d{5} ` = PLZ/Ort, die Zeile davor = Straße; Land DE. Zusatzzeilen dazwischen entfallen (wie bisher). Keine PLZ-Zeile → Fehler |
| `steuern` | alle Ankertreffer auf der Seite; `{satz}` liest die Zahl an dieser Stelle (`\d{1,2}(?:[,.]\d{1,2})?`), der Betrag kommt aus dem versetzten Rahmen je Treffer |

Zeilen eines Rahmens: Wörter nach Mittelpunkt-y gruppiert (Toleranz: halbe mittlere Worthöhe), in der Zeile nach x sortiert.

### 6.4 Positionstabelle

- **Erste Seite:** Tabelle von Unterkante `kopf` bis Oberkante `ende` (falls auf dieser Seite), sonst bis `unten`. Alle Spaltengrenzen werden waagerecht an den gefundenen Kopf-Anker angepasst: versetzt um seine Verschiebung und skaliert mit dem Verhältnis gefundene zu angelernter Breite (fängt „an Seite anpassen“ beim Edge-Druck ab, Test mit 95 %).
- **Folgeseiten:** Kopf gefunden → darunter; sonst ab der ersten Zeile mit Betrag in der Spalte `netto`. Ende wie oben. So landen Briefkopf und Anschrift der Folgeseite nicht in einer Bezeichnung.
- Jedes Wort kommt in die Spalte seines Mittelpunkts. Zeilen wie 6.3.
- **Position:** Zeile mit Betrag in `netto` und Menge (aus `menge`/`menge_einheit`) oder Einzelpreis; fehlt nur die Menge, gilt 1. `menge_einheit` „2,5 Std“ → Menge 2,5, Einheit „Std“.
- **Fortsetzung:** Zeile ohne Betrag mit Text in `bezeichnung` → an die vorige Position mit derselben Silbentrennregel wie bisher (`vorlagen._anfuegen`).
- **Übertrag, Zwischensumme:** Zeile mit Betrag in `netto`, aber ohne Menge und ohne Einzelpreis → ignoriert und im Probelauf als „ignorierte Zeile“ angezeigt. Der Summenabgleich fängt falsch zugeordnete Zeilen.
- Einheit über `einheiten`, sonst C62; USt-Satz aus Spalte oder `ust_satz`.

### 6.5 Druckwege

- Andere Druckwege derselben Rechnung (Programm direkt, Edge-Raster, „Senden an“ mit Original) verschieben und skalieren die Seite leicht. Relative Koordinaten machen Auflösung und Seitengröße egal; Anker gleichen Verschiebungen aus; der vergrößerte Rahmen und Mittelpunktregel fangen kleine Skalierungen. Eine Skalierung auf „Seite anpassen“ (Edge, rund 95 %) verschiebt weit vom Anker entfernte Felder um bis zu ~1 % der Seite; Rahmen deshalb nicht knapp ziehen (Hinweis in der Oberfläche).
- Die Oberfläche empfiehlt, je Druckweg ein Muster zu hinterlegen: das Original-PDF und einen Druck über den Drucker „E-Rechnung“ (landet bei unbekanntem Layout in `Fehler` und kann von dort übernommen werden, 7.1).
- **Belegt wird das auf VM 108** (Task 11): dieselbe Rechnung als Text-PDF und als Edge-Druck.

## 7. Ablauf in der Oberfläche

### 7.1 Muster

„Neue Vorlage“ → Name → Muster hinzufügen: Datei wählen **oder** aus dem Ordner `Fehler` übernehmen (Liste der PDFs dort; Benutzer haben Leserecht). Seiten werden mit pypdfium2 auf 1400 px Breite gerendert (PNG, im Entwurf zwischengespeichert). Wörter je Muster werden einmal bestimmt (Text-PDF sofort, Bild-PDF per Texterkennung mit Fortschrittsanzeige) und als `m<n>.woerter.json` gespeichert.

### 7.2 Markieren

- Links die Feldliste (Pflichtfelder zuerst, je mit Status „fehlt“/„markiert“), rechts das Seitenbild in einem `<canvas>`. Wörter werden beim Überfahren dezent hervorgehoben.
- Feld wählen, Rahmen um den **Wert** ziehen. Die Oberfläche schlägt als Anker die Wörter links daneben in derselben Zeile vor (sonst die Zeile direkt darüber) und zeigt ihn in einer zweiten Farbe. Klick auf andere Wörter setzt einen anderen Anker, „ohne Anker“ macht das Feld fest. Gelesener Wert erscheint sofort neben dem Feld (Vorschau über `/api/…/vorschau`).
- Steuern: eine Steuerzeile markieren; enthält der Anker eine Zahl mit `%`, ersetzt die Oberfläche sie durch `{satz}`, sonst Auswahl des Satzes.
- Positionen: Rahmen um die ganze Tabelle **ohne** Kopfzeile ziehen, Kopfzeile anklicken (Anker `kopf`), Spaltengrenzen per Klick setzen und je Spalte die Art wählen, optional Ende-Anker anklicken, Linie „Fußbereich“ ziehen.
- Erkennung: die Oberfläche schlägt als `schluesselwoerter` den Anker der Nummer plus die längste Zeile des oberen Seitenviertels vor; der Benutzer kann sie ändern.
- Speichern automatisch nach jeder Änderung (`PUT`), Entwürfe dürfen unvollständig sein.

Vorbefüllen: Die generische Erkennung (`erechnung.generisch.vorschlag_aus_pdf`, Messung in `docs/generisch/messung.md`) liefert je Muster einen Vorschlag für Nummer, Datum, Käufer, Positionen und Summen samt Fundstelle (Zeile). Die Oberfläche kann daraus Rahmen vorschlagen; der Benutzer bestätigt oder korrigiert sie. Der Vorschlag ersetzt weder das Markieren noch den Probelauf und erzeugt keine E-Rechnung.

### 7.3 Probelauf

„Probelauf“ liest **alle** Muster mit dem Entwurf: Werte, Positionen, ignorierte Zeilen, Summenabgleich, Mustang (gegen die erzeugte XML, wie 3.4 Hauptspezifikation), Konfliktprüfung (passt auf ein Muster zusätzlich eine aktive Vorlage → Fehler „mehrere Vorlagen“). Die gefundenen Rahmen liegen grün über dem Seitenbild, nicht gefundene rot. Nummer, Daten und Käufer sichert kein Summenabgleich; deshalb setzt der Benutzer je Muster das Häkchen „Nummer, Datum und Käufer stimmen“.

### 7.4 Aktivieren und verwalten

- „Vorlage aktivieren“ (Primär-Button) nur, wenn **mindestens zwei Muster** fehlerfrei sind, alle Muster fehlerfrei sind und alle Häkchen gesetzt sind. Danach UAC (4.).
- Liste „Vorlagen“: mitgelieferte (nur lesen), aktive angelernte (Deaktivieren, Löschen), deaktivierte (Reaktivieren, Löschen). Erneutes Aktivieren desselben Namens ersetzt die alte Datei, die nach `deaktiviert\<name>-<stempel>.yml` wandert.
- **Export an GM IT:** nur `vorlage.yml`, **keine Muster-PDFs** (F2), als `erechnung-vorlage-<name>-<datum>.yml` in den Download-Ordner. Der Kunde schickt sie an GM IT; Marvin prüft sie gegen eine eigene Rechnung dieses Layouts (vom Kunden auf dem üblichen Weg angefordert, nur nach `/root/erechnung-testdaten/`) und übernimmt sie bei Bedarf ins Release (`erechnung/vorlagen/`). Die Datei enthält nur Koordinaten, Ankertexte und Schlüsselwörter, keine Rechnungsdaten.

## 8. Komponenten

| Datei | Aufgabe |
|---|---|
| `erechnung/bereiche.py` | `Wort`, `pruefe_bereichsvorlage()`, `woerter_aus_pdf()`, `finde_anker()`, `zeilen()`, `positionen_aus_bereichen()`, `rechnung_aus_bereichen()` |
| `erechnung/vorlagen.py` | `_pruefe` verzweigt bei `art: bereiche`; 64-KB-Grenze; `lade_vorlagen(..., tolerant=False)`; `lies_rechnung` verzweigt auf Bereiche (Text und OCR) |
| `erechnung/ocr.py` | `erkenne_seiten()` (Text und Wörter in einem Lauf), `tsv_woerter()`; `erkenne()` bleibt |
| `erechnung/ueberwachen.py` | `lade_konfig(datei, arbeit=None)`, Ordner `vorlagen\angelernt`, Neuladen bei Änderung |
| `erechnung/anlernen/server.py` | Webserver, Sicherheit 3.3, Entwürfe, Muster, Seitenbilder, Wörter, Vorschau |
| `erechnung/anlernen/verwalten.py` | `probelauf()`, `aktivieren()`, `deaktivieren()`, `reaktivieren()`, `loeschen()`, `exportieren()`, Protokoll |
| `erechnung/anlernen/erhoehen.py` | `als_admin(argumente) -> int` (ShellExecuteExW `runas`) |
| `erechnung/anlernen/statisch/` | `index.html`, `anlernen.js`, `app.css`, `gm.css`, `fonts/`, `logo.png`, `favicon.svg` |
| `erechnung/__main__.py` | neue Befehle `anlernen`, `vorlage aktivieren|deaktivieren|reaktivieren|loeschen` |
| `einrichten/einrichten.ps1` | Ordner `vorlagen\angelernt`, Startmenü-Verknüpfung |

## 9. Tests

- Testdaten: Unit-Tests nutzen die synthetischen Muster aus `tests/hilfen_bereiche.py` (CI). Für Gegenproben mit realistischeren Layouts: `werkzeuge/fremdrechnungen.py` erzeugt deterministisch Rechnungen in sieben fremden Layouts (A–G) nach `/root/erechnung-testdaten/fremd/` (`<layout>-<n>.pdf`, je Layout ein `<layout>-1-bild.pdf`, je Datei `.soll.json` mit Sollwerten und erwartetem Verhalten); erzeugen mit `/root/.venvs/erechnung/bin/python werkzeuge/fremdrechnungen.py`, Gegenprobe mit `--gegenprobe`. Nur auf gm-claude, PDFs nicht ins Repo.
- pytest: Schema (gültig, jede Regel einzeln verletzt, Größe), Auslesen per Bereich mit synthetischen reportlab-PDFs (zwei Layouts, verschoben, mehrseitig mit Übertrag, mehrzeilige Bezeichnung), dasselbe als Bild-PDF über Tesseract (übersprungen ohne Tesseract), TSV-Parser mit fester TSV, Überwacher-Neuladen, Server (Token einmalig, Cookie, Host, Origin, CSRF, Pfade, Größen, Leerlauf), Verwalten (Probelauf, Aktivieren mit ersetztem `als_admin`, Konflikt, Protokoll, Export nur `vorlage.yml`). Bestehende Tests laufen unverändert.
- Browser: Playwright (MCP auf gm-claude, Chromium) gegen den echten Server mit Testdaten: Markieren eines Feldes per Maus, Probelauf, Ansicht 1280 px hell und dunkel, 390 px Lesbarkeit der Liste. Kein Playwright in der CI (neue Abhängigkeit ohne Gewinn für die Logik, die die pytest-Tests abdecken).
- Abnahme auf VM 108 (Task 11).

## 10. Grundschutz-Abgleich (Erweiterung)

Maßstab und Schutzbedarf wie Hauptspezifikation 10 (Katalog 2026-10-22). Neu berührt: Bedienoberfläche im Benutzerkontext, vom Benutzer erzeugte Steuerdaten für den SYSTEM-Dienst. Integrität bleibt **normal**: Beträge sichern Summenabgleich und Mustang; Nummer, Daten, Käufer sichert die Sichtprüfung beim Probelauf (Häkchen) und bei Texterkennung die Hinweisdatei.

Unverändert aus Hauptspezifikation 10 und weiter gültig: KONF.8.1/8.2, DET.5.10 (GM-Standard), DET.5.10.2 (A3), BER.5.10, DLS.2.2, NOT.4.15 für die App selbst; der Lernmodus kommt über denselben signierten gm-update-Weg. Neue GM-Standards der Stufe 3 (Offline-Kopie, MFA am Perimeter, SPF/DKIM/DMARC, Management-Netz, Fernwartung) berührt die Erweiterung nicht: keine Netzdienste, kein Fernzugriff.

| ID | Anforderung | Umsetzung |
|---|---|---|
| BER.4.1 | Geringste Berechtigungen | Oberfläche als Benutzer, nie SYSTEM; aktive Vorlagen nur von Administratoren schreibbar; Überwacher liest sie nur |
| KONF.6.4 | Privilegierte Systemfunktionen einschränken | Aktivieren/Deaktivieren/Löschen nur per UAC; erhöhter Prozess prüft selbst neu (4.) |
| KONF.2.4 | Nicht benötigte Funktionen deaktivieren | Server nur auf Abruf, nur 127.0.0.1, Ende nach 30 Min. Leerlauf; kein Dienst, kein offener Port im Normalbetrieb |
| KONF.4.3 | Authentifizierung von Verwaltungsfunktionen | Einmal-Token, Sitzungs-Cookie `HttpOnly`/`SameSite=Strict`, CSRF-Kopf und `Origin`, Host-Prüfung (3.3) |
| BER.3.13 | Sperre bei Inaktivität | Server endet nach 30 Min. ohne Anfrage |
| KONF.7.9 | Einschränkung der Installation | keine neue Software, keine neue Abhängigkeit (Standardbibliothek, pypdfium2/pillow schon im Paket) |
| DET.3.1 / DET.3.1.8 | Protokollierung, privilegierte Ereignisse | `protokoll.txt` (Wer, Admin, Was, SHA-256), `erechnung.log` (Neuladen, übersprungene Dateien), `anlernen.log` |
| ASST.2.3 | Inventar der Anwendungen | aktive Vorlagen mit SHA-256 im Protokoll; Export (`vorlage.yml`) an GM IT |
| NOT.4.15 | Wiederherstellungsweg | Runbook: Vorlagen-Ordner sichern/zurückkopieren, exportierte `vorlage.yml` als Kopie bei GM IT; ersetzte Fassungen in `deaktiviert\` |
| DEV / TEST | Sichere Entwicklung, Tests | Schema ohne Regex/Ausführung, pytest inkl. Sicherheitstests, Playwright-Prüfung, VM-Abnahme |
| X.1.1.2 | Zuständigkeiten | Anlernen: Kunde; Aktivieren: Admin des PCs (Kunde oder GM IT); Übernahme ins Release: GM IT |

**Abweichungen:**

| Nr | ID / Regel | Abweichung | Grund | Art |
|---|---|---|---|---|
| L1 | webui-Regel 18 (Passwort + TOTP) | Keine Anmeldung, Einmal-Token | Nur Loopback, an den startenden Benutzer gebunden, kurzlebig; ein Passwort hätte niemand und wäre schwächer als der Token | dauerhaft (GM-intern, keine Kundenzustimmung nötig) |
| L2 | webui-Regel 19 (`Secure`-Cookie) | Cookie ohne `Secure` | HTTP über Loopback, kein Netzweg | dauerhaft (GM-intern) |
| ~~L3~~ | BER.4.1 | **entfällt** (F2, 02.11.2026): Muster-PDFs bleiben im Profil des Benutzers, der die Rechnungen ohnehin kennt, und werden mit dem Entwurf gelöscht; der Export enthält nur `vorlage.yml` | – | – |

**Restrisiken:** Eine angelernte Vorlage kann Nummer, Datum oder Käufer falsch zuordnen, wenn der Benutzer das Häkchen ohne Prüfung setzt; Beträge bleiben gesichert. Ein Administrator kann jede Vorlage aktivieren (gewollt). Der Parser liest Vorlagen als SYSTEM; durch Schema, Größengrenze und fehlende Regex bleibt das auf Datenfehler begrenzt (A1 der Hauptspezifikation bleibt).

## 11. Fragen an Marvin (beantwortet 02.11.2026)

- **F1 Aktivieren nur mit Admin (UAC)?** **Ja.** Aktivieren, Deaktivieren, Reaktivieren und Löschen angelernter Vorlagen nur mit Administrator-Freigabe (UAC), wie in 4. geplant. Keine Schreibrechte für Benutzer in `vorlagen\angelernt`, keine neue Abweichung zu BER.4.1.
- **F2 Export mit Muster-PDFs?** **Nein.** Export an GM IT nur `vorlage.yml`, keine Muster-PDFs (7.4). Abweichung L3 entfällt (10.). Braucht GM IT zur Prüfung eine Rechnung des Layouts, fordert Marvin sie gesondert an.
- **F3 Prignitz Markt:** Die erste Prignitz-Markt-Vorlage lernt **Marvin zusammen mit dem Kunden** beim Termin an (Kunde bedient, Marvin begleitet und gibt per UAC frei). Weitere Layouts lernt der Kunde danach selbst an.

## 12. Abnahme

Auf VM 108 mit Release 0.2.0 über gm-update, Benutzer ohne Adminrechte:
1. Startmenü „E-Rechnung anlernen“ öffnet den Browser, Oberfläche im GM-Look.
2. Eine Rechnung in fremdem Layout (Testdaten, Task 11) zweimal (Original-PDF und Edge-Druck aus `Fehler`) als Muster; alle Pflichtfelder und Tabelle markiert; Probelauf beide grün, Mustang valid.
3. Aktivieren mit UAC und Admin-Konto; `protokoll.txt` mit Eintrag.
4. Ohne Neustart: dieselbe Rechnung gedruckt und per Edge gedruckt → E-Rechnung in `E-Rechnungen`, Mustang valid im Log.
5. Ein zweiter Benutzer (schnelle Benutzerumschaltung) erreicht den Port ohne Token nur mit `403`.
6. Update auf 0.2.1 (oder erneute Freigabe): Vorlage bleibt aktiv.
7. Deaktivieren → Rechnung landet in `Fehler` („keine Vorlage passt“); Reaktivieren → wieder E-Rechnung.
