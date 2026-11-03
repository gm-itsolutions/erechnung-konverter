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
def test_vorschau_unvollstaendig_und_fehler(lauf):
    s, url, _ = lauf
    lese, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    pdf_kopf = {**schreibe, "Content-Type": "application/pdf"}
    anfrage(s, "POST", "/api/entwurf/werkstatt/muster", werkstatt_pdf(MUSTER1, SUMMEN1), pdf_kopf)
    def vorschau(felder, feld):
        return anfrage(s, "POST", "/api/entwurf/werkstatt/vorschau",
                       json.dumps({"muster": "m1", "feld": feld, "felder": felder}).encode(), schreibe)
    kaeufer = {"seite": "erste", "rahmen": [0.05, 0.2, 0.5, 0.3]}
    st, _, b = vorschau({"kaeufer": kaeufer}, "kaeufer")          # kein nummer-Feld im Entwurf: kein 500
    assert st == 200 and json.loads(b)["fehler"] is None
    assert vorschau({"datum": {"rahmen": [0.1, 0.1, 0.2, 0.2]}}, "datum")[0] == 400
    st, _, b = vorschau({"datum": {"seite": "erste", "rahmen": [0.0, 0.9, 0.05, 0.95]}}, "datum")
    assert st == 200 and json.loads(b)["fehler"]
    assert anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m9/woerter", kopf=lese)[0] == 404
    assert anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m1/seite/2.png", kopf=lese)[0] == 404
def test_content_length_negativ(lauf):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    assert anfrage(s, "POST", "/api/entwurf/werkstatt/muster", b"",
                   {**schreibe, "Content-Type": "application/pdf", "Content-Length": "-1"})[0] == 400
def test_pdf_text_wirft_kein_waisenmuster(lauf, monkeypatch):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    def kaputt(p):
        raise RuntimeError("pdfminer")
    monkeypatch.setattr(srv, "pdf_text", kaputt)
    pdf = werkstatt_pdf(MUSTER1, SUMMEN1)
    assert anfrage(s, "POST", "/api/entwurf/werkstatt/muster", pdf, {**schreibe, "Content-Type": "application/pdf"})[0] == 400
    ordner = tmp / "daten" / "entwuerfe" / "werkstatt" / "muster"
    assert list(ordner.iterdir()) == []
    (ordner / "m1.pdf").write_bytes(pdf)          # Waise ohne .json: Entwurf bleibt lesbar
    st, _, b = anfrage(s, "GET", "/api/entwurf/werkstatt", kopf=lese)
    assert st == 200 and json.loads(b)["muster"] == []
def test_muster_loeschen(lauf):
    s, url, _ = lauf
    lese, schreibe = anmelden(s, url)
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    anfrage(s, "POST", "/api/entwurf/werkstatt/muster", werkstatt_pdf(MUSTER1, SUMMEN1), {**schreibe, "Content-Type": "application/pdf"})
    anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m1/seite/1.png", kopf=lese)
    assert anfrage(s, "DELETE", "/api/entwurf/werkstatt/muster/m1", kopf=schreibe)[0] == 200
    assert anfrage(s, "GET", "/api/entwurf/werkstatt/muster/m1/seite/1.png", kopf=lese)[0] == 404
