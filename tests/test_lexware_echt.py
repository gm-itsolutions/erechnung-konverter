"""Abgleich mit echten Lexware-Rechnungen (nur mit ERECHNUNG_TESTDATEN, Daten nie im Repo)."""
import os
import tempfile
from pathlib import Path
import pytest
from facturx import xml_check_xsd
from lxml import etree
from erechnung.betraege import betraege
from erechnung.cii import erzeuge_cii
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER

DATEN = os.environ.get("ERECHNUNG_TESTDATEN")
pytestmark = [pytest.mark.echt, pytest.mark.skipif(not DATEN, reason="ERECHNUNG_TESTDATEN nicht gesetzt")]
# Erzeugte XML für die Mustang-Prüfung durch Marvin (docs/pruefung.md), außerhalb des Repos.
AUSGABE = Path(tempfile.gettempdir()) / "erechnung-pruefung"

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_wie_lexware(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    steuern = summenabgleich(r)
    soll = betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())
    assert r.nummer == soll["nummer"]
    assert (r.summe_netto, sum(s for _, s in steuern.values()), r.summe_brutto) == (soll["netto"], soll["steuer"], soll["brutto"])
    assert [p.netto for p in r.positionen] == soll["positionen"]

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_xsd_gueltig(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    xml = erzeuge_cii(r, summenabgleich(r))
    AUSGABE.mkdir(mode=0o700, exist_ok=True)
    (AUSGABE / f"{nummer}.xml").write_bytes(xml)
    assert xml_check_xsd(xml, flavor="factur-x", level="en16931")
    assert betraege(xml) == betraege((Path(DATEN) / f"{nummer}.lexware.xml").read_bytes())

def _lexware(nummer):
    return etree.parse(str(Path(DATEN) / f"{nummer}.lexware.xml"))

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_faellig_wie_lexware(nummer):
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    soll = _lexware(nummer).xpath("string(//*[local-name()='DueDateDateTime']/*)")
    assert r.faellig.strftime("%Y%m%d") == soll

@pytest.mark.parametrize("nummer", ["RE0146", "RE0148", "RE0149"])
def test_bezeichnung_wie_lexware(nummer):
    """Bezeichnung = Lexware-Name + Beschreibung, Silbentrennung aufgelöst (Lexware druckt „- “ als „•“)."""
    r = lies_rechnung(Path(DATEN) / f"{nummer}.pdf", lade_vorlagen(STANDARD), VERKAEUFER)
    soll = [" ".join(p.xpath("string(.//*[local-name()='Name'])").split()
                     + p.xpath("string(.//*[local-name()='Description'])").split())
            for p in _lexware(nummer).xpath("//*[local-name()='SpecifiedTradeProduct']")]
    assert [" ".join(p.bezeichnung.replace("•", "-").split()) for p in r.positionen] == soll
