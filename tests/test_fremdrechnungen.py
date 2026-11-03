"""Generator für Test-Rechnungen in fremden Layouts: Summenlogik in soll.json und Gegenprobe ohne Texterkennung."""
import json
from collections import defaultdict
from decimal import Decimal as D, ROUND_HALF_UP
import pytest
from erechnung.vorlagen import STANDARD, VorlagenFehler, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER
from werkzeuge import fremdrechnungen as fr


def _r(x: D) -> D:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


@pytest.mark.parametrize("layout", ["E", "B", *"HIJKLMNO"])   # E: Rabatt und Dezimalmenge, B: zwei Steuersätze
def test_soll_summen_und_abweisung(tmp_path, layout):
    pdfs = fr.erzeuge(tmp_path, [layout], bild=False)
    assert len(pdfs) == fr.ANZAHL
    vorlagen = lade_vorlagen(STANDARD)
    for pdf in pdfs:
        s = json.loads(pdf.with_suffix(".soll.json").read_text(encoding="utf-8"))
        with pytest.raises(VorlagenFehler, match="keine Vorlage passt"):
            lies_rechnung(pdf, vorlagen, VERKAEUFER)
        basis = defaultdict(D)
        for p in s["positionen"]:
            rab = D(p.get("rabatt_prozent", "0"))
            assert D(p["netto"]) == _r(D(p["menge"]) * D(p["einzelpreis"]) * (100 - rab) / 100)
            basis[D(p["satz"])] += D(p["netto"])
        if s["brutto_positionen"]:   # Positionen sind brutto: Steuer wird herausgerechnet
            steuer = {k: _r(b * k / (100 + k)) for k, b in basis.items()}
            assert {D(k): D(v) for k, v in s["steuern"].items()} == steuer
            assert D(s["brutto"]) == sum(basis.values(), D(0)) == D(s["netto"]) + sum(steuer.values(), D(0))
            continue
        zwischen = sum(basis.values(), D(0))
        assert D(s["zwischensumme"]) == zwischen
        rabatt = D(s["rabatt"]["betrag"]) if s["rabatt"] else D(0)
        if rabatt:
            assert rabatt == _r(zwischen * D(s["rabatt"]["prozent"]) / 100)
            (satz,) = basis
            basis[satz] -= rabatt
        assert D(s["netto"]) == zwischen - rabatt
        assert {D(k): D(v) for k, v in s["steuern"].items()} == {k: _r(b * k / 100) for k, b in basis.items()}
        assert D(s["brutto"]) == D(s["netto"]) + sum(D(v) for v in s["steuern"].values())
    if layout == "E":
        assert any(D(p["menge"]) % 1 for p in s["positionen"])
    elif layout == "B":
        assert len(s["steuern"]) == 2
    elif layout == "L":
        assert s["art"] == "gutschrift" and D(s["brutto"]) < 0
    elif layout == "N":
        assert s["seiten"] >= 2


@pytest.mark.parametrize("layout", ["G", "H", "N"])
def test_deterministisch(tmp_path, layout):
    a = fr.erzeuge(tmp_path / "a", [layout], bild=False, varianten=2)
    b = fr.erzeuge(tmp_path / "b", [layout], bild=False, varianten=2)
    assert len(a) == fr.ANZAHL + 2
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]


def test_varianten_lassen_erste_exemplare_unveraendert(tmp_path):
    a = fr.erzeuge(tmp_path / "a", ["M"], bild=False)
    b = fr.erzeuge(tmp_path / "b", ["M"], bild=False, varianten=3)
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b[:fr.ANZAHL]]
