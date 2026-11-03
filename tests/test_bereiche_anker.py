from pathlib import Path

import pytest
import yaml

from erechnung.bereiche import BereichsFehler, Wort, feld_text, finde_anker, treffer, zeilen
from hilfen_bereiche import MUSTER1, SUMMEN1, seiten_aus, werkstatt_pdf

V = yaml.safe_load((Path(__file__).parent / "daten" / "bereiche-beispiel.yml").read_text(encoding="utf-8"))


def test_woerter_relativ(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    w = next(w for w in s[0] if w.text == "Belegnummer")
    assert abs(w.x0 - 0.50) < 0.002 and abs(w.top - 0.150) < 0.003 and 0 < w.bottom - w.top < 0.02


def test_zeilen_gruppiert():
    z = zeilen([Wort("b", 0.3, 0.101, 0.4, 0.111), Wort("a", 0.1, 0.100, 0.2, 0.110), Wort("c", 0.1, 0.2, 0.2, 0.21)])
    assert [[w.text for w in l] for l in z] == [["a", "b"], ["c"]]


def test_anker_verschoben(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=0.02, dy=0.03))
    i, dx, dy = finde_anker(s, V["felder"]["nummer"]["anker"], "erste")
    assert i == 0 and abs(dx - 0.02) < 0.003 and abs(dy - 0.03) < 0.003


def test_anker_fehlt(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    assert finde_anker(s, {"text": "Gibt es nicht", "rahmen": [0, 0, 0.1, 0.1]}, "erste") is None


def test_treffer_satz(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    assert [t[3] for t in treffer(s[0], "MwSt. {satz} %")] == ["19"]


def test_feld_text_mit_anker_und_spur(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=0.02, dy=0.03))
    spur = {}
    assert feld_text(s, V, "nummer", spur=spur) == (0, ["BW-2026-17"])
    assert spur["nummer"]["seite"] == 0 and abs(spur["nummer"]["rahmen"][0] - 0.70) < 0.004


def test_feld_text_ohne_anker_folgt_versatz(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=0.02, dy=0.03))
    assert feld_text(s, V, "kaeufer")[1] == ["Muster Kunde GmbH", "Am Markt 3", "19348 Perleberg"]


def test_feld_text_pflicht_anker_fehlt(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    v = {**V, "felder": {**V["felder"], "nummer": {**V["felder"]["nummer"], "anker": {"text": "Gibt es nicht", "rahmen": [0.5, 0.15, 0.6, 0.16]}}}}
    with pytest.raises(BereichsFehler, match="Anker „Gibt es nicht“ nicht gefunden"):
        feld_text(s, v, "nummer")


def test_feld_text_entwurf_ohne_nummer(tmp_path):
    s = seiten_aus(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    v = {**V, "felder": {"kaeufer": V["felder"]["kaeufer"]}}
    assert feld_text(s, v, "kaeufer")[1][0] == "Muster Kunde GmbH"
    assert feld_text(s, v, "datum") is None
