"""Mustang-Prüfung: Auswertung mit ersetztem Aufruf, dazu echter Lauf, wenn java und Mustang-CLI da sind."""
import sys
import pytest
from erechnung import mustang
from erechnung.cii import erzeuge_cii
from erechnung.modell import summenabgleich
from hilfen import beispiel_rechnung

GUELTIG = """<?xml version="1.0" encoding="UTF-8"?>

<validation filename="x.xml" datetime="2026-11-02 18:33:48">
  <xml>
    <info><version>2</version><profile>urn:cen.eu:en16931:2017</profile><validator version="2.26.0"/>
      <rules><fired>123</fired><failed>0</failed></rules><duration unit="ms">3561</duration></info>
    <summary status="valid"/>
  </xml>
  <summary status="valid"/>
</validation>
"""
UNGUELTIG = """<?xml version="1.0" encoding="UTF-8"?>
<validation filename="x.xml" datetime="2026-11-02 18:34:12">
  <xml>
    <info><version>2</version><profile>urn:cen.eu:en16931:2017</profile><validator version="2.26.0"/>
      <rules><fired>89</fired><failed>2</failed></rules><duration unit="ms">4228</duration></info>
    <messages>
      <error type="4" location="/x" criterion="y">[BR-CO-15]-Invoice total amount with VAT (BT-112) = Invoice total amount without VAT (BT-109) + Invoice total VAT amount (BT-110). [ID BR-CO-15] from /xslt/ZF_250/FACTUR-X_EN16931.xslt)</error>
      <error type="4" location="/x" criterion="z">[BR-CO-16]-Amount due for payment (BT-115) = Invoice total amount with VAT (BT-112) -Paid amount (BT-113) +Rounding amount (BT-114). [ID BR-CO-16] from /xslt/ZF_250/FACTUR-X_EN16931.xslt)</error>
    </messages>
    <summary status="invalid"/>
  </xml>
  <messages></messages>
  <summary status="invalid"/>
</validation>
"""

def falsch(ausgabe: str, code: int = 0, warte: float = 0) -> list[str]:
    """Ersetzt Mustang: gibt `ausgabe` auf stdout aus und endet mit `code` (Quelle kommt als letztes Argument)."""
    return [sys.executable, "-c", f"import sys, time; time.sleep({warte}); sys.stdout.write({ausgabe!r}); sys.exit({code})"]

def test_gueltig(tmp_path):
    xml = tmp_path / "x.xml"
    xml.write_bytes(b"<x/>")
    s = mustang.pruefe(xml, falsch(GUELTIG))
    assert "valid" in s and "123 Regeln" in s and "0 verletzt" in s and "2.26.0" in s

def test_ungueltig(tmp_path):
    with pytest.raises(ValueError) as e:
        mustang.pruefe(tmp_path / "x.xml", falsch(UNGUELTIG, 255))
    t = str(e.value)
    assert "ungültig" in t
    assert "BR-CO-15: Invoice total amount with VAT (BT-112)" in t and "BR-CO-16: Amount due" in t
    assert "xslt" not in t

def test_gueltig_aber_fehlercode(tmp_path):
    with pytest.raises(ValueError, match="Code 3"):
        mustang.pruefe(tmp_path / "x.xml", falsch(GUELTIG, 3))

def test_ohne_bericht(tmp_path):
    with pytest.raises(ValueError, match="ohne Bericht"):
        mustang.pruefe(tmp_path / "x.xml", falsch("Exception in thread main", 1))

def test_nicht_startbar(tmp_path):
    with pytest.raises(ValueError, match="nicht startbar"):
        mustang.pruefe(tmp_path / "x.xml", [str(tmp_path / "gibt-es-nicht.exe")])

def test_frist(tmp_path, monkeypatch):
    monkeypatch.setattr(mustang, "FRIST", 0.5)
    with pytest.raises(ValueError, match="Frist"):
        mustang.pruefe(tmp_path / "x.xml", falsch(GUELTIG, 0, 5))

def test_aufruf_aus_umgebung(tmp_path, monkeypatch):
    jar = tmp_path / "Mustang-CLI-9.9.9.jar"
    jar.write_bytes(b"")
    monkeypatch.setenv("MUSTANG_JAR", str(jar))
    monkeypatch.setattr(mustang.shutil, "which", lambda n: "/opt/java/bin/java")
    a = mustang.mustang()
    assert a[0] == "/opt/java/bin/java" and str(jar) in a and a[-2:] == ["validate", "--source"]
    monkeypatch.setattr(mustang.shutil, "which", lambda n: None)
    assert mustang.mustang() is None

def test_aufruf_im_paket(tmp_path, monkeypatch):
    """Im ZIP: java\\bin\\java.exe und mustang\\Mustang-CLI-<v>.jar neben app\\ haben Vorrang."""
    (tmp_path / "java/bin").mkdir(parents=True)
    (tmp_path / "java/bin/java.exe").write_bytes(b"")
    (tmp_path / "mustang").mkdir()
    (tmp_path / "mustang/Mustang-CLI-2.26.0.jar").write_bytes(b"")
    monkeypatch.setattr(mustang, "WURZEL", tmp_path)
    monkeypatch.delenv("MUSTANG_JAR", raising=False)
    a = mustang.mustang()
    assert a[0] == str(tmp_path / "java/bin/java.exe") and str(tmp_path / "mustang/Mustang-CLI-2.26.0.jar") in a

ECHT = mustang.mustang()

@pytest.mark.skipif(not ECHT, reason="java oder Mustang-CLI (MUSTANG_JAR) fehlt")
def test_echt_synthetisch(tmp_path):
    """Echte Mustang-CLI: synthetische Rechnung gültig (XSD + EN16931-Schematron), falsche Summe ungültig."""
    r = beispiel_rechnung()
    xml = erzeuge_cii(r, summenabgleich(r))
    (tmp_path / "gut.xml").write_bytes(xml)
    assert "valid" in mustang.pruefe(tmp_path / "gut.xml", ECHT)
    (tmp_path / "falsch.xml").write_bytes(xml.replace(b"<ram:GrandTotalAmount>238.00", b"<ram:GrandTotalAmount>239.00"))
    with pytest.raises(ValueError, match="BR-CO-15"):
        mustang.pruefe(tmp_path / "falsch.xml", ECHT)

@pytest.mark.skipif(not ECHT, reason="java oder Mustang-CLI (MUSTANG_JAR) fehlt")
def test_echt_rabatt(tmp_path):
    from decimal import Decimal as D
    from erechnung.modell import Nachlass
    r = beispiel_rechnung()
    r.nachlaesse = [Nachlass(D("20.00"), "Rabatt")]
    r.summe_netto, r.summe_ust, r.summe_brutto, r.steuern = D("180.00"), D("34.20"), D("214.20"), {D("19"): D("34.20")}
    (tmp_path / "rabatt.xml").write_bytes(erzeuge_cii(r, summenabgleich(r)))
    assert "valid" in mustang.pruefe(tmp_path / "rabatt.xml", ECHT)
