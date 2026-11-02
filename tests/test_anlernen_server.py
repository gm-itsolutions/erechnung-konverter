import http.client, json, socket, threading, time
from pathlib import Path
import pytest
from erechnung import __main__ as cli
from erechnung.anlernen import server as srv
from hilfen import VERKAEUFER
@pytest.fixture
def lauf(tmp_path):
    for o in ("Eingang", "E-Rechnungen", "Originale", "Fehler"):
        (tmp_path / o).mkdir()
    konfig = tmp_path / "prog" / "konfig.json"
    konfig.parent.mkdir()
    konfig.write_text(json.dumps({"eingang": str(tmp_path / "Eingang"), "ausgabe": str(tmp_path / "E-Rechnungen"),
        "originale": str(tmp_path / "Originale"), "fehler": str(tmp_path / "Fehler"), "verkaeufer": VERKAEUFER.__dict__}), encoding="utf-8")
    s, url = srv.erstelle_server(konfig, tmp_path / "daten")
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s, url, tmp_path
    s.shutdown()
    s.server_close()
def anfrage(s, methode, pfad, body=b"", kopf=None):
    c = http.client.HTTPConnection("127.0.0.1", s.server_address[1], timeout=10)
    c.request(methode, pfad, body=body, headers=kopf or {})
    r = c.getresponse()
    return r.status, dict(r.getheaders()), r.read()
def anmelden(s, url):
    st, k, _ = anfrage(s, "GET", url.split(str(s.server_address[1]), 1)[1])
    assert st == 303
    keks = k["Set-Cookie"].split(";")[0]
    o = f"http://127.0.0.1:{s.server_address[1]}"
    return {"Cookie": keks}, {"Cookie": keks, "X-CSRF": s.z.csrf, "Origin": o, "Content-Type": "application/json"}
def test_ohne_sitzung_403(lauf):
    s, url, _ = lauf
    assert anfrage(s, "GET", "/")[0] == 403
    assert anfrage(s, "GET", "/api/stand")[0] == 403
def test_token_einmalig_und_cookie_flags(lauf):
    s, url, _ = lauf
    pfad = url.split(str(s.server_address[1]), 1)[1]
    st, k, _ = anfrage(s, "GET", pfad)
    assert st == 303 and "HttpOnly" in k["Set-Cookie"] and "SameSite=Strict" in k["Set-Cookie"]
    assert anfrage(s, "GET", pfad)[0] == 403
def test_token_falsch_und_abgelaufen(lauf):
    s, url, _ = lauf
    assert anfrage(s, "GET", "/start?t=falsch")[0] == 403
    s.z.token_bis = 0
    assert anfrage(s, "GET", url.split(str(s.server_address[1]), 1)[1])[0] == 403
def test_fremder_host(lauf):
    s, url, _ = lauf
    lese, _ = anmelden(s, url)
    assert anfrage(s, "GET", "/api/stand", kopf={**lese, "Host": "evil.example:80"})[0] == 421
def test_csrf_und_origin(lauf):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    body = json.dumps({"name": "werkstatt"}).encode()
    assert anfrage(s, "POST", "/api/entwurf", body, {**lese, "Content-Type": "application/json"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, {**schreibe, "Origin": "http://evil.example"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, {**schreibe, "X-CSRF": "x"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, schreibe)[0] == 200
    assert json.loads((tmp / "daten" / "entwuerfe" / "werkstatt" / "vorlage.json").read_text(encoding="utf-8")) == \
        {"name": "werkstatt", "art": "bereiche", "format": 1, "felder": {}}
    assert anfrage(s, "POST", "/api/entwurf", body, schreibe)[0] == 409
def test_stand(lauf):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    (tmp / "Fehler" / "b.pdf").write_bytes(b"%PDF-")
    (tmp / "Fehler" / "a.pdf").write_bytes(b"%PDF-")
    (tmp / "Fehler" / "a.fehler.txt").write_text("x")
    anfrage(s, "POST", "/api/entwurf", json.dumps({"name": "werkstatt"}).encode(), schreibe)
    st, _, b = anfrage(s, "GET", "/api/stand", kopf=lese)
    assert st == 200 and json.loads(b) == {"entwuerfe": ["werkstatt"], "fehlerordner": ["a.pdf", "b.pdf"],
                                           "aktiv": [], "deaktiviert": [], "mitgeliefert": ["lexware-gm-it"]}   # Listen: Task 10
def test_sicherheitskoepfe(lauf):
    s, url, _ = lauf
    lese, _ = anmelden(s, url)
    st, k, html = anfrage(s, "GET", "/", kopf=lese)
    assert st == 200 and "frame-ancestors 'none'" in k["Content-Security-Policy"]
    assert k["X-Content-Type-Options"] == "nosniff" and k["Referrer-Policy"] == "same-origin"
    assert k["Cache-Control"] == "no-store"
    assert s.z.csrf.encode() in html and b"<script>" not in html
@pytest.mark.parametrize("name", ["../x", "A", "a" * 41, "a/b", "con", "nul", "com1", "lpt9"])
def test_namen_abgelehnt(lauf, name):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    assert anfrage(s, "POST", "/api/entwurf", json.dumps({"name": name}).encode(), schreibe)[0] == 400
def test_json_zu_gross_und_kein_objekt(lauf):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    assert anfrage(s, "POST", "/api/entwurf", b"[1]", schreibe)[0] == 400
    assert anfrage(s, "POST", "/api/entwurf", b"{", schreibe)[0] == 400
    gross = json.dumps({"name": "x" * srv.MAX_JSON}).encode()
    assert anfrage(s, "POST", "/api/entwurf", gross, schreibe)[0] == 413
def test_beenden(lauf):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    assert anfrage(s, "POST", "/api/beenden", b"", schreibe)[0] == 200
def test_kein_mitbinden(lauf):
    s, _, _ = lauf
    assert not s.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
    fremd = socket.socket()
    fremd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with fremd, pytest.raises(OSError):
        fremd.bind(s.server_address)
def test_nicht_ascii_403(lauf):
    s, url, _ = lauf
    assert anfrage(s, "GET", "/start?t=%C3%A4")[0] == 403
    _, schreibe = anmelden(s, url)
    assert anfrage(s, "GET", "/", kopf={"Cookie": "sitzung=\u00e4".encode().decode("latin-1")})[0] == 403
    kopf = {**schreibe, "X-CSRF": "\u00e4".encode("latin-1").decode("latin-1")}
    assert anfrage(s, "POST", "/api/entwurf", b'{"name": "ab"}', kopf)[0] == 403
def test_fremde_halten_nicht_wach(lauf):
    s, url, _ = lauf
    s.z.letzte = 0.0
    anfrage(s, "GET", "/api/stand")
    anfrage(s, "GET", "/api/stand", kopf={"Host": "evil.example"})
    assert s.z.letzte == 0.0
    lese, _ = anmelden(s, url)
    s.z.letzte = 0.0
    anfrage(s, "GET", "/api/stand", kopf=lese)
    assert s.z.letzte > 0.0
def test_kaputte_anfragezeile_beantwortet(lauf):
    s, _, _ = lauf
    with socket.create_connection(s.server_address, timeout=10) as c:
        c.sendall(b"GET /" + b"a" * 70000 + b" HTTP/1.1\r\n\r\n")       # Anfragezeile zu lang: self.path fehlt
        assert c.recv(100).startswith(b"HTTP/1.0 414")
def test_handler_timeout():
    assert srv.Handler.timeout == 30
def test_leerlauf():
    z = type("Z", (), {"letzte": 100.0})()
    assert not srv.leerlauf_vorbei(z, 100.0 + srv.LEERLAUF - 1) and srv.leerlauf_vorbei(z, 100.0 + srv.LEERLAUF + 1)
def test_cli_anlernen_ohne_log_im_programmordner(tmp_path, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(srv, "starte", lambda konfig, daten=None: aufrufe.append((konfig, daten)))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lokal"))
    monkeypatch.setattr(cli.logging, "basicConfig", lambda handlers, **_: [x.close() for x in handlers])
    konfig = tmp_path / "prog" / "konfig.json"
    assert cli.main(["anlernen", "--konfig", str(konfig)]) == 0
    daten = tmp_path / "lokal" / "GM-IT" / "erechnung-konverter" / "anlernen"
    assert aufrufe == [(konfig, daten)] and (daten / "anlernen.log").exists()
    assert not (tmp_path / "prog" / "erechnung.log").exists()
