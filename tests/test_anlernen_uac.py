import json
from pathlib import Path
import pytest, yaml
from erechnung.__main__ import main
from erechnung.anlernen import erhoehen, verwalten
from test_anlernen_server import anfrage, anmelden, lauf   # noqa: F401 (Fixture)
from test_anlernen_verwalten import _entwurf, _konfig_datei
@pytest.fixture
def lauf_mit_entwurf(lauf):
    s, url, tmp = lauf
    lese, schreibe = anmelden(s, url)
    _entwurf(s.z.daten / "entwuerfe" / "test-bereiche")
    return s, schreibe, [], lese
def _falsch_admin(aufrufe, ergebnis='{"ok": true, "meldung": "aktiviert"}'):
    def f(arg):
        aufrufe.append(arg)
        if ergebnis is not None:
            Path(arg[arg.index("--ergebnis") + 1]).write_text(ergebnis, encoding="utf-8")
        return 0
    return f
def test_api_aktivieren_ruft_uac(lauf_mit_entwurf, monkeypatch):
    """Server ruft als_admin mit python.exe -m erechnung vorlage aktivieren … auf und liest die Ergebnisdatei."""
    s, schreibe, aufrufe, _ = lauf_mit_entwurf
    monkeypatch.setattr("erechnung.anlernen.erhoehen.als_admin", _falsch_admin(aufrufe))
    st, _, b = anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', schreibe)
    assert st == 200 and json.loads(b) == {"ok": True, "meldung": "aktiviert"}
    a = aufrufe[0]
    assert a[:4] == ["-m", "erechnung", "vorlage", "aktivieren"]
    assert Path(a[4]) == s.z.daten / "entwuerfe" / "test-bereiche" and a[a.index("--konfig") + 1] == str(s.z.konfig)
    ergebnis = Path(a[a.index("--ergebnis") + 1])
    assert ergebnis.parent.parent == s.z.daten / "arbeit" and not ergebnis.parent.exists()   # frischer Ordner, danach weg
def test_api_bestaetigung_fehlt(lauf_mit_entwurf):
    s, schreibe, _, _ = lauf_mit_entwurf
    assert anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1"]}', schreibe)[0] == 400
    assert anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": "m1 m2"}', schreibe)[0] == 400
def test_api_uac_abgebrochen(lauf_mit_entwurf, monkeypatch):
    s, schreibe, _, _ = lauf_mit_entwurf
    monkeypatch.setattr("erechnung.anlernen.erhoehen.als_admin", lambda arg: -1)
    st, _, b = anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', schreibe)
    assert st == 200 and json.loads(b) == {"ok": False, "meldung": "Administratorfreigabe abgebrochen"}
def test_api_ohne_windows_und_ohne_ergebnis(lauf_mit_entwurf, monkeypatch):
    s, schreibe, aufrufe, _ = lauf_mit_entwurf
    def kein_windows(arg):
        raise RuntimeError("UAC gibt es nur unter Windows")
    monkeypatch.setattr(erhoehen, "als_admin", kein_windows)
    b = anfrage(s, "POST", "/api/vorlage/test-bereiche/deaktivieren", b"", schreibe)[2]
    assert json.loads(b) == {"ok": False, "meldung": "UAC gibt es nur unter Windows"}
    for ergebnis in (None, "kaputt", '{"ok": "ja"}'):
        monkeypatch.setattr(erhoehen, "als_admin", _falsch_admin(aufrufe, ergebnis))
        b = anfrage(s, "POST", "/api/vorlage/test-bereiche/loeschen", b"", schreibe)[2]
        assert json.loads(b) == {"ok": False, "meldung": "kein Ergebnis vom Administrator-Aufruf"}
def test_api_verwalten_routen(lauf_mit_entwurf, monkeypatch):
    s, schreibe, aufrufe, lese = lauf_mit_entwurf
    monkeypatch.setattr(erhoehen, "als_admin", _falsch_admin(aufrufe, '{"ok": true, "meldung": "x"}'))
    for aktion in ("deaktivieren", "reaktivieren", "loeschen"):
        assert anfrage(s, "POST", f"/api/vorlage/test-bereiche/{aktion}", b"", schreibe)[0] == 200
        assert aufrufe[-1][3:5] == [aktion, "test-bereiche"]
    assert anfrage(s, "POST", "/api/vorlage/CON/loeschen", b"", schreibe)[0] == 400
    assert anfrage(s, "POST", "/api/vorlage/con/loeschen", b"", schreibe)[0] == 400
    assert anfrage(s, "POST", "/api/vorlage/test-bereiche/umbenennen", b"", schreibe)[0] == 404
    n = len(aufrufe)
    assert anfrage(s, "POST", "/api/vorlage/test-bereiche/loeschen", b"", {**schreibe, "X-CSRF": "x"})[0] == 403
    assert anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', lese)[0] == 403
    assert len(aufrufe) == n
def test_api_stand_vorlagenlisten(lauf_mit_entwurf):
    s, _, _, lese = lauf_mit_entwurf
    angelernt = s.z.konfig.parent / "vorlagen" / "angelernt"
    (angelernt / "deaktiviert").mkdir(parents=True)
    (angelernt / "werkstatt.yml").write_text("x", encoding="utf-8")
    (angelernt / "deaktiviert" / "alt.yml").write_text("x", encoding="utf-8")
    (angelernt / "deaktiviert" / "werkstatt-20261103-101500.yml").write_text("x", encoding="utf-8")
    (angelernt / "protokoll.txt").write_text("x", encoding="utf-8")
    d = json.loads(anfrage(s, "GET", "/api/stand", kopf=lese)[2])
    assert d["aktiv"] == ["werkstatt"] and d["deaktiviert"] == ["alt"] and "lexware-gm-it" in d["mitgeliefert"]
def test_api_probelauf(lauf_mit_entwurf):
    s, schreibe, _, _ = lauf_mit_entwurf
    s.z.k.pruefe = lambda xml: "valid (Test)"
    d = json.loads(anfrage(s, "POST", "/api/entwurf/test-bereiche/probelauf", b"", schreibe)[2])
    assert d["bereit"] is True and [m["id"] for m in d["muster"]] == ["m1", "m2"]
def test_api_export(lauf_mit_entwurf):
    s, _, _, lese = lauf_mit_entwurf
    st, k, b = anfrage(s, "GET", "/api/entwurf/test-bereiche/export", kopf=lese)
    assert st == 200 and k["Content-Type"] == "application/yaml; charset=utf-8"
    assert k["Content-Disposition"].startswith('attachment; filename="erechnung-vorlage-test-bereiche-')
    assert yaml.safe_load(b)["name"] == "test-bereiche" and b"%PDF" not in b
    assert list((s.z.daten / "arbeit").iterdir()) == []                                  # Datei danach weg
    (s.z.daten / "entwuerfe" / "test-bereiche" / "vorlage.json").write_text('{"name": "test-bereiche"}', encoding="utf-8")
    assert anfrage(s, "GET", "/api/entwurf/test-bereiche/export", kopf=lese)[0] == 400
def test_cli_vorlage_schreibt_ergebnis(tmp_path):
    konfig = _konfig_datei(tmp_path)
    ergebnis = tmp_path / "e.json"
    code = main(["vorlage", "deaktivieren", "gibt-es-nicht", "--konfig", str(konfig), "--benutzer", "kasse", "--ergebnis", str(ergebnis)],
                programm_konfig=konfig)
    assert code == 1 and json.loads(ergebnis.read_text(encoding="utf-8"))["ok"] is False
    assert "gibt-es-nicht" in (konfig.parent / "erechnung.log").read_text(encoding="utf-8")
def test_cli_vorlage_aktivieren(tmp_path, monkeypatch):
    konfig = _konfig_datei(tmp_path)
    k = verwalten._konfig(konfig, tmp_path / "arbeit")
    k.pruefe = lambda xml: "valid (Test)"
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    e = _entwurf(tmp_path / "anlernen" / "entwuerfe" / "test-bereiche")
    ergebnis = tmp_path / "e.json"
    assert main(["vorlage", "aktivieren", str(e), "--konfig", str(konfig), "--ergebnis", str(ergebnis)], programm_konfig=konfig) == 0
    assert (konfig.parent / "vorlagen" / "angelernt" / "test-bereiche.yml").is_file()
def test_cli_vorlage_fremde_konfig_abgelehnt(tmp_path):
    """Der Benutzer darf den erhöhten Lauf nicht auf eine eigene konfig.json (eigene Schreibziele) lenken."""
    echt = _konfig_datei(tmp_path)
    fremd = tmp_path / "fremd" / "konfig.json"
    fremd.parent.mkdir()
    fremd.write_text(echt.read_text(encoding="utf-8"), encoding="utf-8")
    ergebnis = tmp_path / "e.json"
    assert main(["vorlage", "loeschen", "x1", "--konfig", str(fremd), "--ergebnis", str(ergebnis)], programm_konfig=echt) == 1
    assert not ergebnis.exists() and not (fremd.parent / "erechnung.log").exists() and not (fremd.parent / "vorlagen").exists()
def test_cli_vorlage_entwurf_ausserhalb(tmp_path):
    konfig = _konfig_datei(tmp_path)
    e = _entwurf(tmp_path / "irgendwo" / "test-bereiche")
    ergebnis = tmp_path / "e.json"
    assert main(["vorlage", "aktivieren", str(e), "--konfig", str(konfig), "--ergebnis", str(ergebnis)], programm_konfig=konfig) == 1
    assert "Anlern-Ordner" in json.loads(ergebnis.read_text(encoding="utf-8"))["meldung"]
def test_cli_ergebnis_exklusiv(tmp_path):
    konfig = _konfig_datei(tmp_path)
    vorhanden = tmp_path / "e.json"
    vorhanden.write_text("alt", encoding="utf-8")
    assert main(["vorlage", "loeschen", "x1", "--konfig", str(konfig), "--ergebnis", str(vorhanden)], programm_konfig=konfig) == 1
    assert vorhanden.read_text(encoding="utf-8") == "alt"
    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (tmp_path / "link").symlink_to(ziel, target_is_directory=True)
    assert main(["vorlage", "loeschen", "x1", "--konfig", str(konfig), "--ergebnis", str(tmp_path / "link" / "e.json")],
                programm_konfig=konfig) == 1
    assert list(ziel.iterdir()) == []
def test_programm_konfig_aus_paketlage(tmp_path, monkeypatch):
    paket = tmp_path / "GM-IT" / "erechnung-konverter" / "versionen" / "0.2.0" / "app" / "erechnung" / "anlernen"
    paket.mkdir(parents=True)
    monkeypatch.setattr(erhoehen, "__file__", str(paket / "erhoehen.py"))
    assert erhoehen.programm_konfig() == tmp_path / "GM-IT" / "erechnung-konverter" / "konfig.json"
    monkeypatch.setattr(erhoehen, "__file__", str(tmp_path / "erhoehen.py"))
    with pytest.raises(ValueError):
        erhoehen.programm_konfig()
def test_als_admin_nur_windows(monkeypatch):
    monkeypatch.setattr(erhoehen, "_windows", lambda: False)
    with pytest.raises(RuntimeError):
        erhoehen.als_admin(["-m", "erechnung", "--version"])
