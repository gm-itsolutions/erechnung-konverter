"""Holt Lexware-Rechnungen (PDF + E-Rechnungs-XML) nach /root/erechnung-testdaten. Nur gm-claude.
Aufruf: /root/.venvs/erechnung/bin/python werkzeuge/testdaten_holen.py RE0146 RE0148 RE0149"""
import json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ZIEL = Path("/root/erechnung-testdaten")
BASIS = "https://api.lexware.io/v1"

def schluessel() -> str:
    for z in Path("/root/.config/gm-it-os/lexware.env").read_text().splitlines():
        name, _, wert = z.partition("=")
        if name.strip().endswith("KEY") and wert.strip():
            return wert.strip().strip('"')
    sys.exit("kein API-Key in lexware.env")

def hole(pfad: str, accept: str = "application/json") -> bytes:
    time.sleep(0.6)  # 2 Requests/s
    req = urllib.request.Request(BASIS + pfad, headers={"Authorization": f"Bearer {KEY}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def finde_id(nummer: str) -> str:
    seite = 0
    while True:
        d = json.loads(hole(f"/voucherlist?voucherType=invoice&voucherStatus=any&size=250&page={seite}"))
        for v in d["content"]:
            if v.get("voucherNumber") == nummer:
                return v["id"]
        if d.get("last", True):
            sys.exit(f"{nummer} nicht gefunden")
        seite += 1

def pdf_und_xml(rid: str) -> tuple[bytes, bytes | None]:
    try:
        pdf = hole(f"/invoices/{rid}/file", "application/pdf")
    except urllib.error.HTTPError:
        doc = json.loads(hole(f"/invoices/{rid}/document"))
        pdf = hole(f"/files/{doc['documentFileId']}", "application/pdf")
    try:
        return pdf, hole(f"/invoices/{rid}/file", "application/xml")
    except urllib.error.HTTPError:
        from facturx import get_xml_from_pdf  # Lexware-PDF mit eingebetteter XML?
        _, xml = get_xml_from_pdf(pdf, check_xsd=False)
        return pdf, xml or None

if __name__ == "__main__":
    KEY = schluessel()
    ZIEL.mkdir(mode=0o700, exist_ok=True)
    os.chmod(ZIEL, 0o700)
    import pdfplumber
    for nummer in sys.argv[1:]:
        pdf, xml = pdf_und_xml(finde_id(nummer))
        (ZIEL / f"{nummer}.pdf").write_bytes(pdf)
        if xml:
            (ZIEL / f"{nummer}.lexware.xml").write_bytes(xml)
        with pdfplumber.open(ZIEL / f"{nummer}.pdf") as d:
            (ZIEL / f"{nummer}.txt").write_text("\n".join(s.extract_text() or "" for s in d.pages))
            (ZIEL / f"{nummer}.layout.txt").write_text("\n".join(s.extract_text(layout=True) or "" for s in d.pages))
        print(nummer, "PDF", len(pdf), "XML", len(xml or b""))
