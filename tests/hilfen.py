"""Gemeinsame Testhilfen: Beispielrechnung und PDF aus Textzeilen (reportlab, nur Test)."""
from datetime import date
from decimal import Decimal as D
from io import BytesIO
from erechnung.modell import Partei, Position, Rechnung

VERKAEUFER = Partei("GM IT Solutions", "Musterstraße 1", "16928", "Pritzwalk", "DE",
                    ust_id="DE123456789", email="rechnung@example.org",
                    iban="DE02120300000000202051", bic="BYLADEM1001")

def beispiel_rechnung() -> Rechnung:
    return Rechnung(
        nummer="RE9001", datum=date(2026, 10, 15), leistungsdatum=date(2026, 10, 14), faellig=date(2026, 10, 29),
        verkaeufer=VERKAEUFER, kaeufer=Partei("Beispiel Handel GmbH", "Hauptstraße 5", "19348", "Perleberg"),
        positionen=[Position("1", "IT-Service vor Ort", D("2"), "HUR", D("95.00"), D("190.00"), D("19")),
                    Position("2", "Anfahrt", D("1"), "C62", D("10.00"), D("10.00"), D("19"))],
        summe_netto=D("200.00"), summe_ust=D("38.00"), summe_brutto=D("238.00"), steuern={D("19"): D("38.00")})

def pdf_aus_text(zeilen: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    puffer = BytesIO()
    c = canvas.Canvas(puffer, pagesize=A4)
    y = 800
    for z in zeilen:
        if y < 50:
            c.showPage()
            y = 800
        c.drawString(50, y, z)
        y -= 14
    c.save()
    return puffer.getvalue()

def bild_pdf(pdf: bytes, dpi: int = 300) -> bytes:
    """PDF ohne Text: jede Seite als Bild (wie ein Druck aus Edge auf Microsoft Print to PDF)."""
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(pdf)
    bilder = [s.render(scale=dpi / 72, grayscale=True).to_pil() for s in d]
    d.close()
    puffer = BytesIO()
    bilder[0].save(puffer, format="PDF", save_all=True, append_images=bilder[1:], resolution=dpi)
    return puffer.getvalue()
