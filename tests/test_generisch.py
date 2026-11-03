"""Generische Erkennung: je Regel ein kleiner Text, dazu der Abgleich mit echten Lexware-Rechnungen."""
import os
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung.betraege import betraege
from erechnung.generisch import daten, erkenne, zahlen

KOPF = """Muster Software GmbH
Hauptstraße 1 · 10115 Berlin
Kunde Beispiel AG
Frau Erika Muster
Lindenweg 5
14467 Potsdam
Rechnungsnr.: RE-2026-17
Rechnungsdatum: 02.11.2026
"""
TABELLE = """Pos Bezeichnung Menge Einheit Einzelpreis Betrag
1 Wartung Server 2 Std 80,00 160,00
2 Lizenz Office 3 Stk 12,50 37,50
"""
SUMMEN = """Summe netto 197,50
MwSt. 19 % 37,53
Gesamtbetrag 235,03
"""


def test_datumsformate():
    assert [d for d, _, _ in daten("Datum: 02.11.2026")] == [date(2026, 11, 2)]
    assert [d for d, _, _ in daten("vom 04.11.26")] == [date(2026, 11, 4)]
    assert [d for d, _, _ in daten("Date: 2026-11-02")] == [date(2026, 11, 2)]
    assert [d for d, _, _ in daten("Berlin, 2. November 2026")] == [date(2026, 11, 2)]
    assert [d for d, _, _ in daten("Issued Nov 2, 2026")] == [date(2026, 11, 2)]
    assert [d for d, _, _ in daten("Date 03/11/2026")] == []        # TT/MM oder MM/TT: nicht raten
    assert [d for d, _, _ in daten("Date 23/11/2026")] == [date(2026, 11, 23)]


def test_betraege():
    assert [(z.wert, z.stellen) for z in zahlen("1.234,56 € und 1,234.56")] == [(D("1234.56"), 2), (D("1234.56"), 2)]
    assert [(z.wert, z.prozent) for z in zahlen("MwSt. 19 % -12,00")] == [(D(19), True), (D("-12.00"), False)]
    assert all(z.wert > 0 for z in zahlen("Artikel A-1051"))      # Bindestrich in der Artikelnummer ist kein Minus


def test_vollstaendige_rechnung_bestaetigt():
    v = erkenne(KOPF + TABELLE + SUMMEN)
    assert v.bestaetigt, v.grund
    assert (v.nummer, v.datum) == ("RE-2026-17", date(2026, 11, 2))
    assert (v.summe_netto, v.steuern, v.summe_ust, v.summe_brutto) == (D("197.50"), {D(19): D("37.53")}, D("37.53"), D("235.03"))
    assert [(p.menge, p.einzelpreis, p.netto) for p in v.positionen] == [(D(2), D("80.00"), D("160.00")),
                                                                         (D(3), D("12.50"), D("37.50"))]
    assert v.positionen[0].bezeichnung == "Wartung Server"
    assert v.kaeufer.name == "Kunde Beispiel AG" and v.kaeufer.plz == "14467"
    assert "RE-2026-17" in v.fundstellen["nummer"]


def test_steuerzeile_mit_basis_und_zwei_saetzen():
    tab = """Pos Bezeichnung Menge Einheit Einzelpreis MwSt % Betrag
1 Obstbaum 8 Stk 79,00 7 632,00
2 Heckenschnitt 2 Std 50,00 19 100,00
"""
    v = erkenne(KOPF + tab + "Summe netto 732,00\nMwSt. 7 % aus 632,00 44,24\nMwSt. 19 % aus 100,00 19,00\n"
                "Rechnungsbetrag 795,24\n")
    assert v.bestaetigt, v.grund
    assert v.steuern == {D(7): D("44.24"), D(19): D("19.00")}
    assert [p.ust_satz for p in v.positionen] == [D(7), D(19)]


def test_mehrzeilige_bezeichnung():
    tab = """Pos Bezeichnung Menge Einheit Einzelpreis Betrag
1 Wartung Server 2 Std 80,00 160,00
inkl. Updates und
Sicherungsprüfung
2 Lizenz Office 3 Stk 12,50 37,50
"""
    v = erkenne(KOPF + tab + SUMMEN)
    assert v.bestaetigt, v.grund
    assert v.positionen[0].bezeichnung == "Wartung Server inkl. Updates und Sicherungsprüfung"


def test_lieferanschrift_ist_nicht_kaeufer():
    text = """Muster Software GmbH
Hauptstraße 1 · 10115 Berlin
Lieferanschrift:
Lager Nord GmbH
Hafenweg 9
20457 Hamburg

Rechnungsempfänger:
Kunde Beispiel AG
Lindenweg 5
14467 Potsdam
Rechnungsnr.: RE-2026-17
Rechnungsdatum: 02.11.2026
"""
    v = erkenne(text + TABELLE + SUMMEN)
    assert v.kaeufer.name == "Kunde Beispiel AG"


def test_gutschrift_negativ_und_nicht_bestaetigt():
    text = KOPF.replace("Rechnungsnr.", "Gutschriftnr.") + """Pos Bezeichnung Menge Einheit Einzelpreis Betrag
1 Rückgabe Lizenz 1 Stk -50,00 -50,00
Summe netto -50,00
MwSt. 19 % -9,50
Gutschriftbetrag -59,50
"""
    v = erkenne(text)
    assert (v.summe_netto, v.summe_brutto) == (D("-50.00"), D("-59.50"))
    assert not v.bestaetigt and "negative" in v.grund


def test_unstimmige_summen_nicht_bestaetigt():
    v = erkenne(KOPF + TABELLE + SUMMEN.replace("235,03", "236,03"))
    assert not v.bestaetigt and v.grund


def test_unbeschriftete_nummer_braucht_zweite_fundstelle():
    kopf = KOPF.replace("Rechnungsnr.: RE-2026-17\n", "Rechnung RE-2026-17\n")
    v = erkenne(kopf + TABELLE + SUMMEN)
    assert v.nummer == "RE-2026-17" and not v.bestaetigt and "schwach" in v.grund
    v = erkenne(kopf + TABELLE + SUMMEN + "Muster Software GmbH · Rechnung RE-2026-17 vom 02.11.2026\n")
    assert v.bestaetigt, v.grund


def test_stueckpreiszeile_beendet_tabelle_nicht():
    tab = """Pos Bezeichnung Menge Einheit Einzelpreis Betrag
1 Wartung Server 2 Std 80,00 160,00
Bruttopreis: 95,2000
2 Lizenz Office 3 Stk 12,50 37,50
"""
    v = erkenne(KOPF + tab + SUMMEN)
    assert v.bestaetigt, v.grund
    assert len(v.positionen) == 2


DATEN = os.environ.get("ERECHNUNG_TESTDATEN")


@pytest.mark.echt
@pytest.mark.skipif(not DATEN, reason="ERECHNUNG_TESTDATEN nicht gesetzt")
@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149", "RE0158"])
def test_lexware_echt(nummer):
    v = erkenne((Path(DATEN) / f"{nummer}.txt").read_text(encoding="utf-8"))
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert v.bestaetigt, v.grund
    assert (v.nummer, v.summe_netto, v.summe_brutto) == (soll["nummer"], soll["netto"], soll["brutto"])
