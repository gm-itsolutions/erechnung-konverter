# Task 12: Oberfläche – Probelauf, Aktivieren, Vorlagenliste; Browserprüfung

Spezifikation: `docs/lernmodus/spezifikation.md` 7.3, 7.4, 9. Global Constraints in `index.md`. webui-Regeln wie Task 11.

**Files:**
- Modify: `erechnung/anlernen/statisch/anlernen.js`, `index.html`, `app.css`

**Interfaces:**
- Consumes: Task 10 API (`POST …/probelauf` → `{vorlage_fehler, muster: [{id, ok, fehler, werte, positionen, ignoriert, spur, mustang}], bereit}`; `POST …/aktivieren {bestaetigt}` → `{ok, meldung}`; `POST /api/vorlage/<name>/(deaktivieren|reaktivieren|loeschen)`; `GET …/export`; `/api/stand` mit `mitgeliefert`, `aktiv`, `deaktiviert`, `entwuerfe`); Task 11 (`api`, `zeichne`, `oeffneEntwurf`, `werkzeuge/anlernen_demo.py`).
- Produces: `probelauf()`, `zeigeProbelauf(ergebnis)`, `aktivieren()`, `verwalten(name, aktion)`, `exportieren()` in `anlernen.js`.

- [ ] **Step 1: Probelauf-Ansicht** – Primär-Button „Probelauf“ im Kopf von `#anlernen`. Während des Laufs Knopf gesperrt, Text „Probelauf läuft …“ (Texterkennung und Mustang dauern je Muster einige Sekunden).
  - `vorlage_fehler` → `.alert.err` mit dem Text (z. B. „felder: kaeufer fehlt“), keine Tabelle.
  - Sonst je Muster eine `.card`: Kopf mit Dateiname und `.pill` („bestanden“ `ok` / „Fehler“ `err`); bei Fehler der Text als `.alert.err`; sonst eine Zeilenliste der Werte (Nummer, Datum, Fälligkeit, Käufer, Netto, Steuern je Satz, Brutto, Mustang-Kurzbericht in Mono), darunter `.table-wrap` mit den Positionen (Spalten Pos., Bezeichnung, Menge, Einheit, Einzelpreis, USt, Netto; Zahlen `.num`) und, falls vorhanden, „Ignorierte Zeilen“ als Liste mit `.hint` „Übertrag/Zwischensumme – prüfen, ob keine Position darunter ist“.
  - Checkbox je bestandenem Muster: „Nummer, Datum und Käufer stimmen mit der Rechnung überein“ (`<label>` am Feld).
  - Klick auf „Rahmen anzeigen“ öffnet das Muster im Canvas und zeichnet `spur` (gefundene Rahmen) in `ok`-Farbe; Felder, die im Entwurf markiert sind, aber in `spur` fehlen, in `err`-Farbe an der angelernten Stelle.
  - Kopf der Ansicht zeigt zusammengefasst: „2 von 2 Mustern bestanden“ bzw. „mindestens 2 Muster nötig“.

- [ ] **Step 2: Aktivieren** – Knopf „Vorlage aktivieren“ erscheint nach einem Probelauf **statt** „Probelauf“ als Primär-Button (immer nur ein Primär-Button), aktiv nur wenn `bereit` und alle Checkboxen gesetzt; daneben sekundär „Probelauf wiederholen“. Jede Änderung an der Vorlage oder den Mustern setzt den Probelauf zurück. Vor dem Senden Hinweis-Text (`.alert.info`): „Windows fragt gleich nach einem Administrator-Konto. Ohne Freigabe bleibt die Vorlage inaktiv.“ Ergebnis `ok` → `.alert.ok` „Vorlage aktiv. Rechnungen in diesem Layout werden ab sofort umgewandelt.“ und Wechsel zu `#vorlagen`; sonst `.alert.err` mit `meldung`.

- [ ] **Step 3: Vorlagenliste `#vorlagen`** – Tabelle mit allen Einträgen: mitgelieferte (`.pill info` „mitgeliefert“, keine Aktionen), aktive angelernte (`.pill ok` „aktiv“; Aktionen „Deaktivieren“, „Löschen“ als `.btn-danger` rechts), deaktivierte (`.pill warn` „deaktiviert“; „Reaktivieren“, „Löschen“), Entwürfe (`.pill` „Entwurf“; „Bearbeiten“, „Für GM IT exportieren“, „Entwurf löschen“). Löschen mit `confirm()`-Rückfrage im Klartext. Deaktivieren/Reaktivieren/Löschen einer aktiven Vorlage gehen über UAC (gleicher Hinweis wie Step 2). Export lädt per `api(...)` als Blob und speichert über einen temporären `<a download>` (kein Inline-Skript, `URL.createObjectURL`). Leerer Zustand `.empty`: „Noch keine eigene Vorlage. Mit ‚Neue Vorlage‘ eine Muster-Rechnung anlernen.“

- [ ] **Step 4: Browserprüfung mit Playwright-MCP** (auf gm-claude, Chromium vorhanden; laut webui-Skill **in einem Subagenten**, der nur das Ergebnis meldet). Demo im Hintergrund starten: `/root/.venvs/erechnung/bin/python /root/ek-wt-lern/werkzeuge/anlernen_demo.py /tmp/anlernen-demo-12`. Der Demo-Server hat keinen Mustang-Ersatz: Wenn `java`/`MUSTANG_JAR` auf gm-claude fehlen (`which java`, `echo $MUSTANG_JAR`; `docs/pruefung.md` nennt den Weg), zeigt der Probelauf „Mustang-Prüfung nicht verfügbar“ – dann `MUSTANG_JAR` wie in `docs/pruefung.md` setzen, nicht den Code ändern.
  1. URL öffnen; danach dieselbe URL ein zweites Mal öffnen → Seite „Start-Link ungültig oder schon benutzt“ (403).
  2. „Neue Vorlage“ „werkstatt“, beide Muster aus dem Fehler-Ordner übernehmen.
  3. Alle Pflichtfelder, eine Steuerzeile und die Tabelle (Rahmen, Kopf, 4 Grenzen, Arten Nr/Bezeichnung/Menge mit Einheit/Einzelpreis/Gesamt, Ende „Summe netto“) mit Mausaktionen markieren. Koordinaten aus `/api/entwurf/werkstatt/muster/m1/woerter` holen und in Pixel umrechnen.
  4. Probelauf: beide Muster „bestanden“, Werte BW-2026-17 / 285,60 bzw. 297,50, Positionen 2 bzw. 3.
  5. Checkboxen setzen: „Vorlage aktivieren“ wird aktiv (Klick nicht nötig, UAC gibt es auf Linux nicht; Antwort wäre „UAC gibt es nur unter Windows“ → `.alert.err` muss erscheinen, das ist der erwartete Fehlerweg).
  6. Screenshots: 1280 px hell und dunkel (`browser_emulate_media` `colorScheme`), Ansichten Markieren und Probelauf; 390 px hell und dunkel der Vorlagenliste und der Probelauf-Ansicht. Kein seitliches Scrollen der Seite (`document.documentElement.scrollWidth <= innerWidth`), Kontrast lesbar, ein Primär-Button je Ansicht.
  7. `browser_console_messages`: keine Fehler, keine CSP-Verletzung.
  Gefundene Mängel beheben und Schritt 3–7 wiederholen. Screenshots nicht ins Repo.

- [ ] **Step 5: Tests** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen/statisch
git -C /root/ek-wt-lern commit -m "Lernmodus: Probelauf, Aktivieren und Vorlagenliste in der Oberfläche" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
