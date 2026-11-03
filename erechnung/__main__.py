import argparse, logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from . import __version__
def _vorschlag(pdf: Path, mit_ocr: bool) -> int:
    import dataclasses, json, tempfile
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
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="erechnung")
    p.add_argument("--version", action="store_true", help="Version ausgeben (lädt alle Abhängigkeiten, Probe für gm-update)")
    sub = p.add_subparsers(dest="befehl")
    u = sub.add_parser("ueberwachen")
    u.add_argument("--konfig", type=Path, required=True)
    w = sub.add_parser("umwandeln")
    w.add_argument("pdf", type=Path)
    w.add_argument("--konfig", type=Path, required=True)
    v = sub.add_parser("vorschlag", help="generische Erkennung als JSON ausgeben (Exit 0 = bestätigt, 1 = nicht)")
    v.add_argument("pdf", type=Path)
    v.add_argument("--ocr", action="store_true", help="bei PDF ohne Text Tesseract verwenden (falls gefunden)")
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
if __name__ == "__main__":
    sys.exit(main())
