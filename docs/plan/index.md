# erechnung-konverter – Umsetzungsplan (Index)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Jeder Subagent liest **nur** diese Datei (Global Constraints) und seine Task-Datei, bei Bedarf den genannten Abschnitt von `docs/spezifikation.md` (`grep -n '^#' docs/spezifikation.md`, dann `sed -n`).

**Goal:** Eine auf den Drucker „E-Rechnung“ gedruckte Rechnung wird auf dem Windows-PC zur ZUGFeRD-E-Rechnung (EN16931) plus XML; Installation und Update über gm-update.

**Architecture:** Python-Paket `erechnung` (pdfplumber → YAML-Regex-Vorlage → `Decimal`-Modell mit Pflicht-Summenabgleich → CII-XML mit lxml → factur-x). Läuft als geplante Aufgabe (SYSTEM) mit Windows-Embeddable-Python 3.14; das ZIP baut die Forgejo-CI auf Linux, gm-update verteilt es signiert.

**Tech Stack:** Python 3.14, pdfplumber, lxml, factur-x 7.9, pyyaml, pytest (+ reportlab nur für Tests), PowerShell 5.1, gm-update 0.1.3, Mustang-CLI (nur gm-claude).

**Spec:** `docs/spezifikation.md`

## Global Constraints

- Sprache: Code-Bezeichner, Kommentare, Meldungen, Commits **deutsch** (Repo-Stil wie gm-update). Commit-Messages kurz, deutsch, mit Zeile `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Shell: jeden Befehl einzeln absetzen, **kein `&&`, kein `;`** in einem Aufruf (Freigabe lehnt das ab). Absolute Pfade; `git -C /root/erechnung-konverter …`.
- Python-Zielversion **3.14** (Embeddable amd64, **3.14.10**). Lokal auf gm-claude gibt es 3.14 ohne pip: Testumgebung `python3 -m venv /root/.venvs/erechnung` und `/root/.venvs/erechnung/bin/pip install -r /root/erechnung-konverter/requirements-dev.txt`, Tests mit `/root/.venvs/erechnung/bin/python -m pytest`. CI testet mit 3.14.
- Laufzeit-Abhängigkeiten **nur** pdfplumber, lxml, factur-x, pyyaml (plus deren Abhängigkeiten). Keine weiteren ohne Begründung im Commit.
- Geld immer `decimal.Decimal`, nie `float`. Rundung `ROUND_HALF_UP` auf `Decimal("0.01")`.
- Paketname `erechnung`, Produktname `erechnung-konverter`, Aufgabe `\GM-IT\E-Rechnung`, Drucker `E-Rechnung`, Programmordner `%ProgramFiles%\GM-IT\erechnung-konverter`, Datenwurzel Standard `C:\E-Rechnung` mit `Eingang`, `E-Rechnungen`, `Originale`, `Fehler`.
- ZIP-Name `erechnung-konverter-<v>-windows-amd64.zip`; Inhalt `python\`, `app\erechnung\`, `einrichten\`.
- **Keine Secrets** im Repo (Token, Passwörter, API-Keys). Lexware-Key liegt in `/root/.config/gm-it-os/lexware.env`, Paket-Token in `/root/.config/gm-it-os/update-test.token` bzw. `FORGEJO_PAKET_TOKEN` in `/root/ai-os/.env` – nie ausgeben, nie committen.
- **Keine echten Kundendaten im Repo.** Echte Lexware-PDFs/XMLs nur in `/root/erechnung-testdaten/` (0700). Tests mit echten Daten: Marker `echt`, laufen nur mit Umgebungsvariable `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten`.
- Verkäuferdaten (USt-IdNr., IBAN) stehen nicht im Repo, sondern in `konfig.json` auf dem Gerät; Tests nutzen erfundene Werte (IBAN `DE02120300000000202051`, USt-IdNr. `DE123456789`).
- Parallel laufende Tasks: nur die eigenen Dateien `git add`en (nie `-A`, außer Task 01), vor dem Push `git -C /root/erechnung-konverter pull --rebase origin main`. Fehlt das venv, anlegen (Befehle oben, idempotent).
- Commit direkt auf `main` und `git push origin main` nach jedem Task (Repo ist neu, ein Entwickler). In `/root/ai-os` ändert kein Subagent etwas; Projektstand zieht die Hauptsitzung nach.
- Grundschutz: Spezifikation Abschnitt 10 gilt; neue Abweichungen dort eintragen.
- Schnittstellen-Namen exakt wie in den Task-Dateien („Interfaces“). Abweichung nur, wenn alle späteren Tasks mitgezogen werden.

## Taskliste

| Nr | Datei | Titel | Wer | Umfang | Hängt ab von | Status |
|---|---|---|---|---|---|---|
| 01 | `task-01-geruest-modell.md` | Gerüst, Modell, Summenabgleich | Subagent | 45 Min. | – | offen |
| 02 | `task-02-testdaten.md` | Testhilfen, Lexware-Testdaten, Betragsleser | Subagent | 45 Min. | 01 (nur Step 0) | offen |
| 03 | `task-03-cii-facturx.md` | CII-XML (EN16931) und Einbetten mit factur-x | Subagent | 60 Min. | 01, 02 | offen |
| 04 | `task-04-vorlagen.md` | Vorlagen-Auswertung und Vorlage Lexware | Subagent | 75 Min. | 01, 02 | offen |
| 05 | `task-05-ueberwacher.md` | Überwacher, Konfiguration, CLI | Subagent | 60 Min. | 03, 04 | offen |
| 06 | `task-06-paket-ci.md` | CI (Tests, Paket), Windows-ZIP, Release-CI | Subagent | 60 Min. | 01 | offen |
| 07 | `task-07-einrichtung.md` | `einrichten.ps1`, `gm-update.json`, Runbook | Subagent | 45 Min. | – | offen |
| 08 | `task-08-pruefung.md` | Mustang-Prüfung, Echt-Tests gegen Lexware-XML | Subagent | 30 Min. | 02, 05 | offen |
| 09 | `task-09-release-010.md` | Tag `v0.1.0`, CI grün, Artefakt prüfen | Claude (Hauptsitzung) | 15 Min. | 06, 07, 08 | offen |
| 10 | `task-10-vm-test-app.md` | VM 108: Einrichtung und Druck ohne Freigabe | Subagent | 90 Min. | 09 | offen |
| 11 | `task-11-freigabe-010.md` | Freigabe `v0.1.0` per YubiKey | **Marvin** | 5 Min. | 09 | offen |
| 12 | `task-12-vm-test-update.md` | VM 108: Erstinstallation über gm-update | Subagent | 30 Min. | 10, 11 | offen |
| 13 | `task-13-vorlage-verfeinern.md` | Vorlage mit gedruckten PDFs verfeinern, `v0.1.1` | Subagent | 45 Min. | 10 | offen |
| 14 | `task-14-freigabe-update-test.md` | Freigabe `v0.1.1` (Marvin), Update-Test auf VM | **Marvin** + Subagent | 30 Min. | 12, 13 | offen |

**Reihenfolge / Wellen (heute Nacht):**
1. Parallel: 01, 02, 07
2. Parallel: 03, 04, 06 (03 und 04 brauchen zusätzlich 02)
3. 05, danach 08
4. 09, danach 10 (Kette läuft ohne Marvin bis zur gedruckten E-Rechnung auf der VM)

**Morgen früh (Marvin wach):** 11 → 12, parallel 13 → 14. Vor dem Termin mindestens 11 und 12 erledigt; 13/14 sind Verfeinerung.

## Gemeinsame Schnittstellen (Kurzüberblick)

```python
# erechnung/modell.py (Task 01)
ZWEI = Decimal("0.01")
def runde(x: Decimal) -> Decimal
def betrag(text: str) -> Decimal            # "1.234,56 €" -> Decimal("1234.56")
def datum(text: str) -> datetime.date       # "15.10.2026"
@dataclass class Partei: name, strasse="", plz="", ort="", land="DE", ust_id="", steuernummer="", email="", iban="", bic=""
@dataclass class Position: nr, bezeichnung, menge: Decimal, einheit: str, einzelpreis: Decimal, netto: Decimal, ust_satz: Decimal
@dataclass class Rechnung: nummer, datum, verkaeufer: Partei, kaeufer: Partei, positionen: list[Position],
                           summe_netto, summe_brutto, summe_ust: Decimal|None=None, steuern: dict[Decimal, Decimal]=…,
                           leistungsdatum: date|None=None, faellig: date|None=None, waehrung="EUR", vorlage=""
class SummenFehler(ValueError)
def summenabgleich(r: Rechnung) -> dict[Decimal, tuple[Decimal, Decimal]]   # {satz: (basis, steuer)}
# erechnung/betraege.py (Task 02)
def betraege(xml: bytes) -> dict    # nummer, netto, steuer, brutto, positionen (CII oder UBL)
# erechnung/cii.py (Task 03)
def erzeuge_cii(r: Rechnung, steuern: dict[Decimal, tuple[Decimal, Decimal]]) -> bytes
def bette_ein(pdf: bytes, xml: bytes) -> bytes
# erechnung/vorlagen.py (Task 04)
class VorlagenFehler(ValueError)
def pdf_text(pdf: Path, layout: bool = False) -> str
def lade_vorlagen(*ordner: Path) -> list[dict]
def finde_vorlage(text: str, vorlagen: list[dict]) -> dict
def rechnung_aus_text(text: str, vorlage: dict, verkaeufer: Partei) -> Rechnung
def lies_rechnung(pdf: Path, vorlagen: list[dict], verkaeufer: Partei) -> Rechnung
# erechnung/ueberwachen.py (Task 05)
@dataclass class Konfig: eingang, ausgabe, originale, fehler, arbeit: Path; verkaeufer: Partei; vorlagen: list[dict]
def lade_konfig(datei: Path) -> Konfig
def pruefe_ordner(k: Konfig) -> None                # keine Junction, ein Laufwerk, legt arbeit an
def verarbeite(pdf: Path, k: Konfig) -> Path        # gibt E-Rechnungs-PDF zurück, wirft bei Fehler
def bearbeite(pdf: Path, k: Konfig) -> tuple[bool, str]   # Fehler → Fehler-Ordner + .fehler.txt
def umwandeln(pdf: Path, k: Konfig) -> tuple[bool, str]   # CLI: Kopie verarbeiten
def schritt(k: Konfig) -> int
def ueberwache(k: Konfig, takt: float = 0.5) -> None
```
