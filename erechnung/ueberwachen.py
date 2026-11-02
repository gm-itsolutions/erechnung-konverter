"""Ordnerüberwachung: Eingang → E-Rechnung oder Fehlerdatei (Spezifikation Abschnitt 3, 6, 7)."""
import json, logging, os, re, shutil, time, traceback
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable
from . import mustang, ocr
from .cii import bette_ein, erzeuge_cii
from .modell import Partei, SummenFehler, summenabgleich
from .vorlagen import OCR_HINWEIS, STANDARD, lade_vorlagen, lies_rechnung
log = logging.getLogger("erechnung")
@dataclass
class Konfig:
    eingang: Path
    ausgabe: Path
    originale: Path
    fehler: Path
    arbeit: Path
    verkaeufer: Partei
    vorlagen: list[dict]
    ocr: Callable[[Path], str] | None = None   # Texterkennung für PDFs ohne Text
    pruefe: Callable[[Path], str] | None = None   # Mustang (XML → Kurzbericht, ValueError wenn ungültig); None → Fehler
    xml_einzeln: bool = False                  # zusätzlich <Nummer>.xml in den Ausgabeordner (Behörden, XRechnung)
def lade_konfig(datei: Path) -> Konfig:
    d = json.loads(datei.read_text(encoding="utf-8-sig"))  # PowerShell schreibt gern mit BOM
    v = Partei(**d["verkaeufer"])
    if not (v.name and (v.ust_id or v.steuernummer) and v.iban):
        raise ValueError("konfig.json: verkaeufer braucht name, ust_id oder steuernummer und iban")
    arbeit, aufruf, pruefer = datei.parent / "arbeit", ocr.tesseract(), mustang.mustang()
    return Konfig(Path(d["eingang"]), Path(d["ausgabe"]), Path(d["originale"]), Path(d["fehler"]),
                  arbeit, v, lade_vorlagen(STANDARD, datei.parent / "vorlagen"),
                  partial(ocr.erkenne, arbeit=arbeit, aufruf=aufruf) if aufruf else None,
                  partial(mustang.pruefe, aufruf=pruefer) if pruefer else None,
                  d.get("xml_einzeln") is True)
def pruefe_ordner(k: Konfig) -> None:
    """Keine Junction/Symlink, alles auf einem Laufwerk (os.replace), Arbeitsordner anlegen."""
    k.arbeit.mkdir(exist_ok=True)
    for o in (k.eingang, k.ausgabe, k.originale, k.fehler, k.arbeit):
        if o.is_symlink() or o.is_junction():
            raise ValueError(f"{o} ist eine Verknüpfung (Junction/Symlink)")
        if not o.is_dir():
            raise ValueError(f"{o} fehlt")
        if o.stat().st_dev != k.arbeit.stat().st_dev:
            raise ValueError(f"{o} liegt nicht auf dem Laufwerk des Arbeitsordners")
def _frei(ordner: Path, name: str, *endungen: str) -> str:
    # ponytail: Prüfen-dann-Verschieben ohne Sperre; nur der Überwacher schreibt in diese Ordner
    basis, n = name, 1
    while any((ordner / f"{basis}{e}").exists() for e in endungen):
        n += 1
        basis = f"{name}-{n}"
    return basis
def verarbeite(pdf: Path, k: Konfig) -> Path:
    if b"%%EOF" not in pdf.read_bytes()[-1024:]:
        raise ValueError("PDF unvollständig (kein %%EOF)")
    r = lies_rechnung(pdf, k.vorlagen, k.verkaeufer, k.ocr)
    try:
        steuern = summenabgleich(r)
    except SummenFehler as e:
        raise SummenFehler(f"{e} ({OCR_HINWEIS})" if r.ocr_text else str(e)) from None
    xml = erzeuge_cii(r, steuern)
    zugferd = bette_ein(pdf.read_bytes(), xml)  # Sichtkomponente bleibt das Original (bei OCR das Bild-PDF)
    tmp_pdf, tmp_xml = pdf.parent / (pdf.name + ".out.pdf"), pdf.parent / (pdf.name + ".out.xml")
    try:
        tmp_xml.write_bytes(xml)
        tmp_pdf.write_bytes(zugferd)
        if not k.pruefe:
            raise ValueError("Mustang-Prüfung nicht verfügbar (java oder Mustang-CLI fehlt im Programmordner), "
                             "keine E-Rechnung abgelegt")
        # XML statt PDF: das PDF des Kunden ist kein PDF/A-3, Mustang meldet den PDF-Teil immer ungültig (Abweichung A2)
        log.info("%s: Mustang: %s", pdf.name, k.pruefe(tmp_xml))
        basis = _frei(k.ausgabe, re.sub(r"[^A-Za-z0-9._-]", "_", r.nummer), ".pdf", ".xml")
        if k.xml_einzeln:
            os.replace(tmp_xml, k.ausgabe / f"{basis}.xml")
        os.replace(tmp_pdf, k.ausgabe / f"{basis}.pdf")
    finally:
        tmp_xml.unlink(missing_ok=True)
        tmp_pdf.unlink(missing_ok=True)
    orig = _frei(k.originale, pdf.stem, ".pdf", ".ocr.txt")
    if r.ocr_text:
        vermerk = (f"{basis}: {OCR_HINWEIS} (Tesseract), das PDF enthielt keinen Text.\n"
                   "Beträge durch den Summenabgleich geprüft. Rechnungsnummer, Daten und Käufer gegen das PDF prüfen.\n\n"
                   f"--- erkannter Text ---\n{r.ocr_text}\n")
        with open(k.originale / f"{orig}.ocr.txt", "x", encoding="utf-8") as f:
            f.write(vermerk)
        log.info("%s: %s", pdf.name, vermerk)
    os.replace(pdf, k.originale / f"{orig}.pdf")
    log.info("%s → %s (Vorlage %s%s)", pdf.name, basis, r.vorlage, f", {OCR_HINWEIS}" if r.ocr_text else "")
    return k.ausgabe / f"{basis}.pdf"
def bearbeite(pdf: Path, k: Konfig) -> tuple[bool, str]:
    """Erfolg → (True, Pfad); jeder Fehler → Original + .fehler.txt nach Fehler, (False, Grund)."""
    try:
        return True, str(verarbeite(pdf, k))
    except Exception as e:
        grund = str(e) if isinstance(e, ValueError) else traceback.format_exc()
        log.warning("%s: %s", pdf.name, grund)
        basis = _frei(k.fehler, pdf.stem, ".pdf", ".fehler.txt")
        (k.fehler / f"{basis}.fehler.txt").write_text(f"{grund}\n", encoding="utf-8")
        os.replace(pdf, k.fehler / f"{basis}.pdf")
        return False, grund
def schritt(k: Konfig) -> int:
    for f in sorted(k.eingang.iterdir()):
        if f.is_file() and f.suffix.lower() == ".pdf":
            stempel = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            try:
                os.replace(f, k.arbeit / f"{stempel}-{f.name}")
            except (PermissionError, FileNotFoundError):
                continue  # Spooler schreibt noch (Freigabeverletzung) → nächster Takt
    n = 0
    for pdf in sorted(k.arbeit.iterdir()):
        if pdf.is_file() and pdf.suffix.lower() == ".pdf" and not pdf.name.endswith(".out.pdf"):
            bearbeite(pdf, k)
            n += 1
    return n
def ueberwache(k: Konfig, takt: float = 0.5) -> None:
    pruefe_ordner(k)
    for rest in list(k.arbeit.glob("*.out.*")):  # Reste eines abgebrochenen Laufs
        rest.unlink()
    for rest in list(k.arbeit.glob("ocr-*")):
        shutil.rmtree(rest, ignore_errors=True)
    log.info("Überwachung gestartet: %s (Texterkennung: %s, Mustang: %s, XML einzeln: %s)", k.eingang,
             k.ocr.keywords["aufruf"][0] if isinstance(k.ocr, partial) else "nicht verfügbar",
             " ".join(a for i, a in enumerate(k.pruefe.keywords["aufruf"]) if i == 0 or a.endswith(".jar"))
             if isinstance(k.pruefe, partial) else "NICHT VERFÜGBAR, jede Rechnung geht nach Fehler",
             "ja" if k.xml_einzeln else "nein")
    while True:
        try:
            schritt(k)
        except Exception:
            log.exception("Fehler im Überwachungsschritt")
        time.sleep(takt)
def umwandeln(pdf: Path, k: Konfig) -> tuple[bool, str]:
    pruefe_ordner(k)
    kopie = k.arbeit / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{pdf.name}"
    shutil.copyfile(pdf, kopie)
    return bearbeite(kopie, k)
