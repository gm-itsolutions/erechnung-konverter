"""Vergleichslogik des Messwerkzeugs mit kleinen synthetischen Eingaben."""
from datetime import date
from decimal import Decimal as D
from werkzeuge.korpus_messen import kennzahlen, vergleiche

SOLL = {"nummer": "R1", "datum": "2026-01-02", "netto": "100.00", "steuern": {"19.00": "19.00"}, "brutto": "119.00",
        "kaeufer": {"name": "Muster GmbH"}, "positionen": [{"netto": "60.00"}, {"netto": "40.00"}]}
GELESEN = dict(nummer="R1", datum=date(2026, 1, 2), netto=D("100"), brutto=D("119.0"), steuern={D("19"): D("19.00")},
               kaeufer="muster  gmbh", positionen=[D("40.00"), D("60")])


def test_alles_richtig_numerisch():
    assert all(v is True for v in vergleiche(SOLL, GELESEN).values())


def test_falsche_und_fehlende_felder():
    e = vergleiche(SOLL, {**GELESEN, "datum": date(2026, 1, 3), "steuern": {D("7"): D("19")}, "positionen": [D("100")]})
    assert (e["datum"], e["ust"], e["pos_anzahl"], e["pos_netto"], e["nummer"]) == (False, False, False, False, True)
    assert all(v is False for v in vergleiche(SOLL, None).values())


def test_nicht_bewertbar_wenn_soll_fehlt():
    e = vergleiche({"nummer": "R1", "datum": "2026-01-02", "netto": "1", "brutto": "1"}, GELESEN)
    assert (e["ust"], e["kaeufer"], e["pos_anzahl"], e["pos_netto"]) == (None, None, None, None)


def test_kennzahlen_bestaetigt_aber_falsch():
    ok = {"status": "ok", "bestaetigt": True, "felder": vergleiche(SOLL, GELESEN)}
    falsch = {"status": "ok", "bestaetigt": True, "felder": vergleiche(SOLL, {**GELESEN, "nummer": "X"})}
    skip = {"status": "uebersprungen", "bestaetigt": False, "felder": {}}
    k = kennzahlen([ok, falsch, skip])
    assert (k["gemessen"], k["uebersprungen"], k["vollstaendig_richtig"], k["bestaetigt"], k["bestaetigt_aber_falsch"]) == (2, 1, 1, 2, 1)
    assert k["felder"]["nummer"]["richtig"] == 1


def test_none_im_gelesenen_stuerzt_nicht_ab():
    from werkzeuge.korpus_messen import FELDER, _vergleiche
    erg = {"status": "ok", "bestaetigt": True, "felder": {}, "gelesen": {**GELESEN, "positionen": [None, D("1")]}}
    r = _vergleiche(erg, SOLL)
    assert r["status"] == "fehler" and not r["bestaetigt"] and r["felder"] == {f: False for f in FELDER}
    erg = {"status": "ok", "bestaetigt": False, "felder": {}, "gelesen": {**GELESEN, "datum": "02.01.2026"}}
    assert _vergleiche(erg, SOLL)["status"] == "fehler"


def test_gutschrift_vorzeichen_und_kern():
    from werkzeuge.korpus_messen import kennzahlen
    soll = {**SOLL, "netto": "-100.00", "brutto": "-119.00", "steuern": {"19": "-19.00"},
            "positionen": [{"netto": "-100.00"}]}
    neg = {**GELESEN, "netto": D("-100"), "brutto": D("-119"), "steuern": {D("19"): D("-19")}, "positionen": [D("-100")]}
    assert all(v is True for v in vergleiche(soll, neg).values())
    assert vergleiche(soll, {**neg, "netto": D("100")})["netto"] is False
    x = {"status": "ok", "bestaetigt": True, "felder": vergleiche(soll, {**neg, "netto": D("100")})}
    y = {"status": "ok", "bestaetigt": True, "felder": vergleiche(soll, {**neg, "kaeufer": "X"})}
    k = kennzahlen([x, y])
    assert (k["bestaetigt_aber_falsch"], k["bestaetigt_kern_falsch"]) == (2, 1)
