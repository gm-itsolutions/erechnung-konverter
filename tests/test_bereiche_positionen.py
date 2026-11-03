from decimal import Decimal as D
from pathlib import Path
import pytest, yaml
from erechnung.bereiche import BereichsFehler, positionen_aus_bereichen, rechnung_aus_bereichen
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, VorlagenFehler, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, seiten_aus, werkstatt_pdf
DATEN = Path(__file__).parent / "daten"
V = yaml.safe_load((DATEN / "bereiche-beispiel.yml").read_text(encoding="utf-8"))
def seiten(tmp_path, pdf):
    return seiten_aus(tmp_path, pdf)
def test_muster1(tmp_path):
    pos, ignoriert = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V)
    assert [(p.nr, p.bezeichnung, p.menge, p.einheit, p.einzelpreis, p.netto, p.ust_satz) for p in pos] == [
        ("1", "Inspektion nach Herstellervorgabe inkl. Probefahrt", D("2"), "HUR", D("95.00"), D("190.00"), D("19")),
        ("2", "Motoröl 5W-30", D("4"), "H87", D("12.50"), D("50.00"), D("19"))]
    assert ignoriert == []
@pytest.mark.parametrize("dx, dy", [(0.02, 0.03), (-0.015, -0.01)])
def test_verschoben(tmp_path, dx, dy):
    pos, _ = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=dx, dy=dy)), V)
    assert [p.netto for p in pos] == [D("190.00"), D("50.00")]
@pytest.mark.parametrize("kopf_wiederholen", [True, False])
def test_mehrseitig_mit_uebertrag(tmp_path, kopf_wiederholen):
    zeilen = [(str(i), f"Teil {i}", "1 Stk", "10,00", "10,00") for i in range(1, 31)]
    pdf = werkstatt_pdf(zeilen, ("300,00", "57,00", "357,00"), umbruch_nach=20, uebertrag="200,00",
                        kopf_wiederholen=kopf_wiederholen)
    s = seiten(tmp_path, pdf)
    assert len(s) == 2
    pos, ignoriert = positionen_aus_bereichen(s, V)
    assert [p.nr for p in pos] == [str(i) for i in range(1, 31)]
    assert all(p.bezeichnung == f"Teil {p.nr}" for p in pos)       # kein Briefkopf in einer Bezeichnung
    assert len(ignoriert) == 2 and all("Übertrag" in z for z in ignoriert)
    r = rechnung_aus_bereichen(s, V, VERKAEUFER)
    assert summenabgleich(r) == {D("19"): (D("300.00"), D("57.00"))}
def test_skaliert_wie_edge(tmp_path):
    """Edge „an Seite anpassen“: Seite um 95 % verkleinert und zentriert."""
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, skala=0.95))
    pos, _ = positionen_aus_bereichen(s, V)
    assert [(p.menge, p.einheit, p.netto) for p in pos] == [(D("2"), "HUR", D("190.00")), (D("4"), "H87", D("50.00"))]
    assert rechnung_aus_bereichen(s, V, VERKAEUFER).summe_brutto == D("285.60")
def test_kopf_fehlt(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["positionen"]["kopf"]["text"] = "Pos Artikel"
    with pytest.raises(BereichsFehler, match="Tabellenkopf"):
        positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
def test_menge_fehlt_gilt_eins(tmp_path):
    z = [("1", "Pauschale Diagnose", "", "80,00", "80,00")]
    pos, _ = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(z, ("80,00", "15,20", "95,20"))), V)
    assert (pos[0].menge, pos[0].einheit) == (D("1"), "C62")
def test_preis_unlesbar_ist_kein_traceback(tmp_path):
    """W10: Nicht-Zahl im Preisfeld → Preis aus Netto/Menge, kein IndexError."""
    z = [("1", "Teil", "2 Stk", "n/a", "20,00")]
    pos, _ = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(z, ("20,00", "3,80", "23,80"))), V)
    assert pos[0].einzelpreis == D("10.00")
def test_spur_tabelle(tmp_path):
    spur = {}
    rechnung_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V, VERKAEUFER, spur=spur)
    assert {"nummer", "summe_brutto", "positionen1"} <= set(spur)
def test_lies_rechnung_text_pdf(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "b.yml").write_text((DATEN / "bereiche-beispiel.yml").read_text(encoding="utf-8"), encoding="utf-8")
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER)
    assert (r.vorlage, r.nummer, r.summe_brutto, len(r.positionen)) == ("test-bereiche", "BW-2026-17", D("285.60"), 2)
    summenabgleich(r)
def test_lies_rechnung_fehler_ist_vorlagenfehler(tmp_path):
    (tmp_path / "v").mkdir()
    v = yaml.safe_load(yaml.safe_dump(V))
    v["positionen"]["kopf"]["text"] = "Pos Artikel"
    (tmp_path / "v" / "b.yml").write_text(yaml.safe_dump(v, allow_unicode=True), encoding="utf-8")
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
    with pytest.raises(VorlagenFehler, match="Tabellenkopf"):
        lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER)
def test_lies_rechnung_ocr_mit_seiten(tmp_path, monkeypatch):
    """W1: Lesart (name, (text, seiten)) → Bereichsleser mit ocr=True."""
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "b.yml").write_text((DATEN / "bereiche-beispiel.yml").read_text(encoding="utf-8"), encoding="utf-8")
    pdf = tmp_path / "bild.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")       # ohne Text; wird gar nicht geöffnet
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1))
    text = " ".join(w.text for w in s[0])
    monkeypatch.setattr("erechnung.vorlagen.pdf_text", lambda *a, **k: "")
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER,
                      ocr=lambda p: iter([("test", (text, s))]))
    assert (r.nummer, len(r.positionen), r.ocr_lesart) == ("BW-2026-17", 2, "test")
