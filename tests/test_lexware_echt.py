"""Abgleich mit echten Lexware-Rechnungen (nur mit ERECHNUNG_TESTDATEN, Daten nie im Repo)."""
import os
import shutil
import tempfile
from functools import partial
from pathlib import Path
import pytest
from decimal import Decimal as D
from facturx import xml_check_xsd
from lxml import etree
from erechnung import mustang, ocr
from erechnung.betraege import betraege
from erechnung.cii import erzeuge_cii
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER, bild_pdf

DATEN = os.environ.get("ERECHNUNG_TESTDATEN")
pytestmark = [pytest.mark.echt, pytest.mark.skipif(not DATEN, reason="ERECHNUNG_TESTDATEN nicht gesetzt")]
# Erzeugte XML für die Mustang-Prüfung durch Marvin (docs/pruefung.md), außerhalb des Repos.
AUSGABE = Path(tempfile.gettempdir()) / "erechnung-pruefung"
# RE0158: Rabatt auf Rechnungsebene (abzgl. Rabatt, Gesamt (netto))
NUMMERN = ["RE0146", "RE0148", "RE0149", "RE0158"]

@pytest.mark.parametrize("nummer", NUMMERN)
def test_wie_lexware(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    steuern = summenabgleich(r)
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert r.nummer == soll["nummer"]
    assert (r.summe_netto, sum(s for _, s in steuern.values()), r.summe_brutto) == (soll["netto"], soll["steuer"], soll["brutto"])
    assert [p.netto for p in r.positionen] == soll["positionen"]
    assert sum((n.betrag for n in r.nachlaesse), D(0)) == soll["nachlass"]

@pytest.mark.parametrize("nummer", NUMMERN)
def test_xsd_gueltig(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    xml = erzeuge_cii(r, summenabgleich(r))
    AUSGABE.mkdir(mode=0o700, exist_ok=True)
    (AUSGABE / f"{nummer}.xml").write_bytes(xml)
    assert xml_check_xsd(xml, flavor="factur-x", level="en16931")
    assert betraege(xml) == betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())

@pytest.mark.skipif(not mustang.mustang(), reason="java oder Mustang-CLI (MUSTANG_JAR) fehlt")
@pytest.mark.parametrize("nummer", NUMMERN)
def test_mustang_gueltig(nummer, tmp_path):
    """Mustang (XSD + EN16931-Schematron) auf die erzeugte XML, wie in der App."""
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    (tmp_path / f"{nummer}.xml").write_bytes(erzeuge_cii(r, summenabgleich(r)))
    assert "0 verletzt" in mustang.pruefe(tmp_path / f"{nummer}.xml", mustang.mustang())

def _lexware(nummer):
    return etree.parse(str(Path(DATEN) / f"{nummer}.lexware.xml"))

@pytest.mark.parametrize("nummer", NUMMERN)
def test_faellig_wie_lexware(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    soll = _lexware(nummer).xpath("string(//*[local-name()='DueDateDateTime']/*)")
    assert r.faellig.strftime("%Y%m%d") == soll

@pytest.mark.parametrize("nummer", NUMMERN)
def test_bezeichnung_wie_lexware(nummer):
    """Bezeichnung = Lexware-Name + Beschreibung, Silbentrennung aufgelöst (Lexware druckt „- “ als „•“)."""
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    soll = [" ".join(p.xpath("string(.//*[local-name()='Name'])").split()
                     + p.xpath("string(.//*[local-name()='Description'])").split())
            for p in _lexware(nummer).xpath("//*[local-name()='SpecifiedTradeProduct']")]
    assert [" ".join(p.bezeichnung.replace("•", "-").split()) for p in r.positionen] == soll

@pytest.mark.skipif(not shutil.which("tesseract"), reason="tesseract nicht installiert")
@pytest.mark.parametrize("dpi", [300, 200])
@pytest.mark.parametrize("nummer", NUMMERN)
def test_ocr_wie_lexware(nummer, dpi, tmp_path, monkeypatch):
    """Echte Rechnung als Bild-PDF ohne Text (wie Edge-Druck) → Texterkennung → dieselben Beträge wie Lexware.
    Nutzt tessdata_best aus $ERECHNUNG_TESTDATEN/tessdata (wie im Paket), sonst das tessdata des Systems."""
    if (Path(DATEN) / "tessdata" / "deu.traineddata").exists():
        monkeypatch.setenv("TESSDATA_PREFIX", str(Path(DATEN) / "tessdata"))
    pdf = tmp_path / f"{nummer}.pdf"
    pdf.write_bytes(bild_pdf((Path(DATEN) / f"{nummer}.pdf").read_bytes(), dpi))
    (tmp_path / "arbeit").mkdir()
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD), VERKAEUFER, partial(ocr.erkenne, arbeit=tmp_path / "arbeit", aufruf=ocr.tesseract()))
    assert r.ocr_text
    steuern = summenabgleich(r)
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert r.nummer == soll["nummer"]
    assert (r.summe_netto, sum(s for _, s in steuern.values()), r.summe_brutto) == (soll["netto"], soll["steuer"], soll["brutto"])
    assert [p.netto for p in r.positionen] == soll["positionen"]
    assert sum((n.betrag for n in r.nachlaesse), D(0)) == soll["nachlass"]
    assert r.faellig.strftime("%Y%m%d") == _lexware(nummer).xpath("string(//*[local-name()='DueDateDateTime']/*)")
    assert betraege(erzeuge_cii(r, steuern)) == soll
