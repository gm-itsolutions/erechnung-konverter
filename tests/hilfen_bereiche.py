"""Synthetische Rechnung „Beispiel Werkstatt“ für Bereichs-Vorlagen (tests/daten/bereiche-beispiel.yml)."""
from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from erechnung.bereiche import woerter_aus_pdf

W, H = A4
SPALTEN_X = (0.08, 0.14, 0.51, 0.62, 0.80)
MUSTER1 = [("1", "Inspektion nach Herstellervorgabe", "2 Std", "95,00", "190,00"),
           ("", "inkl. Probefahrt", "", "", ""),
           ("2", "Motoröl 5W-30", "4 Stk", "12,50", "50,00")]
SUMMEN1 = ("240,00", "45,60", "285,60")


def seiten_aus(tmp_path: Path, pdf: bytes):
    """Wörter je Seite aus PDF-Bytes."""
    p = tmp_path / "m.pdf"
    p.write_bytes(pdf)
    return woerter_aus_pdf(p)


def werkstatt_pdf(zeilen, summen, dx=0.0, dy=0.0, umbruch_nach=None, uebertrag="", kopf_wiederholen=True,
                  nummer="BW-2026-17") -> bytes:
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    c.setFont("Helvetica", 10)

    def t(x, y, s):
        c.drawString((x + dx) * W, H * (1 - (y + dy)) - 8, s)

    def kopf(y):
        for x, s in zip(SPALTEN_X, ("Nr", "Leistung", "Anzahl", "Preis", "Betrag")):
            t(x, y, s)

    t(0.08, 0.08, "Beispiel Werkstatt · Feldweg 2 · 16928 Pritzwalk")
    for i, s in enumerate(("Muster Kunde GmbH", "Am Markt 3", "19348 Perleberg")):
        t(0.08, 0.150 + 0.02 * i, s)
    for i, (l, w) in enumerate((("Belegnummer", nummer), ("Belegdatum", "05.11.2026"), ("Zahlbar in", "14 Tage"))):
        t(0.50, 0.150 + 0.02 * i, l)
        t(0.70, 0.150 + 0.02 * i, w)
    kopf(0.250)
    y = 0.275
    for i, z in enumerate(zeilen):
        if i == umbruch_nach:
            t(0.50, y, "Übertrag")
            t(0.80, y, uebertrag)
            t(0.08, 0.95, "Seite 1/2")
            c.showPage()
            c.setFont("Helvetica", 10)
            t(0.08, 0.08, "Beispiel Werkstatt · Feldweg 2 · 16928 Pritzwalk")
            t(0.50, 0.10, "Belegnummer")
            t(0.70, 0.10, nummer)
            y = 0.15
            if kopf_wiederholen:
                kopf(y)
                y += 0.025
            t(0.50, y, "Übertrag")
            t(0.80, y, uebertrag)
            y += 0.02
        for x, s in zip(SPALTEN_X, z):
            if s:
                t(x, y, s)
        y += 0.02
    y += 0.01
    for l, w in zip(("Summe netto", "MwSt. 19 %", "Endbetrag"), summen):
        t(0.50, y, l)
        t(0.80, y, w)
        y += 0.02
    c.save()
    return puffer.getvalue()
