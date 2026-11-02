from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung.vorlagen import VorlagenFehler, finde_vorlage, lade_vorlagen, lies_rechnung, rechnung_aus_text
from erechnung.modell import summenabgleich
from hilfen import VERKAEUFER, pdf_aus_text
VORLAGE = """
name: test-layout
schluesselwoerter: ["Testfirma", "Rechnung Nr."]
felder:
  nummer: 'Rechnung Nr\\.\\s*(\\S+)'
  datum: 'Datum:\\s*(\\d{2}\\.\\d{2}\\.\\d{4})'
  faellig: 'zahlbar bis\\s*(\\d{2}\\.\\d{2}\\.\\d{4})'
  summe_netto: '^Netto\\s+([\\d.,]+)'
  summe_brutto: '^Brutto\\s+([\\d.,]+)'
steuern: '^USt (?P<satz>\\d+) %\\s+(?P<betrag>[\\d.,]+)'
kaeufer: 'An:\\n(?P<name>.+)\\n(?P<strasse>.+)\\n(?P<plz>\\d{5}) (?P<ort>.+)'
positionen:
  start: '^Pos Text'
  ende: '^Netto'
  zeile: '^(?P<nr>\\d+) (?P<bezeichnung>.+?) (?P<menge>[\\d,]+) (?P<einheit>Std|Stk) (?P<einzelpreis>[\\d.,]+) (?P<netto>[\\d.,]+)$'
  ust_satz: 19
  ignorieren: ['^Seite \\d+']
einheiten: {Std: HUR, Stk: H87}
"""
TEXT = """Testfirma · Weg 1 · 16928 Pritzwalk
An:
Beispiel Handel GmbH
Hauptstraße 5
19348 Perleberg
Rechnung Nr. RE9001
Datum: 15.10.2026
Pos Text Menge Einheit Preis Gesamt
1 IT-Service 2,00 Std 95,00 190,00
Server geprüft
Seite 1
2 Kabel 2 Stk 5,00 10,00
Netto 200,00
USt 19 % 38,00
Brutto 238,00
zahlbar bis 29.10.2026"""
@pytest.fixture
def vorlagen(tmp_path):
    (tmp_path / "test.yml").write_text(VORLAGE, encoding="utf-8")
    return lade_vorlagen(tmp_path, tmp_path / "gibt-es-nicht")
def test_finde_und_lies(vorlagen):
    v = finde_vorlage(TEXT, vorlagen)
    r = rechnung_aus_text(TEXT, v, VERKAEUFER)
    assert (r.nummer, str(r.datum), str(r.faellig), r.vorlage) == ("RE9001", "2026-10-15", "2026-10-29", "test-layout")
    assert r.kaeufer.name == "Beispiel Handel GmbH" and r.kaeufer.plz == "19348" and r.kaeufer.ort == "Perleberg"
    assert [p.bezeichnung for p in r.positionen] == ["IT-Service Server geprüft", "Kabel"]
    assert [p.einheit for p in r.positionen] == ["HUR", "H87"]
    assert r.steuern == {D("19"): D("38.00")}
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
def test_keine_vorlage(vorlagen):
    with pytest.raises(VorlagenFehler, match="keine Vorlage"):
        finde_vorlage("Andere Firma", vorlagen)
def test_mehrere_vorlagen(tmp_path):
    for n in ("a", "b"):
        (tmp_path / f"{n}.yml").write_text(VORLAGE.replace("test-layout", n), encoding="utf-8")
    with pytest.raises(VorlagenFehler, match="mehrere Vorlagen: a, b"):
        finde_vorlage(TEXT, lade_vorlagen(tmp_path))
def test_pflichtfeld_fehlt(vorlagen):
    with pytest.raises(VorlagenFehler, match="summe_brutto"):
        rechnung_aus_text(TEXT.replace("Brutto", "Gesamt"), vorlagen[0], VERKAEUFER)
def test_kaputte_vorlage(tmp_path):
    (tmp_path / "x.yml").write_text(VORLAGE.replace("'^Pos Text'", "'(['"), encoding="utf-8")
    with pytest.raises(VorlagenFehler, match="x.yml"):
        lade_vorlagen(tmp_path)
def test_pdf_ohne_text(tmp_path, vorlagen):
    leer = tmp_path / "leer.pdf"
    leer.write_bytes(pdf_aus_text([]))
    with pytest.raises(VorlagenFehler, match="kein Text"):
        lies_rechnung(leer, vorlagen, VERKAEUFER)
def test_pdf_durchlauf(tmp_path, vorlagen):
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    assert lies_rechnung(pdf, vorlagen, VERKAEUFER).summe_brutto == D("238.00")
def test_lexware_synthetisch():
    from erechnung.vorlagen import STANDARD
    text = (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
    vorlagen = lade_vorlagen(STANDARD)
    r = rechnung_aus_text(text, finde_vorlage(text, vorlagen), VERKAEUFER)
    assert r.nummer == "RE9146" and r.summe_brutto == D("238.00")
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
    assert (str(r.datum), str(r.leistungsdatum), r.faellig) == ("2026-10-15", "2026-10-14", None)
    assert (r.kaeufer.name, r.kaeufer.strasse, r.kaeufer.plz, r.kaeufer.ort) == ("Beispiel Handel GmbH", "Hauptstraße 5", "19348", "Perleberg")
    assert [p.bezeichnung for p in r.positionen] == [
        "Arbeitsstunde • Wartung Server - 2 • Prüfung Datensicherung", "Patchkabel Cat. 6 - 1 m Farbe grau"]
    assert [(p.menge, p.einheit) for p in r.positionen] == [(D("2"), "HUR"), (D("2"), "H87")]
