import argparse, logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from . import __version__
def _vorschlag(pdf: Path, mit_ocr: bool) -> int:
    import dataclasses, json, tempfile
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1252 bei umgeleiteter Ausgabe
    from datetime import date
    from decimal import Decimal
    from functools import partial
    from . import ocr
    from .generisch import vorschlag_aus_pdf
    with tempfile.TemporaryDirectory() as arbeit:
        aufruf = ocr.tesseract() if mit_ocr else None
        v = vorschlag_aus_pdf(pdf, partial(ocr.erkenne, arbeit=Path(arbeit), aufruf=aufruf) if aufruf else None)
        d = dataclasses.asdict(v)
        d["steuern"] = {str(satz): str(basis) for satz, basis in v.steuern.items()}
        print(json.dumps(d, ensure_ascii=False, indent=2,
                         default=lambda o: str(o) if isinstance(o, (Decimal, date)) else repr(o)))
    return 0 if v.bestaetigt else 1
def main(argv=None, programm_konfig: Path | None = None) -> int:
    """`programm_konfig` ersetzt in Tests die konfig.json des Programmordners (Befehl `vorlage`)."""
    p = argparse.ArgumentParser(prog="erechnung")
    p.add_argument("--version", action="store_true", help="Version ausgeben (lädt alle Abhängigkeiten, Probe für gm-update)")
    sub = p.add_subparsers(dest="befehl")
    u = sub.add_parser("ueberwachen")
    u.add_argument("--konfig", type=Path, required=True)
    w = sub.add_parser("umwandeln")
    w.add_argument("pdf", type=Path)
    w.add_argument("--konfig", type=Path, required=True)
    n = sub.add_parser("anlernen")
    n.add_argument("--konfig", type=Path, required=True)
    v = sub.add_parser("vorlage")       # erhöht per UAC, aufgerufen von der Anlern-Oberfläche
    v.add_argument("aktion", choices=("aktivieren", "deaktivieren", "reaktivieren", "loeschen"))
    v.add_argument("ziel", help="Entwurfsordner (aktivieren) oder Vorlagenname")
    v.add_argument("--konfig", type=Path, required=True)
    v.add_argument("--benutzer", default="")
    v.add_argument("--ergebnis-id", required=True, help="16 Hex-Zeichen; Datei <Programmordner>\\ergebnisse\\<id>.json")
    vs = sub.add_parser("vorschlag", help="generische Erkennung als JSON ausgeben (Exit 0 = bestätigt, 1 = nicht)")
    vs.add_argument("pdf", type=Path)
    vs.add_argument("--ocr", action="store_true", help="bei PDF ohne Text Tesseract verwenden (falls gefunden)")
    a = p.parse_args(argv)
    if a.version:
        import facturx, lxml, pdfplumber, yaml  # noqa: F401 – Probe: Paket vollständig?
        from . import ueberwachen  # noqa: F401
        print(__version__)
        return 0
    if not a.befehl:
        p.print_usage()
        return 2
    if a.befehl == "vorschlag":
        return _vorschlag(a.pdf, a.ocr)
    if a.befehl == "anlernen":  # Benutzerkontext: kein Log im Programmordner (nur Admins schreiben dort)
        import os
        from .anlernen import server
        daten = Path(os.environ["LOCALAPPDATA"]) / "GM-IT" / "erechnung-konverter" / "anlernen"
        daten.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(daten / "anlernen.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        logging.basicConfig(level=logging.INFO, handlers=[h], format="%(asctime)s %(levelname)s %(message)s")
        try:
            server.starte(a.konfig, daten)
        except Exception:   # unter pythonw sonst unsichtbar
            logging.getLogger("erechnung.anlernen").exception("Start fehlgeschlagen")
            return 1
        return 0
    if a.befehl == "vorlage":
        return _vorlage(a, programm_konfig)
    from .ueberwachen import lade_konfig, ueberwache, umwandeln
    h = RotatingFileHandler(a.konfig.parent / "erechnung.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[h], format="%(asctime)s %(levelname)s %(message)s")
    k = lade_konfig(a.konfig)
    if a.befehl == "ueberwachen":
        ueberwache(k)  # läuft dauerhaft; unter pythonw.exe gibt es kein stdout
        return 1
    ok, text = umwandeln(a.pdf, k)
    print(text)
    return 0 if ok else 1
def _vorlage(a, programm_konfig: Path | None) -> int:
    """Erhöhter Lauf: konfig.json nur aus dem Programmordner, Ergebnis nur nach <Programmordner>\\ergebnisse\\."""
    from .anlernen import erhoehen
    try:
        konfig = erhoehen.pruefe_konfig(a.konfig, programm_konfig or erhoehen.programm_konfig())
        erhoehen.ergebnis_datei(konfig.parent, a.ergebnis_id)    # ungültige ID: gar nichts tun
    except (ValueError, OSError) as e:      # kein Log: der Ordner wäre die Wahl des Benutzers
        print(e, file=sys.stderr)
        return 1
    h = RotatingFileHandler(konfig.parent / "erechnung.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log = logging.getLogger("erechnung.vorlage")
    log.addHandler(h)
    log.setLevel(logging.INFO)
    try:
        return _vorlage_ausfuehren(a, konfig, log)
    finally:
        log.removeHandler(h)
        h.close()
def _vorlage_ausfuehren(a, konfig: Path, log) -> int:
    from .anlernen import erhoehen, verwalten
    benutzer = erhoehen.benutzer_name(a.benutzer)   # stammt aus %USERNAME% des Benutzers: keine Zeilen ins Log schmuggeln
    try:
        if a.aktion == "aktivieren":
            e = verwalten.aktivieren(erhoehen.pruefe_entwurf_pfad(Path(a.ziel)), konfig, benutzer)
        else:
            e = getattr(verwalten, a.aktion)(a.ziel, konfig, benutzer)
    except Exception as x:                  # immer ein Ergebnis für den Server, nie ein Traceback
        e = {"ok": False, "meldung": str(x) if isinstance(x, (ValueError, OSError)) else f"{type(x).__name__}: {x}"}
    log.info("vorlage %s %r (Benutzer %r): %r", a.aktion, Path(a.ziel).name, benutzer, e["meldung"])
    try:
        erhoehen.schreibe_ergebnis(konfig.parent, a.ergebnis_id, e)
    except (ValueError, OSError) as x:
        log.error("Ergebnis %r nicht geschrieben: %s", a.ergebnis_id, x)
        return 1
    return 0 if e["ok"] else 1
if __name__ == "__main__":
    sys.exit(main())
