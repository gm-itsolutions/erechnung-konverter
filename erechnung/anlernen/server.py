"""Lokale Anlern-Oberfläche, nur 127.0.0.1, Benutzerkontext (docs/lernmodus/spezifikation.md 3)."""
import hmac, json, logging, os, re, secrets, shutil, socket, threading, time
from datetime import date
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit
import pypdfium2 as pdfium
from ..bereiche import FELDER, GERAETE, BereichsFehler, Wort, _betrag, _datum, _feld, _nummer, _tage, feld_text, woerter_aus_pdf
from ..modell import de
from ..ueberwachen import lade_konfig
from ..vorlagen import MIN_ZEICHEN, pdf_text
log = logging.getLogger("erechnung.anlernen")
STATISCH = Path(__file__).parent / "statisch"
NAME, MUSTER = re.compile(r"[a-z0-9][a-z0-9-]{1,39}"), re.compile(r"m[0-9]{1,3}")
MAX_HOEHE = 6000    # Pixel; 1400 breit, A4 = 1980
MAX_SEITEN, DATEINAME = 20, re.compile(r"[\w .-]{1,80}")
LESER = {"nummer": _nummer, "nummer_kontrolle": _nummer, "datum": _datum, "leistungsdatum": _datum, "faellig": _datum,
         "zahlungsziel_tage": _tage, "summe_netto": _betrag, "summe_ust": _betrag, "summe_brutto": _betrag, "nachlass": _betrag}
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
def muster_pfad(z, name, m) -> Path:
    if not MUSTER.fullmatch(m):
        raise Fehler(400, "Muster-ID ungültig")
    p = entwurf_ordner(z, name) / "muster" / f"{m}.pdf"
    if not p.is_file():
        raise Fehler(404, "Muster nicht gefunden")
    return p
def _muster_info(pdf: Path) -> dict:
    return json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
def seiten_von(z, name, m) -> list:
    """Wörter je Seite (relativ 0..1); Text-PDF per pdfplumber, sonst erste OCR-Lesart; gecacht."""
    pdf = muster_pfad(z, name, m)
    cache = pdf.with_suffix(".woerter.json")
    if cache.is_file():
        return [[Wort(*w) for w in s] for s in json.loads(cache.read_text(encoding="utf-8"))]
    if _muster_info(pdf)["text"]:
        seiten = woerter_aus_pdf(pdf)
    else:
        if z.k.ocr is None:
            raise Fehler(409, "Texterkennung nicht verfügbar")
        g = iter(z.k.ocr(pdf))
        try:
            lesart = next(g, None)
        finally:
            getattr(g, "close", lambda: None)()
        if lesart is None or len(lesart) < 3:
            raise Fehler(409, "Texterkennung lieferte keine Wortlage")
        seiten = lesart[2]
    _atomar(cache, json.dumps([[[w.text, *(round(x, 4) for x in w[1:])] for w in s] for s in seiten]).encode())
    return seiten
def _atomar(ziel: Path, daten: bytes) -> None:
    tmp = ziel.with_name(ziel.name + ".tmp")
    tmp.write_bytes(daten)
    os.replace(tmp, ziel)
def _neues_muster(z, name, daten: bytes, dateiname: str):
    if not daten.startswith(b"%PDF-"):
        raise Fehler(400, "keine PDF-Datei")
    ordner = entwurf_ordner(z, name) / "muster"
    for k in range(1, 1000):
        pdf = ordner / f"m{k}.pdf"
        try:
            with open(pdf, "xb") as f:      # atomar: parallele Uploads bekommen verschiedene IDs
                f.write(daten)
            break
        except FileExistsError:
            continue
    else:
        raise Fehler(400, "zu viele Muster")
    try:
        d = pdfium.PdfDocument(pdf)
        try:
            seiten = len(d)
        finally:
            d.close()
        if not 1 <= seiten <= MAX_SEITEN:
            raise ValueError
        n = len(re.findall(r"\w", pdf_text(pdf)))
    except Exception:
        pdf.unlink()
        raise Fehler(400, f"PDF unlesbar oder mehr als {MAX_SEITEN} Seiten") from None
    datei = unquote(dateiname)
    datei = datei if DATEINAME.fullmatch(datei) else "muster.pdf"
    info = {"datei": datei, "seiten": seiten, "text": n >= MIN_ZEICHEN}
    _atomar(pdf.with_suffix(".json"), json.dumps(info, ensure_ascii=False).encode())
    return json_antwort({"id": f"m{k}", **{x: info[x] for x in ("seiten", "text")}})
@route("GET", r"/api/entwurf/([^/]+)")
def _entwurf_lesen(h, z, name):
    o = entwurf_ordner(z, name)
    muster = [{"id": p.stem, **_muster_info(p)} for p in sorted((o / "muster").glob("m*.pdf"), key=lambda p: int(p.stem[1:]))
              if p.with_suffix(".json").is_file()]
    return json_antwort({"vorlage": json.loads((o / "vorlage.json").read_text(encoding="utf-8")), "muster": muster})
@route("PUT", r"/api/entwurf/([^/]+)")
def _entwurf_speichern(h, z, name):
    o = entwurf_ordner(z, name)
    v = lies_json(h)
    if not isinstance(v.get("felder", {}), dict):
        raise Fehler(400, "felder muss ein Objekt sein")
    v = {**v, "name": name, "art": "bereiche", "format": 1}
    (o / "vorlage.json").write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")
    return json_antwort({"ok": True})
@route("DELETE", r"/api/entwurf/([^/]+)")
def _entwurf_loeschen(h, z, name):
    shutil.rmtree(entwurf_ordner(z, name))
    return json_antwort({"ok": True})
@route("POST", r"/api/entwurf/([^/]+)/muster")
def _muster_hoch(h, z, name):
    entwurf_ordner(z, name)
    try:
        n = int(h.headers.get("Content-Length", ""))
    except ValueError:
        raise Fehler(400, "Content-Length fehlt") from None
    if n < 0:
        raise Fehler(400, "Content-Length ungültig")
    if n > MAX_PDF:
        raise Fehler(413, "PDF zu groß")
    return _neues_muster(z, name, h.rfile.read(n), h.headers.get("X-Dateiname", ""))
@route("POST", r"/api/entwurf/([^/]+)/muster-aus-fehler")
def _muster_aus_fehler(h, z, name):
    datei = lies_json(h).get("datei")
    if not isinstance(datei, str) or datei not in {p.name for p in z.k.fehler.glob("*.pdf") if p.is_file()}:
        raise Fehler(400, "Datei steht nicht im Fehlerordner")
    p = z.k.fehler / datei
    if p.stat().st_size > MAX_PDF:
        raise Fehler(413, "PDF zu groß")
    return _neues_muster(z, name, p.read_bytes(), quote(datei))
@route("DELETE", r"/api/entwurf/([^/]+)/muster/([^/]+)")
def _muster_loeschen(h, z, name, m):
    muster_pfad(z, name, m)
    for p in (entwurf_ordner(z, name) / "muster").glob(f"{m}.*"):
        p.unlink()
    for p in (entwurf_ordner(z, name) / "muster").glob(f"{m}-*.png"):
        p.unlink()
    return json_antwort({"ok": True})
@route("GET", r"/api/entwurf/([^/]+)/muster/([^/]+)/seite/([0-9]{1,3})\.png")
def _seitenbild(h, z, name, m, s):
    pdf, s = muster_pfad(z, name, m), int(s)
    if not 1 <= s <= _muster_info(pdf)["seiten"]:
        raise Fehler(404, "Seite nicht vorhanden")
    png = pdf.with_name(f"{m}-{s}.png")
    if not png.is_file():
        d = pdfium.PdfDocument(pdf)
        try:
            seite = d[s - 1]
            b, hoehe = seite.get_size()
            if b < 1 or hoehe < 1 or hoehe * 1400 / b > MAX_HOEHE:
                raise Fehler(400, "Seitenformat ungültig")
            tmp = png.with_name(png.name + ".tmp")
            seite.render(scale=1400 / b).to_pil().save(tmp, format="PNG")
            os.replace(tmp, png)
        finally:
            d.close()
    return 200, "image/png", png.read_bytes()
@route("GET", r"/api/entwurf/([^/]+)/muster/([^/]+)/woerter")
def _woerter(h, z, name, m):
    return json_antwort([[[w.text, *(round(x, 4) for x in w[1:])] for w in s] for s in seiten_von(z, name, m)])
def _lesbar(feld: str, text: str) -> str:
    if feld == "kaeufer":
        return text
    wert = LESER[feld](text)
    return wert.strftime("%d.%m.%Y") if isinstance(wert, date) else de(wert) if isinstance(wert, Decimal) else str(wert)
@route("POST", r"/api/entwurf/([^/]+)/vorschau")
def _vorschau(h, z, name):
    k = lies_json(h)
    feld, felder = k.get("feld"), k.get("felder")
    if feld not in FELDER or not isinstance(felder, dict) or feld not in felder:
        raise Fehler(400, "feld/felder ungültig")
    try:
        for n, f in felder.items():
            _feld(f, n)
    except BereichsFehler as e:
        raise Fehler(400, str(e)) from None
    pdf = muster_pfad(z, name, k.get("muster") if isinstance(k.get("muster"), str) else "")
    seiten, text = seiten_von(z, name, pdf.stem), _muster_info(pdf)["text"]
    try:
        r = feld_text(seiten, {"name": name, "felder": felder}, feld, ocr=not text)
        if r is None:
            return json_antwort({"zeilen": [], "wert": None, "fehler": "Anker nicht gefunden"})
        zeilen = r[1]
        if not " ".join(zeilen).strip():
            return json_antwort({"zeilen": zeilen, "wert": None, "fehler": "Rahmen enthält keinen Text"})
        return json_antwort({"zeilen": zeilen, "wert": _lesbar(feld, " / ".join(zeilen) if feld == "kaeufer" else " ".join(zeilen)),
                             "fehler": None})
    except ValueError as e:        # BereichsFehler ist ein ValueError
        return json_antwort({"zeilen": [], "wert": None, "fehler": str(e)})
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
