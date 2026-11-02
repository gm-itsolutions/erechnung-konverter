# Task 07: Anlern-Server – Sicherheitskern, Start, Leerlauf

Spezifikation: `docs/lernmodus/spezifikation.md` 3.1–3.3, 4. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/anlernen/__init__.py` (leer), `erechnung/anlernen/server.py`, `erechnung/anlernen/statisch/index.html` (Platzhalter: `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="csrf" content="{{csrf}}"><title>E-Rechnung anlernen</title></head><body></body></html>`; Task 11 ersetzt den Inhalt), `tests/test_anlernen_server.py`
- Modify: `erechnung/__main__.py` (Befehl `anlernen`)

**Interfaces:**
- Consumes: `ueberwachen.lade_konfig(datei, arbeit=…)` (Task 06).
- Produces:
  - `erstelle_server(konfig: Path, daten: Path) -> tuple[ThreadingHTTPServer, str]` (Server läuft noch nicht; URL `http://127.0.0.1:<port>/start?t=<token>`); Zustand unter `server.z` (`Zustand`: `konfig, daten, k, token, token_bis, sitzung, csrf, host, letzte, statisch`)
  - `class Fehler(Exception)` mit `status`; `route(methode, muster)` (Dekorator, hängt an `ROUTEN` an; Funktion `(handler, z, *gruppen) -> (status, typ, bytes[, extra_koepfe])`)
  - `json_antwort(obj, status=200)`, `lies_json(handler) -> dict`, `entwurf_ordner(z, name) -> Path`
  - `leerlauf_vorbei(z, jetzt: float) -> bool`; `starte(konfig, daten=None, oeffnen=True)`
  - Testhilfen in `tests/test_anlernen_server.py`: Fixture `lauf`, `anfrage(s, methode, pfad, body, kopf)`, `anmelden(s, url) -> (lese_kopf, schreib_kopf)` (Task 08–10 importieren sie)

- [ ] **Step 1: Failing tests** – `tests/test_anlernen_server.py`

```python
import http.client, json, threading
from pathlib import Path
import pytest
from erechnung.anlernen import server as srv
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
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
def test_token_falsch_und_abgelaufen(lauf, monkeypatch):
    s, url, _ = lauf
    assert anfrage(s, "GET", "/start?t=falsch")[0] == 403
    s.z.token_bis = 0
    assert anfrage(s, "GET", url.split(str(s.server_address[1]), 1)[1])[0] == 403
def test_fremder_host(lauf):
    s, url, _ = lauf
    lese, _ = anmelden(s, url)
    assert anfrage(s, "GET", "/api/stand", kopf={**lese, "Host": "evil.example:80"})[0] == 421
def test_csrf_und_origin(lauf):
    s, url, _ = lauf
    lese, schreibe = anmelden(s, url)
    body = json.dumps({"name": "werkstatt"}).encode()
    assert anfrage(s, "POST", "/api/entwurf", body, {**lese, "Content-Type": "application/json"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, {**schreibe, "Origin": "http://evil.example"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, {**schreibe, "X-CSRF": "x"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf", body, schreibe)[0] == 200
def test_sicherheitskoepfe(lauf):
    s, url, _ = lauf
    lese, _ = anmelden(s, url)
    st, k, html = anfrage(s, "GET", "/", kopf=lese)
    assert st == 200 and "frame-ancestors 'none'" in k["Content-Security-Policy"]
    assert k["X-Content-Type-Options"] == "nosniff" and k["Referrer-Policy"] == "same-origin"
    assert s.z.csrf.encode() in html and b"<script>" not in html
@pytest.mark.parametrize("name", ["../x", "A", "a" * 41, "a/b"])
def test_namen_abgelehnt(lauf, name):
    s, url, _ = lauf
    _, schreibe = anmelden(s, url)
    assert anfrage(s, "POST", "/api/entwurf", json.dumps({"name": name}).encode(), schreibe)[0] in (400, 404)
def test_leerlauf():
    z = type("Z", (), {"letzte": 100.0})()
    assert not srv.leerlauf_vorbei(z, 100.0 + srv.LEERLAUF - 1) and srv.leerlauf_vorbei(z, 100.0 + srv.LEERLAUF + 1)
```
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_anlernen_server.py -q`

- [ ] **Step 3: Sicherheitskern** – `erechnung/anlernen/server.py`

```python
"""Lokale Anlern-Oberfläche, nur 127.0.0.1, Benutzerkontext (docs/lernmodus/spezifikation.md 3)."""
import hmac, json, logging, os, re, secrets, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from ..ueberwachen import lade_konfig
log = logging.getLogger("erechnung.anlernen")
STATISCH = Path(__file__).parent / "statisch"
NAME, MUSTER = re.compile(r"[a-z0-9][a-z0-9-]{1,39}"), re.compile(r"m[0-9]{1,3}")
MAX_PDF, MAX_JSON, LEERLAUF, TOKEN_FRIST = 10 * 1024 * 1024, 64 * 1024, 30 * 60, 60
TYPEN = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".json": "application/json"}
CSP = "default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
class Fehler(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(text); self.status = status
class Zustand:
    def __init__(self, konfig: Path, daten: Path, port: int):
        self.konfig, self.daten, self.host = konfig, daten, f"127.0.0.1:{port}"
        (daten / "entwuerfe").mkdir(parents=True, exist_ok=True)
        (daten / "arbeit").mkdir(exist_ok=True)
        self.k = lade_konfig(konfig, arbeit=daten / "arbeit")
        self.token, self.token_bis = secrets.token_urlsafe(32), time.monotonic() + TOKEN_FRIST
        self.sitzung, self.csrf, self.letzte = None, secrets.token_urlsafe(32), time.monotonic()
        self.statisch = {"/statisch/" + p.relative_to(STATISCH).as_posix(): p for p in STATISCH.rglob("*") if p.is_file()}
def leerlauf_vorbei(z, jetzt: float) -> bool:
    return jetzt - z.letzte > LEERLAUF
ROUTEN: list = []      # (Methode, Muster, Funktion, ändernd)
def route(methode: str, muster: str):
    def dekor(f):
        ROUTEN.append((methode, re.compile(muster), f, methode != "GET"))
        return f
    return dekor
class Handler(BaseHTTPRequestHandler):
    server_version = "erechnung"
    sys_version = ""
    def log_message(self, fmt, *a):
        log.info("%s %s", self.command, self.path.split("?")[0])        # nie den Token loggen
    def _senden(self, status, typ, daten, extra=()):
        self.send_response(status)
        for k, w in (("Content-Type", typ), ("Content-Length", str(len(daten))), ("Content-Security-Policy", CSP),
                     ("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "same-origin"),
                     ("Cache-Control", "no-store"), *extra):
            self.send_header(k, w)
        self.end_headers()
        self.wfile.write(daten)
    def _bearbeiten(self):
        z = self.server.z
        z.letzte = time.monotonic()
        try:
            if self.headers.get("Host") != z.host:
                raise Fehler(421, "falscher Host")
            pfad = urlsplit(self.path).path
            if self.command == "GET" and pfad == "/start":
                t = parse_qs(urlsplit(self.path).query).get("t", [""])[0]
                if z.token is None or time.monotonic() > z.token_bis or not hmac.compare_digest(t, z.token):
                    raise Fehler(403, "Start-Link ungültig oder schon benutzt")
                z.token, z.sitzung = None, secrets.token_urlsafe(32)
                return self._senden(303, "text/plain", b"", (("Location", "/"),
                                    ("Set-Cookie", f"sitzung={z.sitzung}; HttpOnly; SameSite=Strict; Path=/")))
            keks = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
            if z.sitzung is None or not hmac.compare_digest(keks.get("sitzung", ""), z.sitzung):
                raise Fehler(403, "keine Sitzung, bitte über das Startmenü öffnen")
            if self.command != "GET" and (not hmac.compare_digest(self.headers.get("X-CSRF", ""), z.csrf)
                                          or self.headers.get("Origin") != f"http://{z.host}"):
                raise Fehler(403, "CSRF-Prüfung fehlgeschlagen")
            if self.command == "GET" and pfad == "/":
                html = (STATISCH / "index.html").read_text(encoding="utf-8").replace("{{csrf}}", z.csrf)
                return self._senden(200, TYPEN[".html"], html.encode())
            if self.command == "GET" and pfad in z.statisch:
                p = z.statisch[pfad]
                return self._senden(200, TYPEN.get(p.suffix, "application/octet-stream"), p.read_bytes())
            for methode, muster, f, _ in ROUTEN:
                m = muster.fullmatch(pfad)
                if m and methode == self.command:
                    return self._senden(*f(self, z, *m.groups()))
            raise Fehler(404, "nicht gefunden")
        except Fehler as e:
            self._senden(e.status, "application/json", json.dumps({"fehler": str(e)}).encode())
        except Exception:
            log.exception("Fehler bei %s %s", self.command, self.path.split("?")[0])
            self._senden(500, "application/json", b'{"fehler": "interner Fehler, siehe anlernen.log"}')
    do_GET = do_POST = do_PUT = do_DELETE = _bearbeiten
def erstelle_server(konfig: Path, daten: Path):
    s = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    s.z = Zustand(konfig, daten, s.server_address[1])
    return s, f"http://{s.z.host}/start?t={s.z.token}"
```

`_senden` nimmt optional ein viertes Element (zusätzliche Köpfe) aus der Routen-Antwort: `return self._senden(*f(self, z, *m.groups()))` funktioniert, wenn `_senden(status, typ, daten, extra=())`.

- [ ] **Step 4: Erste Endpunkte** – mit `@route` im selben Modul. Hilfen: `json_antwort(obj, status=200)` → `(status, "application/json", json.dumps(obj, ensure_ascii=False).encode())`; `lies_json(h)`: `Content-Length` > `MAX_JSON` → `Fehler(413)`, kein Objekt → `Fehler(400)`; `entwurf_ordner(z, name)`: `NAME.fullmatch` sonst `Fehler(400)`, existiert nicht → `Fehler(404)`.

| Methode, Pfad | Verhalten |
|---|---|
| `GET /api/stand` | `{"entwuerfe": [Namen], "fehlerordner": [*.pdf in k.fehler, sortiert, nur Dateinamen], "aktiv": [], "deaktiviert": [], "mitgeliefert": []}` (Listen der Vorlagen füllt Task 07) |
| `POST /api/entwurf` `{name}` | Ordner `entwuerfe/<name>/muster` anlegen, `vorlage.json` = `{"name", "art": "bereiche", "format": 1, "felder": {}}`; vorhanden → 409 |
| `POST /api/beenden` | Antwort 200, danach `threading.Thread(target=h.server.shutdown).start()` |

- [ ] **Step 5: `starte` und CLI**

```python
def starte(konfig: Path, daten: Path | None = None, oeffnen: bool = True) -> None:
    if os.environ.get("USERNAME", "").upper() in ("SYSTEM", "") or os.environ.get("USERNAME", "").endswith("$"):
        raise SystemExit("Die Anlern-Oberfläche läuft nur als angemeldeter Benutzer, nicht als SYSTEM.")
    daten = daten or Path(os.environ["LOCALAPPDATA"]) / "GM-IT" / "erechnung-konverter" / "anlernen"
    s, url = erstelle_server(konfig, daten)
    def waechter():
        while not leerlauf_vorbei(s.z, time.monotonic()):
            time.sleep(10)
        log.info("30 Minuten ohne Anfrage, Oberfläche beendet")
        s.shutdown()
    threading.Thread(target=waechter, daemon=True).start()
    if oeffnen:
        (os.startfile if hasattr(os, "startfile") else __import__("webbrowser").open)(url)
    try:
        s.serve_forever()
    finally:
        s.server_close()
```

`__main__.py`: Unterbefehl `anlernen --konfig <pfad>`; Log `RotatingFileHandler(<daten>/anlernen.log, 1 MB, 3)` (Ordner vorher anlegen), dann `starte(a.konfig)`. Die Prüfung auf SYSTEM gilt nur unter Windows (`os.name == "nt"`), damit Tests auf Linux laufen.


- [ ] **Step 6: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 7: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen erechnung/__main__.py tests/test_anlernen_server.py
git -C /root/ek-wt-lern commit -m "Lernmodus: lokaler Anlern-Server mit Einmal-Token, CSRF und Leerlauf-Ende" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
