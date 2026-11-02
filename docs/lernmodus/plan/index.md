# Lernmodus – Umsetzungsplan (Index)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Jeder Subagent liest **nur** diese Datei und seine Task-Datei, bei Bedarf den genannten Abschnitt von `docs/lernmodus/spezifikation.md` (`grep -n '^#' …`, dann `sed -n`).

**Goal:** Der Kunde lernt am Windows-PC eine neue Rechnungsvorlage an, indem er Rahmen um die Felder einer Muster-Rechnung zieht; nach Probelauf (Summenabgleich, Mustang) und Admin-Bestätigung wandelt der Überwacher dieses Layout um.

**Architecture:** Neues Vorlagenformat `art: bereiche` (Koordinaten relativ zur Seite plus wörtliche Anker, keine Regex) mit eigenem Leser `erechnung/bereiche.py` auf Wortlisten aus pdfplumber bzw. Tesseract-TSV. Oberfläche = lokaler `http.server` der App auf 127.0.0.1 im Benutzerkontext mit Einmal-Token, Canvas-JS ohne Bibliotheken, GM-webui-Look. Aktivieren über einen per UAC erhöhten CLI-Aufruf, der alles selbst neu prüft und nach `<Programmordner>\vorlagen\angelernt\` schreibt; der Überwacher lädt Änderungen im Takt neu.

**Tech Stack:** Python 3.14 (Embeddable), Standardbibliothek (`http.server`, `secrets`, `hmac`, `ctypes`, `difflib`), pdfplumber, pypdfium2 + pillow (schon im Paket), pyyaml, Tesseract 5.5.3 (Paket), Mustang 2.26.0 (Paket), pytest + reportlab (Test), Playwright-MCP auf gm-claude (Browserprüfung), PowerShell 5.1.

**Spec:** `docs/lernmodus/spezifikation.md` (ergänzt `docs/spezifikation.md`)

## Global Constraints

- Sprache: Bezeichner, Kommentare, Meldungen, Oberfläche, Commits **deutsch**. Commit-Messages kurz, mit Zeile `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Shell: jeden Befehl einzeln, **kein `&&`, kein `;`**. Absolute Pfade, `git -C <repo> …`.
- Arbeitsort: Branch `lernmodus` im Worktree `/root/ek-wt-lern` (`git -C /root/erechnung-konverter worktree add /root/ek-wt-lern lernmodus`, falls nicht vorhanden; Branch vorher aus `lernmodus-plan` anlegen). Nach jedem Task `git push origin lernmodus`. **Kein Merge nach main** ohne Hauptsitzung; Haupt-Klon `/root/erechnung-konverter` nicht umschalten.
- Tests: `/root/.venvs/erechnung/bin/python -m pytest` im Worktree (venv anlegen wie `docs/plan/index.md`, falls fehlt). Vor jedem Commit alle Tests grün, bestehende Tests unverändert grün.
- Python **3.14**. **Keine neue Laufzeit-Abhängigkeit** (erlaubt: pdfplumber, lxml, factur-x, pyyaml und deren Abhängigkeiten, darunter pypdfium2, pillow). Keine neue Test-Abhängigkeit.
- Geld `decimal.Decimal`, nie `float`. Koordinaten `float`, relativ 0..1, Ursprung oben links, auf 4 Nachkommastellen gerundet gespeichert.
- Vorlagen mit `art: bereiche` enthalten **nie** Regex; Code baut aus Ankertexten nur wörtliche Vergleiche. Feste Muster im Code ohne verschachtelte Wiederholung.
- Server nur `127.0.0.1`, nie `0.0.0.0`; Prozess im Benutzerkontext. Sicherheitsregeln Spezifikation 3.3 sind nicht verhandelbar.
- Oberfläche: GM-webui (`/root/ai-os/50-vorlagen/webui/README.md` lesen). `gm.css`, `fonts/`, `logo.png`, `favicon.svg` unverändert kopieren; eigenes CSS nur in `app.css` mit Tokens; kein CDN, kein Framework, kein Inline-Skript (CSP).
- Pfade: Programmordner `%ProgramFiles%\GM-IT\erechnung-konverter`, aktive angelernte Vorlagen `<konfig-ordner>\vorlagen\angelernt\`, Entwürfe `%LOCALAPPDATA%\GM-IT\erechnung-konverter\anlernen\` (in Tests immer per Parameter `daten: Path` ersetzbar).
- **Entscheidungen F1–F3** (Spezifikation 11): Verwalten nur per UAC; Export nur `vorlage.yml` ohne Muster-PDFs; erste Prignitz-Markt-Vorlage lernt Marvin mit dem Kunden an.
- **Keine Secrets, keine echten Kundendaten** im Repo; Tests mit erfundenen Daten (`tests/hilfen.py`: `VERKAEUFER`). Echte PDFs nur `/root/erechnung-testdaten/`.
- **Testdaten fremder Layouts:** `werkzeuge/fremdrechnungen.py` erzeugt deterministisch Rechnungen in sieben fremden Layouts (A–G) nach `/root/erechnung-testdaten/fremd/` (`<layout>-<n>.pdf`, je Layout ein `<layout>-1-bild.pdf`, je Datei `.soll.json` mit Sollwerten und erwartetem Verhalten). Erzeugen: `/root/.venvs/erechnung/bin/python /root/ek-wt-lern/werkzeuge/fremdrechnungen.py` (fehlt der Ordner, zuerst ausführen). Unit-Tests bleiben bei `tests/hilfen_bereiche.py` (CI hat den Ordner nicht); die fremden Layouts dienen zur Gegenprobe in Task 04, 05, 09, 11, 12, 14. Grenzfälle mit erwartetem Fehler: C (Datum mit Monatsnamen), F (§ 19 UStG, Satz 0).
- In `/root/ai-os` ändert kein Subagent etwas.
- Grundschutz: Spezifikation Abschnitt 10 gilt; neue Abweichungen dort eintragen.
- Schnittstellen-Namen exakt wie unten und in den Task-Dateien.

## Taskliste

| Nr | Datei | Titel | Wer | Umfang | Hängt ab von | Status |
|---|---|---|---|---|---|---|
| 01 | `task-01-format-schema.md` | Vorlagenformat `art: bereiche`, Schema, Laden | Subagent | 45 Min. | – | offen |
| 02 | `task-02-woerter-anker.md` | Wörter mit Lage, Zeilen, Anker (Text-PDF) | Subagent | 45 Min. | 01 | offen |
| 03 | `task-03-kopf-summen.md` | Kopf- und Summenfelder, Steuerzeilen | Subagent | 45 Min. | 02 | offen |
| 04 | `task-04-positionen.md` | Positionstabelle, Folgeseiten, Übertrag, Skalierung; `lies_rechnung` | Subagent | 60 Min. | 03 | offen |
| 05 | `task-05-ocr-woerter.md` | Texterkennung mit Wortlage (TSV), Bereiche bei Bild-PDF | Subagent | 45 Min. | 04, 06 | offen |
| 06 | `task-06-ueberwacher-neuladen.md` | Überwacher: `angelernt`, tolerant, Neuladen | Subagent | 30 Min. | 01 | offen |
| 07 | `task-07-server-sicherheit.md` | Anlern-Server: Token, Cookie, CSRF, Host, Leerlauf, CLI | Subagent | 60 Min. | 06 | offen |
| 08 | `task-08-server-endpunkte.md` | Server: Entwürfe, Muster, Seitenbilder, Wörter, Vorschau | Subagent | 60 Min. | 03, 05, 07 | offen |
| 09 | `task-09-verwalten.md` | Probelauf, Aktivieren, Verwalten, Export `vorlage.yml` (Logik) | Subagent | 60 Min. | 04, 05, 06, 07 | offen |
| 10 | `task-10-uac-routen-cli.md` | UAC-Aufruf, Verwaltungs-Routen, CLI `vorlage` | Subagent | 45 Min. | 08, 09 | offen |
| 11 | `task-11-ui-markieren.md` | Oberfläche: Muster und Markieren (Canvas, GM-Look) | Subagent | 90 Min. | 08 | offen |
| 12 | `task-12-ui-probelauf.md` | Oberfläche: Probelauf, Aktivieren, Vorlagenliste; Playwright | Subagent | 75 Min. | 10, 11 | offen |
| 13 | `task-13-einrichtung.md` | `einrichten.ps1` (Startmenü, Ordner), Paket, Runbook | Subagent | 40 Min. | 10 | offen |
| 14 | `task-14-release-vm.md` | Merge, Release 0.2.0, Freigabe, Abnahme VM 108 | Hauptsitzung + **Marvin** + Subagent | 150 Min. | alle | offen |

**Reihenfolge:** 01 → 02 → 03 → 04; parallel nach 01: 06 → 07. Dann 05 (braucht 04 und 06) → 08 → 09 → 10; 11 nach 08 parallel zu 09/10; dann 12 und 13 parallel; zuletzt 14.
Parallele Tasks: nur eigene Dateien `git add`, vor dem Push `git -C /root/ek-wt-lern pull --rebase origin lernmodus`. Dateien, die mehrere Tasks ändern (`bereiche.py`, `vorlagen.py`, `ueberwachen.py`, `server.py`, `anlernen.js`), werden nie von zwei gleichzeitig laufenden Tasks angefasst; die Reihenfolge oben stellt das sicher.

## Gemeinsame Schnittstellen

```python
# erechnung/bereiche.py
class BereichsFehler(ValueError)                                                     # Task 01
FORMAT = 1; PFLICHT_FELDER; FELDER; SPALTEN; NAME
def pruefe_bereichsvorlage(v: dict) -> dict
class Wort(NamedTuple): text: str; x0: float; top: float; x1: float; bottom: float  # Task 02, relativ 0..1
Seite = list[Wort]; RAND = 0.005; BETRAG; DATUM; SATZ
def woerter_aus_pdf(pdf: Path) -> list[Seite]
def zeilen(woerter: Seite) -> list[list[Wort]]
def treffer(seite: Seite, text: str, ocr: bool = False) -> list[tuple[float, float, float, str | None]]  # (x0, top, x1, Satz)
def finde_anker(seiten, anker: dict, seite: str, ocr: bool = False) -> tuple[int, float, float] | None  # (Seite, dx, dy)
def woerter_im_rahmen(seite: Seite, rahmen: list[float], dx: float = 0, dy: float = 0) -> Seite
def feld_text(seiten, v, name, ocr=False, spur=None) -> tuple[int, list[str]] | None
def _betrag(t) -> Decimal; _datum(t) -> date; _tage(t) -> int; _nummer(t) -> str     # Task 03
def kopf_aus_bereichen(seiten, v, ocr=False, spur=None) -> dict
def positionen_aus_bereichen(seiten, v, ocr=False, spur=None) -> tuple[list[Position], list[str]]   # Task 04
def rechnung_aus_bereichen(seiten, v, verkaeufer: Partei, ocr=False, spur=None) -> Rechnung
#   spur wird gefüllt: {feld: {"seite": i, "rahmen": [x0, y0, x1, y1]}}, auch "steuern1", "positionen1" …
# erechnung/vorlagen.py
MAX_BYTES = 64 * 1024                                                                # Task 01
def lade_vorlagen(*ordner: Path, tolerant: bool = False) -> list[dict]
def lies_rechnung(pdf, vorlagen, verkaeufer, ocr=None) -> Rechnung                   # Task 04/05: ocr → str oder (str, list[Seite])
# erechnung/ocr.py (Task 05)
def tsv_woerter(tsv: str, breite: int, hoehe: int) -> Seite
def erkenne_seiten(pdf: Path, arbeit: Path, aufruf: list[str]) -> tuple[str, list[Seite]]
# erechnung/ueberwachen.py (Task 06)
ANGELERNT = "angelernt"
def lade_konfig(datei: Path, arbeit: Path | None = None) -> Konfig     # + Konfig.vorlagen_ordner, Konfig.vorlagen_stand
def vorlagen_stand(ordner: list[Path]) -> tuple
def lade_alle_vorlagen(ordner: list[Path]) -> list[dict]
def aktualisiere_vorlagen(k: Konfig) -> bool
# erechnung/anlernen/server.py (Task 07, 08, 10)
def erstelle_server(konfig: Path, daten: Path) -> tuple[ThreadingHTTPServer, str]   # server.z = Zustand
def route(methode: str, muster: str)        # Dekorator; Funktion (handler, z, *gruppen) -> (status, typ, bytes[, köpfe])
class Fehler(Exception)                      # .status
def json_antwort(obj, status=200); def lies_json(handler) -> dict; def entwurf_ordner(z, name) -> Path
def leerlauf_vorbei(z, jetzt: float) -> bool
def starte(konfig: Path, daten: Path | None = None, oeffnen: bool = True) -> None
# erechnung/anlernen/verwalten.py (Task 09)
MIN_MUSTER = 2
def probelauf(entwurf: Path, k: Konfig) -> dict
def aktivieren(entwurf: Path, konfig: Path, benutzer: str) -> dict          # {"ok", "meldung"}
def deaktivieren(name, konfig, benutzer) -> dict; reaktivieren(...); loeschen(...)
def exportieren(entwurf: Path, ziel: Path) -> Path
# erechnung/anlernen/erhoehen.py (Task 10)
def als_admin(argumente: list[str]) -> int
```

**HTTP-API** (Task 07/08/10; alle Pfade nur mit Sitzungs-Cookie, ändernde zusätzlich `X-CSRF` und `Origin`): `GET /start?t=`, `GET /`, `GET /statisch/…`, `GET /api/stand`, `POST /api/entwurf`, `GET|PUT|DELETE /api/entwurf/<n>`, `POST /api/entwurf/<n>/muster`, `POST /api/entwurf/<n>/muster-aus-fehler`, `DELETE /api/entwurf/<n>/muster/<m>`, `GET /api/entwurf/<n>/muster/<m>/seite/<s>.png`, `GET /api/entwurf/<n>/muster/<m>/woerter`, `POST /api/entwurf/<n>/vorschau`, `POST /api/entwurf/<n>/probelauf`, `POST /api/entwurf/<n>/aktivieren`, `GET /api/entwurf/<n>/export`, `POST /api/vorlage/<name>/(deaktivieren|reaktivieren|loeschen)`, `POST /api/beenden`.

**CLI:** `python -m erechnung anlernen --konfig <konfig.json>` (Benutzer), `python.exe -m erechnung vorlage (aktivieren <entwurf>|deaktivieren <name>|reaktivieren <name>|loeschen <name>) --konfig … --benutzer … --ergebnis <json>` (erhöht per UAC).

