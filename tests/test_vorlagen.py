from decimal import Decimal as D
from pathlib import Path
import pytest
from erechnung.vorlagen import VorlagenFehler, _anfuegen, finde_vorlage, lade_vorlagen, lies_rechnung, rechnung_aus_text
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
    assert (str(r.datum), str(r.leistungsdatum), str(r.faellig)) == ("2026-10-15", "2026-10-14", "2026-10-22")
    assert (r.kaeufer.name, r.kaeufer.strasse, r.kaeufer.plz, r.kaeufer.ort) == ("Beispiel Handel GmbH", "Hauptstraße 5", "19348", "Perleberg")
    assert [p.bezeichnung for p in r.positionen] == [
        "Arbeitsstunde • Wartung Server - 2 • Prüfung Datensicherung", "Patchkabel Cat. 6 - 1 m Farbe grau"]
    assert [(p.menge, p.einheit) for p in r.positionen] == [(D("2"), "HUR"), (D("2"), "H87")]
@pytest.mark.parametrize("text,zeile,soll", [
    ("Wartung Dokumentenscan-", "ner: Reinigung", "Wartung Dokumentenscanner: Reinigung"),
    ("Tausch der Einzugs-", "rollen", "Tausch der Einzugsrollen"),
    ("Wartungskit (Einzugs-", "und Trennrolle)", "Wartungskit (Einzugs- und Trennrolle)"),
    ("Abholung oder Bring-", "oder Holservice", "Abholung oder Bring- oder Holservice"),
    ("neues E-Mail-", "Postfach", "neues E-Mail-Postfach"),
    ("Drucker (ABC-", "PRT-003)", "Drucker (ABC-PRT-003)"),
    ("Wartung Server -", "2", "Wartung Server - 2"),
    ("Arbeitsstunde", "• Prüfung", "Arbeitsstunde • Prüfung"),
])
def test_silbentrennung(text, zeile, soll):
    assert _anfuegen(text, zeile) == soll
def test_lexware_zusatzzeile_stoert_nicht():
    from erechnung.vorlagen import STANDARD
    text = (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
    text = text.replace("Datum: 15.10.2026\n", "Datum: 15.10.2026\nAbteilung Einkauf\n")
    r = rechnung_aus_text(text, finde_vorlage(text, lade_vorlagen(STANDARD)), VERKAEUFER)
    assert (r.kaeufer.name, r.kaeufer.strasse, r.kaeufer.plz) == ("Beispiel Handel GmbH", "Hauptstraße 5", "19348")
def _ocr_lexware():
    """Lexware-Text mit typischen Abweichungen der Texterkennung (beobachtet an Bild-PDFs der echten Rechnungen)."""
    from erechnung.ocr import bereinige
    text = (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
    for alt, neu in [
        ("Pos. Bezeichnung Menge Einheit Einzel € USt. % Gesamt €", "[00 [Bassiehnung __—__] Menge | Eine | emeete [Ust % | 0osame"),
        ("1 Arbeitsstunde 2 Stunde 95,00 19,00 190,00", "A Arbeitsstunde 2 | Stunde 95,00 | 19,00 190,00"),  # Pos.-Nr. verlesen
        ("2 Patchkabel Cat. 6 - 1 m 2 Stück 5,00 19,00 10,00", "2 Patchkabel Cat. 6 - 1 m 2 Stück 5.00 19.00 10.00 €"),
        ("Zwischensumme 190,00", "[aischensumme | vum"),
        ("Datum: 15.10.2026", "Datum: 15.1O.2026"),
        ("Zwischensumme (netto) 200,00", "Zwischensumme(netto) 200,00 EUR"),
        ("Umsatzsteuer 19 % 38,00", "Umsatzsteuer 19% 38.00"),
        ("Gesamtbetrag 238,00", "Gesamtbetrag 2 38,00 €"),
        ("GM - IT Solutions - Marvin Gawenda\n", "GM - IT Solutions -  Marvin Gawenda\n"),
    ]:
        assert alt in text, alt
        text = text.replace(alt, neu, 1)
    return bereinige(text)
def test_lexware_ocr_tolerant():
    from erechnung.vorlagen import STANDARD
    text = _ocr_lexware()
    r = rechnung_aus_text(text, finde_vorlage(text, lade_vorlagen(STANDARD)), VERKAEUFER)
    assert (r.nummer, str(r.datum)) == ("RE9146", "2026-10-15")
    assert summenabgleich(r) == {D("19"): (D("200.00"), D("38.00"))}
    assert [(p.nr, p.netto) for p in r.positionen] == [("1", D("190.00")), ("2", D("10.00"))]
    assert r.positionen[0].bezeichnung == "Arbeitsstunde • Wartung Server - 2 • Prüfung Datensicherung"
    assert r.positionen[1].bezeichnung == "Patchkabel Cat. 6 - 1 m Farbe grau"   # Kopfzeile Seite 2 nicht angehängt
def test_lexware_nummer_uneinheitlich():
    from erechnung.vorlagen import STANDARD
    vorlagen = lade_vorlagen(STANDARD)
    text = _ocr_lexware().replace("Rechnung RE9146", "Rechnung RE9148")      # Überschrift verlesen
    with pytest.raises(VorlagenFehler, match="Rechnungsnummer uneinheitlich"):
        rechnung_aus_text(text, finde_vorlage(text, vorlagen), VERKAEUFER)
    text = _ocr_lexware().replace("Rechnungsnr.: RE9146", "Rechnungsnr.: REO9146")   # zusätzliches O: bleibt Fehler
    with pytest.raises(VorlagenFehler, match="Rechnungsnummer uneinheitlich"):
        rechnung_aus_text(text, finde_vorlage(text, vorlagen), VERKAEUFER)
    text = _ocr_lexware().replace("Rechnung RE9146", "Rechnung RE 9146")             # Überschrift unsauber: Fehler
    with pytest.raises(VorlagenFehler, match="Feld nummer"):
        rechnung_aus_text(text, finde_vorlage(text, vorlagen), VERKAEUFER)


@pytest.mark.parametrize("gelesen", ["REO0146", "REO01 46", "RE01 46", "REO146", "RE0146"])
def test_lexware_nummer_ocr_gegenprobe(gelesen):
    """Echter Edge-Druck (VM 108): Überschrift sauber, „Rechnungsnr.:“ mit O/O0 statt 0, Leerzeichen,
    und vom Adressblock daneben eingeleitet. Nummer kommt aus der Überschrift, Gegenprobe normalisiert."""
    from erechnung.vorlagen import STANDARD
    text = _ocr_lexware().replace("RE9146", "RE0146")
    text = text.replace("Rechnungsnr.: RE0146", f"Pritzwalk OT Beispielort Musterstraße Rechnungsnr.: {gelesen}")
    r = rechnung_aus_text(text, finde_vorlage(text, lade_vorlagen(STANDARD)), VERKAEUFER)
    assert r.nummer == "RE0146"


def _lexware_rabatt(ocr=False):
    """Lexware-Rabatt wie RE0158: Zwischensumme (netto), abzgl. Rabatt, Gesamt (netto) (erfundene Beträge)."""
    text = _ocr_lexware() if ocr else (Path(__file__).parent / "daten" / "lexware-synthetisch.txt").read_text(encoding="utf-8")
    alt = ("Zwischensumme(netto) 200,00 EUR\nUmsatzsteuer 19% 38.00\nGesamtbetrag 2 38,00 €" if ocr else
           "Zwischensumme (netto) 200,00\nUmsatzsteuer 19 % 38,00\nGesamtbetrag 238,00")
    neu = ("Zwischensumme(netto) 200,00 EUR\nabzgl. Rabatt — 20.00 €\nGesamt(netto) 1 80,00 EUR\nUmsatzsteuer 19% 34.20\nGesamtbetrag 214,20 €" if ocr else
           "Zwischensumme (netto) 200,00\nabzgl. Rabatt -20,00\nGesamt (netto) 180,00\nUmsatzsteuer 19 % 34,20\nGesamtbetrag 214,20")
    assert alt in text
    return text.replace(alt, neu)


@pytest.mark.parametrize("ocr", [False, True])
def test_lexware_rabatt(ocr):
    from erechnung.vorlagen import STANDARD
    text = _lexware_rabatt(ocr)
    r = rechnung_aus_text(text, finde_vorlage(text, lade_vorlagen(STANDARD)), VERKAEUFER)
    assert r.summe_netto == D("180.00")
    assert [(n.betrag, n.grund, n.ust_satz, n.zuschlag) for n in r.nachlaesse] == [(D("20.00"), "Rabatt", None, False)]
    assert summenabgleich(r) == {D("19"): (D("180.00"), D("34.20"))}
    assert [p.netto for p in r.positionen] == [D("190.00"), D("10.00")]
