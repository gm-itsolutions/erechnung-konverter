# Task 08: Anlern-Server – Entwürfe, Muster, Seitenbilder, Wörter, Vorschau

Spezifikation: `docs/lernmodus/spezifikation.md` 4, 7.1, 7.2. Global Constraints in `index.md`.

**Files:**
- Create: `tests/test_anlernen_endpunkte.py`
- Modify: `erechnung/anlernen/server.py` (Routen ergänzen)

**Interfaces:**
- Consumes: Task 07 (`route`, `Fehler`, `json_antwort`, `lies_json`, `entwurf_ordner`, `NAME`, `MUSTER`, `MAX_PDF`, Testhilfen `lauf`, `anfrage`, `anmelden`); `bereiche.woerter_aus_pdf`, `feld_text`, `_feld`, `BereichsFehler` (Task 01–02); `bereiche._nummer`, `_datum`, `_tage`, `_betrag` (Task 03); `vorlagen.MIN_ZEICHEN`, `vorlagen.pdf_text`; `Konfig.ocr` (liefert `(text, seiten)`, Task 05); `modell.de`.
- Produces:
  - `muster_pfad(z, name, m) -> Path`, `seiten_von(z, name, m) -> list[Seite]` (gecacht in `m<k>.woerter.json`; Task 09 nutzt sie nicht, liest selbst)
  - HTTP-API siehe Step 3 (alle unter Sitzung; ändernde mit CSRF)

- [ ] **Step 1: Failing tests** – `tests/test_anlernen_endpunkte.py`

```python
import json
from erechnung.anlernen import server as srv
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
from test_anlernen_server import anfrage, anmelden, lauf   # noqa: F401 (Fixture)
def test_muster_hochladen_bild_woerter_vorschau(lauf):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    pdf_kopf = {**schreibe, "Content-Type": "application/pdf", "X-Dateiname": "muster.pdf"}
    assert anfrage(s, "POST", "/api/entwurf/werkstatt/muster", b"kein pdf", pdf_kopf)[0] == 400
    st, _, b = anfrage(s, "POST", "/api/entwurf/werkstatt/muster", werkstatt_pdf(MUSTER1, SUMMEN1), pdf_kopf)
    assert st == 200 and json.loads(b) == {"id": "m1", "seiten": 1, "text": True}
    st, k, png = anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m1/seite/1.png", kopf=lese)
    assert st == 200 and k["Content-Type"] == "image/png" and png[:4] == b"\x89PNG"
    st, _, b = anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m1/woerter", kopf=lese)
    assert any(w[0] == "Belegnummer" for w in json.loads(b)[0])
    feld = {"seite": "erste", "rahmen": [0.68, 0.148, 0.95, 0.166], "anker": {"text": "Belegnummer", "rahmen": [0.50, 0.150, 0.60, 0.162]}}
    st, _, b = anfrage(s, "POST", "/api/entwurf/werkstatt/vorschau",
                       json.dumps({"muster": "m1", "feld": "nummer", "felder": {"nummer": feld}}).encode(), schreibe)
    assert st == 200 and json.loads(b)["wert"] == "BW-2026-17"
def test_zu_gross(lauf, monkeypatch):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    monkeypatch.setattr(srv, "MAX_PDF", 100)
    st = anfrage(s, "POST", "/api/entwurf/werkstatt/muster", b"%PDF-" + b"0" * 200,
                 {**schreibe, "Content-Type": "application/pdf"})[0]
    assert st == 413
def test_aus_fehlerordner_nur_aus_liste(lauf):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    (tmp / "Fehler" / "20261105-rechnung.pdf").write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    stand = json.loads(anfrage(s, "GET", "/api/stand", kopf=lese)[2])
    assert stand["fehlerordner"] == ["20261105-rechnung.pdf"]
    pfad = "/api/entwurf/werkstatt/muster-aus-fehler"
    assert anfrage(s, "POST", pfad, json.dumps({"datei": "../prog/konfig.json"}).encode(), schreibe)[0] == 400
    assert anfrage(s, "POST", pfad, json.dumps({"datei": "20261105-rechnung.pdf"}).encode(), schreibe)[0] == 200
def test_entwurf_speichern_und_loeschen(lauf):
    s, url, _ = lauf
    lese, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    v = {"name": "egal", "felder": {"nummer": {"seite": "erste", "rahmen": [0.1, 0.1, 0.2, 0.2]}}}
    assert anfrage(s, "PUT", "/api/entwurf/werkstatt", json.dumps(v).encode(), schreibe)[0] == 200
    e = json.loads(anfrage(s, "GET", "/api/entwurf/werkstatt", kopf=lese)[2])
    assert e["vorlage"]["name"] == "werkstatt" and e["vorlage"]["art"] == "bereiche" and "nummer" in e["vorlage"]["felder"]
    assert anfrage(s, "DELETE", "/api/entwurf/werkstatt", kopf=schreibe)[0] == 200
    assert anfrage(s, "GET", "/api/entwurf/werkstatt", kopf=lese)[0] == 404
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_anlernen_endpunkte.py -q`

- [ ] **Step 3: Endpunkte** – mit `@route` in `server.py`. `muster_pfad(z, name, m)`: `MUSTER.fullmatch(m)` sonst `Fehler(400)`, Datei fehlt → 404.

| Methode, Pfad | Verhalten |
|---|---|
| Methode, Pfad | Verhalten |
|---|---|
| `GET /api/entwurf/<n>` | `{"vorlage": …, "muster": [{"id", "datei", "seiten", "text"}]}` |
| `PUT /api/entwurf/<n>` | Körper = Vorlage (Entwurf, darf unvollständig sein), `name/art/format` werden überschrieben, gespeichert als `vorlage.json` |
| `DELETE /api/entwurf/<n>` | Ordner löschen (`shutil.rmtree`) |
| `POST /api/entwurf/<n>/muster` | Körper PDF (`Content-Length` > `MAX_PDF` → 413, beginnt nicht mit `%PDF-` → 400), nächste freie ID `m1…m999`, `m<k>.pdf` + `m<k>.json` (`datei` aus `X-Dateiname`, nur `[\w .-]{1,80}`, sonst „muster.pdf“; `seiten` per pypdfium2, > 20 → 400; `text` = ≥ `MIN_ZEICHEN` Zeichen per `pdf_text`) |
| `POST /api/entwurf/<n>/muster-aus-fehler` `{datei}` | `datei` muss exakt in der aktuellen Fehlerordner-Liste stehen, sonst 400; dann wie Hochladen (Kopie) |
| `DELETE /api/entwurf/<n>/muster/<m>` | `m<k>.*` löschen |
| `GET /api/entwurf/<n>/muster/<m>/seite/<s>.png` | `s` 1..Seitenzahl; pypdfium2 `render(scale=1400 / breite_pt)`, als `m<k>-<s>.png` zwischenspeichern |
| `GET /api/entwurf/<n>/muster/<m>/woerter` | `seiten_von()`: Text-PDF `woerter_aus_pdf`, sonst `z.k.ocr(pdf)[1]` (kein OCR → 409 „Texterkennung nicht verfügbar“); JSON `[[ [text, x0, top, x1, bottom], … ] je Seite]`, Zahlen auf 4 Stellen |
| `POST /api/entwurf/<n>/vorschau` `{muster, feld, felder}` | Feld mit `bereiche._feld` prüfen (400 bei Fehler), `feld_text(seiten, {"name": n, "felder": felder}, feld, ocr=not text)`; Antwort `{"zeilen", "wert", "fehler"}`, `wert` über `LESER = {"nummer": _nummer, "nummer_kontrolle": _nummer, "datum": _datum, "leistungsdatum": _datum, "faellig": _datum, "zahlungsziel_tage": _tage, "summe_netto": _betrag, "summe_ust": _betrag, "summe_brutto": _betrag, "nachlass": _betrag}` als Text (`str()`, Datum `TT.MM.JJJJ`, Betrag mit `modell.de`); `kaeufer`: `wert` = Zeilen mit „ / “; `ValueError` → `fehler` |


Vorschau nutzt bewusst `feld_text` aus Task 02: Was die Oberfläche zeigt, liest später auch der Überwacher.

- [ ] **Step 4: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen/server.py tests/test_anlernen_endpunkte.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Server-Endpunkte für Entwürfe, Muster, Seitenbilder und Vorschau" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
