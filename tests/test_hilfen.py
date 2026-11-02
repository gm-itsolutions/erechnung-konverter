from decimal import Decimal as D
from erechnung.modell import summenabgleich
from hilfen import beispiel_rechnung, pdf_aus_text

def test_beispiel_rechnung_summen():
    assert summenabgleich(beispiel_rechnung()) == {D("19"): (D("200.00"), D("38.00"))}

def test_pdf_aus_text():
    assert pdf_aus_text(["Zeile"] * 80).startswith(b"%PDF")
