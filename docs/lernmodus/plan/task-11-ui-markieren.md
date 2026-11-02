# Task 11: Oberfläche – Muster und Markieren (Canvas)

Spezifikation: `docs/lernmodus/spezifikation.md` 3.1, 7.1, 7.2. Global Constraints in `index.md`. **Vorher lesen:** `/root/ai-os/50-vorlagen/webui/README.md` ganz, `index.html` der Vorlage als Bauplan.

**Files:**
- Create: `erechnung/anlernen/statisch/anlernen.js`, `erechnung/anlernen/statisch/app.css`, Kopien aus `/root/ai-os/50-vorlagen/webui/`: `gm.css`, `fonts/` (ganzer Ordner), `logo.png`, `favicon.svg` (unverändert); `werkzeuge/anlernen_demo.py`
- Modify: `erechnung/anlernen/statisch/index.html` (Platzhalter aus Task 07 ersetzen)

**Interfaces:**
- Consumes: HTTP-API aus Task 07/08 (`/api/stand`, `/api/entwurf…`, `/vorschau`, Seitenbilder, Wörter). Probelauf/Aktivieren-API (Task 10) nutzt erst Task 12.
- Produces: `index.html` mit Ansichten `#vorlagen` und `#anlernen` (Hash-Navigation, ein Dokument); in `anlernen.js` die Funktionen `api`, `ladeStand`, `oeffneEntwurf`, `zeichne`, `ankerVorschlag`, `satzPlatzhalter`, `speichern` (Task 12 ergänzt `probelauf`, `zeigeProbelauf`, `aktivieren`, `verwalten`).

- [ ] **Step 1: Demo-Starter** – `werkzeuge/anlernen_demo.py` (nur gm-claude; startet den Server mit Testdaten, ohne Browser, druckt die Start-URL)

```python
"""Anlern-Oberfläche mit synthetischen Mustern starten (Entwicklung/Browserprüfung): python werkzeuge/anlernen_demo.py <ordner>"""
import json, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "tests")]
from erechnung.anlernen.server import erstelle_server
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
basis = Path(sys.argv[1])
for o in ("Eingang", "E-Rechnungen", "Originale", "Fehler", "prog"):
    (basis / o).mkdir(parents=True, exist_ok=True)
(basis / "Fehler" / "20261105-rechnung.pdf").write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
(basis / "Fehler" / "20261106-rechnung.pdf").write_bytes(
    werkstatt_pdf(MUSTER1 + [("3", "Filter", "1 Stk", "10,00", "10,00")], ("250,00", "47,50", "297,50"), dx=0.01, dy=0.02))
konfig = basis / "prog" / "konfig.json"
konfig.write_text(json.dumps({"eingang": str(basis / "Eingang"), "ausgabe": str(basis / "E-Rechnungen"),
    "originale": str(basis / "Originale"), "fehler": str(basis / "Fehler"), "verkaeufer": VERKAEUFER.__dict__}), encoding="utf-8")
s, url = erstelle_server(konfig, basis / "daten")
print(url, flush=True)
s.serve_forever()
```

Start (Hintergrund): `/root/.venvs/erechnung/bin/python /root/ek-wt-lern/werkzeuge/anlernen_demo.py /tmp/anlernen-demo`.

- [ ] **Step 2: `index.html`** – Gerüst nach der Vorlage: `<html lang="de">`, `<meta name="csrf" content="{{csrf}}">`, `<meta name="robots" content="noindex">`, `gm.css`, `app.css`, `favicon.svg`, `<script src="/statisch/anlernen.js" defer>`. Kein Inline-Skript, kein `style=` (CSP).
  - `.sidebar`: Logo, App-Name „E-Rechnung anlernen“, `.nav` mit „Vorlagen“ (`#vorlagen`) und „Anlernen“ (`#anlernen`, `aria-current="page"` je nach Ansicht), unten „Beenden“ (`.btn`, ruft `POST /api/beenden`, dann Text „Oberfläche beendet. Fenster schließen.“).
  - Ansicht `#vorlagen`: `.page-head` „Vorlagen“ + Primär „Neue Vorlage“; `.card` mit `.table-wrap` (Name, Art, Status-`.pill`); Inhalt füllt Task 12. Dialog „Neue Vorlage“ als `.card` mit `.field` (Name, `.hint` „nur Kleinbuchstaben, Ziffern und Bindestrich“) und `.actions`.
  - Ansicht `#anlernen`: `.page-head` mit `h1` „Vorlage anlernen: <name>“, Aktionen rechts (Primär „Probelauf“ – Task 12). Darunter zwei Spalten (`app.css`: `.lern-raster { display: grid; grid-template-columns: minmax(16rem, 22rem) 1fr; gap: var(--…) }`, Token-Namen aus `gm.css` nehmen):
    - links `.card` „Muster“: Liste der Muster (Dateiname, Seitenzahl, `.pill` „Text“/„Bild, Texterkennung“), Knopf „Datei hinzufügen“ (`<input type="file" accept="application/pdf">`, Upload als `application/pdf`), Auswahl „Aus Fehler-Ordner übernehmen“ (`<select>` mit `stand.fehlerordner`); darunter `.card` „Felder“: Pflichtfelder (Rechnungsnummer, Rechnungsdatum, Käufer, Summe netto, Gesamtbetrag, Positionen), dann optionale (Zweite Fundstelle der Nummer, Leistungsdatum, Fälligkeit, Zahlungsziel in Tagen, Umsatzsteuer gesamt, Steuerzeile, Nachlass); je Zeile Status-`.pill` („fehlt“ `warn` / „markiert“ `ok`), gelesener Wert in Mono, Knopf „Markieren“, Knopf „Entfernen“; Feld „Erkennungstexte“ (`.field`, kommagetrennt, `.hint` „alle müssen auf jeder Rechnung dieses Layouts stehen“).
    - rechts `.card`: Kopf mit Muster-Auswahl, Seite ‹ n/m ›, Hinweiszeile (was jetzt zu tun ist, z. B. „Rahmen um den Wert der Rechnungsnummer ziehen“); darunter `<canvas aria-label="Seite der Muster-Rechnung">` über einem `<img>` des Seitenbilds (Canvas absolut darüber, gleiche Größe, `app.css`).
  - Unter 900 px: `.alert.warn` „Zum Markieren einen größeren Bildschirm verwenden.“ statt Canvas (CSS `@media`), Listen bleiben lesbar.

- [ ] **Step 3: Kernfunktionen in `anlernen.js`** (vollständig so übernehmen, Rest drumherum bauen)

```javascript
"use strict";
const CSRF = document.querySelector('meta[name="csrf"]').content;
async function api(methode, pfad, body, typ = "application/json") {
  const r = await fetch(pfad, {method: methode, headers: methode === "GET" ? {} : {"X-CSRF": CSRF, "Content-Type": typ},
    body: body === undefined ? undefined : (typ === "application/json" ? JSON.stringify(body) : body)});
  const t = r.headers.get("Content-Type") || "";
  const daten = t.startsWith("application/json") ? await r.json() : await r.blob();
  if (!r.ok) throw new Error(daten.fehler || `Fehler ${r.status}`);
  return daten;
}
const r4 = (x) => Math.round(x * 10000) / 10000;
function relativ(ev, canvas) {   // Mausposition → Seitenkoordinaten 0..1
  const b = canvas.getBoundingClientRect();
  return {x: Math.min(1, Math.max(0, (ev.clientX - b.left) / b.width)), y: Math.min(1, Math.max(0, (ev.clientY - b.top) / b.height))};
}
const mitteY = (w) => (w[2] + w[4]) / 2;           // w = [text, x0, top, x1, bottom]
function umriss(ws) {
  return [r4(Math.min(...ws.map(w => w[1]))), r4(Math.min(...ws.map(w => w[2]))), r4(Math.max(...ws.map(w => w[3]))), r4(Math.max(...ws.map(w => w[4])))];
}
function ankerVorschlag(rahmen, woerter) {
  // 1. Wörter links vom Rahmen in derselben Zeile (zusammenhängend, höchstens 4, Lücke < 0,03)
  const [x0, y0, , y1] = rahmen;
  const links = woerter.filter(w => mitteY(w) >= y0 && mitteY(w) <= y1 && w[3] <= x0 + 0.002).sort((a, b) => b[1] - a[1]);
  const kette = [];
  for (const w of links) {
    if (kette.length && kette[kette.length - 1][1] - w[3] > 0.03) break;
    if (!kette.length && x0 - w[3] > 0.15) break;
    kette.push(w);
    if (kette.length === 4) break;
  }
  // 2. sonst die Zeile direkt darüber, waagerecht überlappend
  if (!kette.length) {
    const drueber = woerter.filter(w => w[4] <= y0 + 0.002 && y0 - w[4] < 0.03 && w[3] > rahmen[0] && w[1] < rahmen[2]);
    const yMax = Math.max(...drueber.map(mitteY));
    kette.push(...drueber.filter(w => Math.abs(mitteY(w) - yMax) < 0.004).sort((a, b) => a[1] - b[1]).slice(0, 4));
  } else {
    kette.sort((a, b) => a[1] - b[1]);
  }
  return kette.length ? {text: kette.map(w => w[0]).join(" "), rahmen: umriss(kette)} : null;
}
function satzPlatzhalter(text) {   // „MwSt. 19 %“ → „MwSt. {satz} %“
  return text.replace(/\d{1,2}(?:[.,]\d{1,2})?(?=\s*%)/, "{satz}");
}
```

  - **Ablauf Feld:** „Markieren“ → Modus `feld:<name>` → Maus ziehen (pointerdown/move/up, gestrichelter Rahmen) → `rahmen` in 0..1 → `anker = ankerVorschlag(...)` (bei `kaeufer` kein Anker) → Feld `{seite: (name in Summen/nachlass/summe_*) ? "letzte" : "erste", rahmen, anker}` (Seite: wenn der Benutzer auf der letzten Seite eines mehrseitigen Musters markiert, `letzte`) → `speichern()` → `POST …/vorschau` → Wert/Fehler in der Liste. Klick auf ein Wort während der Anker-Anzeige setzt den Anker neu (das Wort und rechts angrenzende Wörter derselben Zeile bis zum Rahmen); Knopf „ohne Anker“.
  - **Steuerzeile:** wie Feld; `anker.text = satzPlatzhalter(anker.text)`; fehlt danach `{satz}`, erscheint ein `<select>` (19, 7) → `steuern.satz`. Gespeichert unter `vorlage.steuern = {seite, anker, rahmen[, satz]}`.
  - **Positionen** (Modus in Schritten, Hinweiszeile führt): (a) Rahmen um die Tabelle ohne Kopfzeile ziehen → `links = x0`, letzte Spaltengrenze `x1`, `unten = y1` (Vorschlag); (b) Kopfzeile anklicken → `kopf = {text: erste 3 Wörter der Zeile innerhalb links..x1, rahmen: umriss}`; (c) Spaltengrenzen per Klick (senkrechte Linien, Klick auf vorhandene Linie entfernt sie), je Spalte ein `<select>` unter dem Bild mit den Arten aus `SPALTEN` in Deutsch (Pos.-Nr., Bezeichnung, Menge, Einheit, Menge mit Einheit, Einzelpreis, USt-Satz, Gesamt netto, ignorieren); (d) optional „Ende der Tabelle“: Wort anklicken (z. B. „Zwischensumme“) → `ende`; (e) optional „Fußbereich“: waagerechte Linie anklicken → `unten`. `ust_satz` per `<select>` (19, 7), wenn keine Spalte USt-Satz.
  - **Erkennungstexte:** Vorschlag beim ersten Speichern: Ankertext der Nummer plus längste Zeile im oberen Viertel der ersten Seite (Wörter mit `top < 0.25` nach Zeile gruppiert, max. 80 Zeichen); Eingabe überschreibt.
  - **Zeichnen:** `zeichne()` zeichnet alle markierten Rahmen der aktuellen Seite (Wert: Farbe aus `getComputedStyle(document.documentElement).getPropertyValue("--amber")`, Anker: Token für `info`, Tabelle/Spalten: Token für Text gedämpft), Beschriftung in IBM Plex Mono klein. Keine Hex-Werte in JS oder `app.css`. Wort unter der Maus dünn umrandet.
  - **Speichern:** `speichern()` entprellt (500 ms) `PUT /api/entwurf/<name>` mit der ganzen Vorlage. Fehler → `.alert.err` oben.
  - Esc bricht den aktuellen Modus ab. Alle Knöpfe als `<button type="button">` mit Text.

- [ ] **Step 4: Sichtprüfung (kurz)** – Demo starten (Step 1), per Playwright-MCP `browser_navigate` auf die gedruckte URL, Entwurf „werkstatt“ anlegen, Muster aus dem Fehler-Ordner übernehmen, Rechnungsnummer per `browser_drag`/Mausaktionen markieren (Rahmen um „BW-2026-17“), prüfen: Liste zeigt „BW-2026-17“ und Anker „Belegnummer“. Ein Screenshot 1280 px hell genügt hier; die volle Prüfung macht Task 12. Konsole ohne Fehler (`browser_console_messages`), insbesondere keine CSP-Verletzung.

- [ ] **Step 5: Tests** – `/root/.venvs/erechnung/bin/python -m pytest -q` (Server-Tests prüfen weiter `{{csrf}}`-Ersetzung und kein `<script>` ohne `src`).

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen/statisch werkzeuge/anlernen_demo.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Oberfläche zum Markieren im GM-Look" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```

Fehlt ein Baustein in `gm.css` wirklich (z. B. Canvas-Überlagerung), in `app.css` mit Tokens bauen und im Commit-Text nennen (webui-Skill, Schritt 3).
