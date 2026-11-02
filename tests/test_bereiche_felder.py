from datetime import date
from decimal import Decimal as D
from pathlib import Path
import pytest, yaml
from erechnung.bereiche import BereichsFehler, _betrag, feld_text, kopf_aus_bereichen
from hilfen_bereiche import MUSTER1, SUMMEN1, seiten_aus, werkstatt_pdf
V = yaml.safe_load((Path(__file__).parent / "daten" / "bereiche-beispiel.yml").read_text(encoding="utf-8"))
@pytest.mark.parametrize("dx, dy", [(0, 0), (0.02, 0.03), (-0.01, -0.02)])
def test_kopf_werte(tmp_path, dx, dy):
    k = kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=dx, dy=dy)), V)
    assert k["nummer"] == "BW-2026-17" and k["datum"] == date(2026, 11, 5) and k["faellig"] == date(2026, 11, 19)
    assert (k["kaeufer"].name, k["kaeufer"].strasse, k["kaeufer"].plz, k["kaeufer"].ort) == \
        ("Muster Kunde GmbH", "Am Markt 3", "19348", "Perleberg")
    assert (k["summe_netto"], k["summe_brutto"], k["steuern"]) == (D("240.00"), D("285.60"), {D("19"): D("45.60")})
def test_summen_wandern_mit_positionen(tmp_path):
    mehr = MUSTER1 + [("3", "Filter", "1 Stk", "10,00", "10,00"), ("4", "Kleinteile", "1 Stk", "5,00", "5,00")]
    k = kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(mehr, ("255,00", "48,45", "303,45"))), V)
    assert (k["summe_netto"], k["summe_brutto"]) == (D("255.00"), D("303.45"))
def test_spur(tmp_path):
    spur = {}
    kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V, spur=spur)
    assert spur["nummer"]["seite"] == 0 and len(spur["summe_netto"]["rahmen"]) == 4
    assert len(spur["steuern1"]["rahmen"]) == 4
def test_pflichtanker_fehlt(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["felder"]["summe_brutto"]["anker"]["text"] = "Gesamtsumme"
    with pytest.raises(BereichsFehler, match="Anker „Gesamtsumme“ nicht gefunden"):
        kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
def test_nummer_unzulaessig(tmp_path):
    with pytest.raises(BereichsFehler, match="Rechnungsnummer"):
        kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, nummer="BW#17")), V)
def test_nummer_kontrolle(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["felder"]["nummer_kontrolle"] = {"seite": "erste", "rahmen": [0.68, 0.168, 0.95, 0.186],
                                       "anker": {"text": "Belegdatum", "rahmen": [0.50, 0.170, 0.59, 0.182]}}
    with pytest.raises(BereichsFehler, match="uneinheitlich"):
        kopf_aus_bereichen(seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
def test_leere_seitenliste():
    with pytest.raises(BereichsFehler, match="ohne Seiten"):
        kopf_aus_bereichen([], V)
    with pytest.raises(BereichsFehler, match="ohne Seiten"):
        feld_text([], V, "nummer")
def test_betrag_ohne_zahl():
    with pytest.raises(ValueError):
        _betrag("n/a")
