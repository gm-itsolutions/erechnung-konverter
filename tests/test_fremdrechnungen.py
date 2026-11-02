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


@pytest.mark.parametrize("layout", ["E", "B"])   # E: Rabatt und Dezimalmenge, B: zwei Steuersätze
def test_soll_summen_und_abweisung(tmp_path, layout):
    pdfs = fr.erzeuge(tmp_path, [layout], bild=False)
    assert len(pdfs) == fr.ANZAHL
    vorlagen = lade_vorlagen(STANDARD)
    for pdf in pdfs:
        s = json.loads(pdf.with_suffix(".soll.json").read_text(encoding="utf-8"))
        basis = defaultdict(D)
        for p in s["positionen"]:
            assert D(p["netto"]) == _r(D(p["menge"]) * D(p["einzelpreis"]))
            basis[D(p["satz"])] += D(p["netto"])
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
        with pytest.raises(VorlagenFehler, match="keine Vorlage passt"):
            lies_rechnung(pdf, vorlagen, VERKAEUFER)
    if layout == "E":
        assert any(D(p["menge"]) % 1 for p in s["positionen"])
    else:
        assert len(s["steuern"]) == 2


def test_deterministisch(tmp_path):
    a, b = fr.erzeuge(tmp_path / "a", ["G"], bild=False), fr.erzeuge(tmp_path / "b", ["G"], bild=False)
    assert [p.read_bytes() for p in a] == [p.read_bytes() for p in b]
