import json, os, re, time
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
ID = "0123456789abcdef"
def _falsch_admin(aufrufe, ergebnis='{"ok": true, "meldung": "aktiviert"}', programm=None):
    """Ersatz für den erhöhten Lauf: schreibt wie dieser nach <Programmordner>/ergebnisse/<id>.json."""
    def f(arg):
        aufrufe.append(arg)
        if ergebnis is not None:
            datei = Path(arg[arg.index("--konfig") + 1]).parent / "ergebnisse" / f"{arg[arg.index('--ergebnis-id') + 1]}.json"
            datei.parent.mkdir(exist_ok=True)
            datei.write_text(ergebnis, encoding="utf-8")
        return 0
    return f
def _cli(tmp_path, *arg, konfig=None, erlaubt=None, eid=ID):
    konfig = konfig or _konfig_datei(tmp_path)
    code = main(["vorlage", *arg, "--konfig", str(konfig), "--ergebnis-id", eid], programm_konfig=erlaubt or konfig)
    datei = (erlaubt or konfig).parent / "ergebnisse" / f"{eid}.json"
    return code, json.loads(datei.read_text(encoding="utf-8")) if datei.is_file() else None
def test_api_aktivieren_ruft_uac(lauf_mit_entwurf, monkeypatch):
    """Server ruft als_admin mit python.exe -m erechnung vorlage aktivieren … auf und liest die Ergebnisdatei."""
    s, schreibe, aufrufe, _ = lauf_mit_entwurf
    monkeypatch.setattr("erechnung.anlernen.erhoehen.als_admin", _falsch_admin(aufrufe))
    st, _, b = anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', schreibe)
    assert st == 200 and json.loads(b) == {"ok": True, "meldung": "aktiviert"}
    a = aufrufe[0]
    assert a[:4] == ["-m", "erechnung", "vorlage", "aktivieren"]
    assert Path(a[4]) == s.z.daten / "entwuerfe" / "test-bereiche" and a[a.index("--konfig") + 1] == str(s.z.konfig)
    assert re.fullmatch(r"[0-9a-f]{16}", a[a.index("--ergebnis-id") + 1]) and "--ergebnis" not in a
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
    code, e = _cli(tmp_path, "deaktivieren", "gibt-es-nicht", "--benutzer", "kasse\nFALSCH admin=x", konfig=konfig)
    assert code == 1 and e["ok"] is False
    log = (konfig.parent / "erechnung.log").read_text(encoding="utf-8")
    assert "gibt-es-nicht" in log and len(log.splitlines()) == 1 and "kasseFALSCH" in log   # Benutzername gesäubert
def test_cli_vorlage_aktivieren(tmp_path, monkeypatch):
    konfig = _konfig_datei(tmp_path)
    k = verwalten._konfig(konfig, tmp_path / "arbeit")
    k.pruefe = lambda xml: "valid (Test)"
    monkeypatch.setattr(verwalten, "_konfig", lambda konfig, arbeit: k)
    e = _entwurf(tmp_path / "anlernen" / "entwuerfe" / "test-bereiche")
    assert _cli(tmp_path, "aktivieren", str(e), konfig=konfig)[0] == 0
    assert (konfig.parent / "vorlagen" / "angelernt" / "test-bereiche.yml").is_file()
def test_cli_vorlage_fremde_konfig_abgelehnt(tmp_path):
    """Der Benutzer darf den erhöhten Lauf nicht auf eine eigene konfig.json (eigene Schreibziele) lenken."""
    echt = _konfig_datei(tmp_path)
    fremd = tmp_path / "fremd" / "konfig.json"
    fremd.parent.mkdir()
    fremd.write_text(echt.read_text(encoding="utf-8"), encoding="utf-8")
    code, e = _cli(tmp_path, "loeschen", "x1", konfig=fremd, erlaubt=echt)
    assert code == 1 and e is None
    assert not any((fremd.parent / x).exists() for x in ("erechnung.log", "vorlagen", "ergebnisse"))
    assert _cli(tmp_path, "loeschen", "x1", konfig=Path("//host/share/konfig.json"), erlaubt=echt) == (1, None)
def test_cli_vorlage_entwurf_ausserhalb_und_unc(tmp_path):
    konfig = _konfig_datei(tmp_path)
    e = _entwurf(tmp_path / "irgendwo" / "test-bereiche")
    code, erg = _cli(tmp_path, "aktivieren", str(e), konfig=konfig)
    assert code == 1 and "Anlern-Ordner" in erg["meldung"]
    code, erg = _cli(tmp_path, "aktivieren", "//host/share/anlernen/entwuerfe/test-bereiche", konfig=konfig, eid="fedcba9876543210")
    assert code == 1 and "Netzwerk" in erg["meldung"]
def test_cli_ergebnis_id_und_ordner(tmp_path):
    konfig = _konfig_datei(tmp_path)
    for falsch in ("../../x", "0123456789ABCDEF", "abc"):
        assert _cli(tmp_path, "loeschen", "x1", konfig=konfig, eid=falsch) == (1, None)
    assert not (tmp_path / "x.json").exists()
    ordner = konfig.parent / "ergebnisse"
    ordner.mkdir()
    (ordner / f"{ID}.json").write_text("alt", encoding="utf-8")
    alt = ordner / "1111111111111111.json"
    alt.write_text("{}", encoding="utf-8")
    os.utime(alt, (time.time() - 2 * 86400,) * 2)
    assert main(["vorlage", "loeschen", "x1", "--konfig", str(konfig), "--ergebnis-id", ID], programm_konfig=konfig) == 1
    assert (ordner / f"{ID}.json").read_text(encoding="utf-8") == "alt"                  # exklusiv: nicht überschrieben
    assert not alt.exists()                                                               # älter als ein Tag: weg
def test_cli_ergebnisordner_verknuepfung(tmp_path):
    konfig = _konfig_datei(tmp_path)
    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (konfig.parent / "ergebnisse").symlink_to(ziel, target_is_directory=True)
    assert _cli(tmp_path, "loeschen", "x1", konfig=konfig)[0] == 1
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
@pytest.mark.parametrize("pfad", [r"\\host\share\konfig.json", r"\\?\UNC\host\share\konfig.json", r"\\.\pipe\x", "//host/share/x"])
def test_unc_abgelehnt(pfad):
    with pytest.raises(ValueError, match="Netzwerk"):
        erhoehen.pruefe_konfig(Path(pfad), Path("/prog/konfig.json"))
def test_benutzer_name():
    assert erhoehen.benutzer_name("kasse\r\nadmin=x\t" + "y" * 100) == "kasseadmin=x" + "y" * 52
