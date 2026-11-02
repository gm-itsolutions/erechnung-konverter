"""Lokale Anlern-Oberfläche, nur 127.0.0.1, Benutzerkontext (docs/lernmodus/spezifikation.md 3)."""
import hmac, json, logging, os, re, secrets, socket, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from ..ueberwachen import lade_konfig
log = logging.getLogger("erechnung.anlernen")
STATISCH = Path(__file__).parent / "statisch"
NAME, MUSTER = re.compile(r"[a-z0-9][a-z0-9-]{1,39}"), re.compile(r"m[0-9]{1,3}")
GERAETE = {"con", "prn", "aux", "nul", *(f"{g}{i}" for g in ("com", "lpt") for i in range(1, 10))}   # Windows-Gerätenamen
MAX_PDF, MAX_JSON, LEERLAUF, TOKEN_FRIST = 10 * 1024 * 1024, 64 * 1024, 30 * 60, 60
TYPEN = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".json": "application/json"}
CSP = "default-src 'self'; img-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
class Fehler(Exception):
    def __init__(self, status: int, text: str):
        super().__init__(text)
        self.status = status
class Zustand:
    def __init__(self, konfig: Path, daten: Path, port: int):
        self.konfig, self.daten, self.host = konfig, daten, f"127.0.0.1:{port}"
        (daten / "entwuerfe").mkdir(parents=True, exist_ok=True)
        (daten / "arbeit").mkdir(exist_ok=True)
        self.k = lade_konfig(konfig, arbeit=daten / "arbeit")
        self.token, self.token_bis = secrets.token_urlsafe(32), time.monotonic() + TOKEN_FRIST
        self.sitzung, self.csrf, self.letzte = None, secrets.token_urlsafe(32), time.monotonic()
        self.statisch = {"/statisch/" + p.relative_to(STATISCH).as_posix(): p for p in STATISCH.rglob("*") if p.is_file()}
def gleich(a: str, b: str) -> bool:
    """Zeitkonstanter Vergleich; Nicht-ASCII ergibt False statt TypeError."""
    return hmac.compare_digest(a.encode(), b.encode())
def leerlauf_vorbei(z, jetzt: float) -> bool:
    return jetzt - z.letzte > LEERLAUF
ROUTEN: list = []      # (Methode, Muster, Funktion, ändernd)
def route(methode: str, muster: str):
    def dekor(f):
        ROUTEN.append((methode, re.compile(muster), f, methode != "GET"))
        return f
    return dekor
def json_antwort(obj, status: int = 200):
    return status, "application/json", json.dumps(obj, ensure_ascii=False).encode()
def lies_json(handler) -> dict:
    try:
        n = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        raise Fehler(400, "Content-Length ungültig") from None
    if n > MAX_JSON:
        raise Fehler(413, "Anfrage zu groß")
    try:
        obj = json.loads(handler.rfile.read(n)) if n > 0 else None
    except ValueError:
        raise Fehler(400, "kein gültiges JSON") from None
    if not isinstance(obj, dict):
        raise Fehler(400, "JSON-Objekt erwartet")
    return obj
def _name(name) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in GERAETE:
        raise Fehler(400, "Name ungültig: 2–40 Zeichen a–z, 0–9, Bindestrich")
    return name
def entwurf_ordner(z, name) -> Path:
    o = z.daten / "entwuerfe" / _name(name)
    if not o.is_dir():
        raise Fehler(404, "Entwurf nicht gefunden")
    return o
class Handler(BaseHTTPRequestHandler):
    server_version = "erechnung"
    sys_version = ""
    timeout = 30            # hängende Clients (falsche Content-Length) halten keinen Thread fest
    def log_message(self, fmt, *a):
        log.info("%s %s", getattr(self, "command", ""), getattr(self, "path", "").split("?")[0])   # nie den Token loggen
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
        try:
            if self.headers.get("Host") != z.host:
                raise Fehler(421, "falscher Host")
            pfad = urlsplit(self.path).path
            if self.command == "GET" and pfad == "/start":
                t = parse_qs(urlsplit(self.path).query).get("t", [""])[0]
                if z.token is None or time.monotonic() > z.token_bis or not gleich(t, z.token):
                    raise Fehler(403, "Start-Link ungültig oder schon benutzt")
                z.token, z.sitzung, z.letzte = None, secrets.token_urlsafe(32), time.monotonic()
                return self._senden(303, "text/plain", b"", (("Location", "/"),
                                    ("Set-Cookie", f"sitzung={z.sitzung}; HttpOnly; SameSite=Strict; Path=/")))
            keks = dict(c.strip().split("=", 1) for c in self.headers.get("Cookie", "").split(";") if "=" in c)
            if z.sitzung is None or not gleich(keks.get("sitzung", ""), z.sitzung):
                raise Fehler(403, "keine Sitzung, bitte über das Startmenü öffnen")
            z.letzte = time.monotonic()         # erst nach Host- und Sitzungsprüfung: Fremde halten den Server nicht wach
            if self.command != "GET" and (not gleich(self.headers.get("X-CSRF", ""), z.csrf)
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
            self._senden(e.status, "application/json", json.dumps({"fehler": str(e)}, ensure_ascii=False).encode())
        except Exception:
            log.exception("Fehler bei %s %s", self.command, self.path.split("?")[0])
            self._senden(500, "application/json", b'{"fehler": "interner Fehler, siehe anlernen.log"}')
    do_GET = do_POST = do_PUT = do_DELETE = _bearbeiten
@route("GET", r"/api/stand")
def _stand(h, z):
    return json_antwort({"entwuerfe": sorted(p.name for p in (z.daten / "entwuerfe").iterdir() if p.is_dir()),
                         "fehlerordner": sorted(p.name for p in z.k.fehler.glob("*.pdf") if p.is_file()),
                         "aktiv": [], "deaktiviert": [], "mitgeliefert": []})       # Vorlagenlisten: Task 10
@route("POST", r"/api/entwurf")
def _entwurf_neu(h, z):
    name = _name(lies_json(h).get("name"))
    o = z.daten / "entwuerfe" / name
    try:
        o.mkdir()
    except FileExistsError:
        raise Fehler(409, "Entwurf gibt es schon") from None
    (o / "muster").mkdir()
    (o / "vorlage.json").write_text(json.dumps({"name": name, "art": "bereiche", "format": 1, "felder": {}},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    return json_antwort({"name": name})
@route("POST", r"/api/beenden")
def _beenden(h, z):
    threading.Thread(target=h.server.shutdown, daemon=True).start()
    return json_antwort({"ok": True})
class Server(ThreadingHTTPServer):
    """Ohne SO_REUSEADDR (unter Windows erlaubt es Mitbinden fremder Prozesse); Windows: SO_EXCLUSIVEADDRUSE."""
    allow_reuse_address = False
    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
def erstelle_server(konfig: Path, daten: Path):
    s = Server(("127.0.0.1", 0), Handler)
    s.z = Zustand(konfig, daten, s.server_address[1])
    return s, f"http://{s.z.host}/start?t={s.z.token}"
def starte(konfig: Path, daten: Path | None = None, oeffnen: bool = True) -> None:
    benutzer = os.environ.get("USERNAME", "")
    if os.name == "nt" and (benutzer.upper() in ("SYSTEM", "") or benutzer.endswith("$")):
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
