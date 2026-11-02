from datetime import date
from decimal import Decimal as D
import pytest
from erechnung.modell import Partei, Position, Rechnung, SummenFehler, betrag, datum, runde, summenabgleich
def pos(nr, menge, preis, netto, satz="19"):
    return Position(str(nr), f"Leistung {nr}", D(menge), "HUR", D(preis), D(netto), D(satz))
def rechnung(positionen, netto, ust, brutto, steuern=None):
    return Rechnung(nummer="RE0001", datum=date(2026, 10, 15),
                    verkaeufer=Partei("GM IT Solutions"), kaeufer=Partei("Muster GmbH"),
                    positionen=positionen, summe_netto=D(netto), summe_brutto=D(brutto),
                    summe_ust=None if ust is None else D(ust), steuern=steuern or {})
@pytest.mark.parametrize("text,erwartet", [
    ("1.234,56", "1234.56"), ("1.234,56 €", "1234.56"), ("€ 12,00", "12.00"), ("-12,50", "-12.50"),
    ("0,5", "0.5"), ("1234", "1234"), ("1 234,00", "1234.00"), ("1 234,00", "1234.00"),
])
def test_betrag(text, erwartet):
    assert betrag(text) == D(erwartet)
@pytest.mark.parametrize("text", ["abc", "", "NaN", "Infinity"])
def test_betrag_unsinn(text):
    with pytest.raises(ValueError):
        betrag(text)
def test_datum():
    assert datum("05.11.2026") == date(2026, 11, 5)
def test_runde_kaufmaennisch():
    assert runde(D("0.125")) == D("0.13")
    assert runde(D("2.675")) == D("2.68")
def test_abgleich_ok_ein_satz():
    r = rechnung([pos(1, "2", "95.00", "190.00"), pos(2, "1", "10.00", "10.00")],
                 "200.00", "38.00", "238.00", {D("19"): D("38.00")})
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
def test_abgleich_gemischte_saetze():
    r = rechnung([pos(1, "1", "100.00", "100.00"), pos(2, "1", "50.00", "50.00", "7")],
                 "150.00", "22.50", "172.50")
    assert summenabgleich(r) == {D("19"): (D("100.00"), D("19.00")), D("7"): (D("50.00"), D("3.50"))}
def test_abgleich_gedruckte_steuer_mit_cent_toleranz():
    r = rechnung([pos(1, "1", "10.05", "10.05")], "10.05", "1.92", "11.97", {D("19"): D("1.92")})
    assert summenabgleich(r) == {D("19"): (D("10.05"), D("1.92"))}  # berechnet 1.91, gedruckt gilt
@pytest.mark.parametrize("positionen,netto,ust,brutto,steuern,teil", [
    ([], "0", "0", "0", None, "keine Positionen"),
    ([pos(1, "2", "10.00", "25.00")], "25.00", "4.75", "29.75", None, "Position 1"),
    ([pos(1, "1", "100.00", "100.00")], "110.00", "20.90", "130.90", None, "Netto"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "19.00", "120.00", None, "Brutto"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "18.00", "118.00", None, "Umsatzsteuer"),
    ([pos(1, "1", "100.00", "100.00")], "100.00", "19.00", "119.00", {D("19"): D("17.00")}, "19 %"),
    ([pos(1, "1", "100.00", "100.00", "0")], "100.00", "0.00", "100.00", None, "0 %"),
])
def test_abgleich_fehler(positionen, netto, ust, brutto, steuern, teil):
    with pytest.raises(SummenFehler, match=teil):
        summenabgleich(rechnung(positionen, netto, ust, brutto, steuern))
