# Task 10: UAC-Aufruf, Server-Routen fürs Verwalten, CLI `vorlage`

Spezifikation: `docs/lernmodus/spezifikation.md` 4 (Aktivieren braucht Administratorrechte), 7.3, 7.4. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/anlernen/erhoehen.py`, `tests/test_anlernen_uac.py`
- Modify: `erechnung/anlernen/server.py` (Routen, `/api/stand` füllen), `erechnung/__main__.py` (Befehl `vorlage`)

**Interfaces:**
- Consumes: Task 09 (`probelauf`, `aktivieren`, `deaktivieren`, `reaktivieren`, `loeschen`, `exportieren`, Testhilfen `_entwurf`, `_konfig_datei`); Task 07/08 (`route`, `Fehler`, `json_antwort`, `lies_json`, `entwurf_ordner`, Testhilfen `lauf`, `anfrage`, `anmelden`); Task 06 `lade_alle_vorlagen`, `ANGELERNT`.
- Produces:
  - `erhoehen.als_admin(argumente: list[str]) -> int` (Windows: UAC, wartet, Exit-Code; Abbruch → -1; sonst `RuntimeError`)
  - CLI (erhöht aufgerufen): `python.exe -m erechnung vorlage {aktivieren <entwurf-ordner> | deaktivieren <name> | reaktivieren <name> | loeschen <name>} --konfig <konfig.json> --benutzer <name> --ergebnis <json-datei>`
  - API: `POST /api/entwurf/<n>/probelauf`, `POST /api/entwurf/<n>/aktivieren` `{bestaetigt: [ids]}`, `POST /api/vorlage/<name>/(deaktivieren|reaktivieren|loeschen)`, `GET /api/entwurf/<n>/export`; `/api/stand` mit `mitgeliefert`, `aktiv`, `deaktiviert`

- [ ] **Step 1: Failing tests** – `tests/test_anlernen_uac.py`

```python
import json
from pathlib import Path
import pytest
from erechnung.__main__ import main
from test_anlernen_server import anfrage, anmelden, lauf   # noqa: F401 (Fixture)
from test_anlernen_verwalten import _entwurf, _konfig_datei
@pytest.fixture
def lauf_mit_entwurf(lauf):
    s, url, tmp = lauf
    _, schreibe = anmelden(s, url)
    _entwurf(s.z.daten / "entwuerfe" / "test-bereiche")
    return s, schreibe, []
def test_api_aktivieren_ruft_uac(lauf_mit_entwurf, monkeypatch):
    """Server ruft als_admin mit python.exe -m erechnung vorlage aktivieren … auf und liest die Ergebnisdatei."""
    s, schreibe, aufrufe = lauf_mit_entwurf
    def falsch_admin(arg):
        aufrufe.append(arg)
        Path(arg[arg.index("--ergebnis") + 1]).write_text('{"ok": true, "meldung": "aktiviert"}', encoding="utf-8")
        return 0
    monkeypatch.setattr("erechnung.anlernen.erhoehen.als_admin", falsch_admin)
    st, _, b = anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', schreibe)
    assert st == 200 and json.loads(b)["ok"] and aufrufe[0][:4] == ["-m", "erechnung", "vorlage", "aktivieren"]
```

def test_api_bestaetigung_fehlt(lauf_mit_entwurf):
    s, schreibe, _ = lauf_mit_entwurf
    assert anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1"]}', schreibe)[0] == 400
def test_api_uac_abgebrochen(lauf_mit_entwurf, monkeypatch):
    s, schreibe, _ = lauf_mit_entwurf
    monkeypatch.setattr("erechnung.anlernen.erhoehen.als_admin", lambda arg: -1)
    st, _, b = anfrage(s, "POST", "/api/entwurf/test-bereiche/aktivieren", b'{"bestaetigt": ["m1", "m2"]}', schreibe)
    assert st == 200 and json.loads(b) == {"ok": False, "meldung": "Administratorfreigabe abgebrochen"}
def test_cli_vorlage_schreibt_ergebnis(tmp_path):
    konfig = _konfig_datei(tmp_path)
    ergebnis = tmp_path / "e.json"
    code = main(["vorlage", "deaktivieren", "gibt-es-nicht", "--konfig", str(konfig), "--benutzer", "kasse", "--ergebnis", str(ergebnis)])
    assert code == 1 and json.loads(ergebnis.read_text(encoding="utf-8"))["ok"] is False
def test_als_admin_nur_windows(monkeypatch):
    from erechnung.anlernen import erhoehen
    monkeypatch.setattr(erhoehen.os, "name", "posix")
    with pytest.raises(RuntimeError):
        erhoehen.als_admin(["-m", "erechnung", "--version"])
```

Der Server ruft `erhoehen.als_admin` über das Modul auf (`from . import erhoehen` … `erhoehen.als_admin(...)`), damit der Ersatz im Test greift.

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_anlernen_uac.py -q`

- [ ] **Step 3: `erhoehen.py`**

```python
"""Erhöhter Aufruf per UAC (ShellExecuteExW, Verb runas), wartet auf das Ende und liefert den Exit-Code."""
import ctypes, os, subprocess, sys
from ctypes import wintypes
class _SEI(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
def als_admin(argumente: list[str]) -> int:
    if os.name != "nt":
        raise RuntimeError("UAC gibt es nur unter Windows")
    python = os.path.join(os.path.dirname(sys.executable), "python.exe")   # nicht pythonw: Exit-Code zuverlässig
    sei = _SEI(cbSize=ctypes.sizeof(_SEI), fMask=0x00000040, lpVerb="runas", lpFile=python,      # SEE_MASK_NOCLOSEPROCESS
               lpParameters=subprocess.list2cmdline(argumente), nShow=0)
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei)):
        return -1                                   # abgebrochen (ERROR_CANCELLED) oder nicht startbar
    ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
    ctypes.windll.kernel32.CloseHandle(sei.hProcess)
    return code.value
```

Kein automatischer Test für den echten UAC-Weg (nur Windows); geprüft in Task 11.

- [ ] **Step 4: Routen und CLI** – Server: `probelauf` mit `z.k` (Benutzer-Arbeitsordner); `aktivieren`: `bestaetigt` muss alle Muster-IDs enthalten (sonst 400), Ergebnisdatei `z.daten/"arbeit"/f"ergebnis-{secrets.token_hex(8)}.json"`, Aufruf `als_admin(["-m", "erechnung", "vorlage", "aktivieren", str(entwurf), "--konfig", str(z.konfig), "--benutzer", os.environ.get("USERNAME", ""), "--ergebnis", str(datei)])`; Exit-Code -1 → `{"ok": False, "meldung": "Administratorfreigabe abgebrochen"}`; `RuntimeError` (kein Windows) → `{"ok": False, "meldung": str(e)}`; fehlt die Ergebnisdatei → `{"ok": False, "meldung": "kein Ergebnis vom Administrator-Aufruf"}`; danach `z.k.vorlagen = lade_alle_vorlagen(z.k.vorlagen_ordner)`. Gleiches Muster für deaktivieren/reaktivieren/loeschen. `GET /export` → `exportieren` in `z.daten/"arbeit"`, Antwort `application/yaml; charset=utf-8` mit `Content-Disposition: attachment; filename="erechnung-vorlage-<name>-<datum>.yml"` (nur die Vorlage, keine Muster-PDFs, F2; Datei danach löschen). `/api/stand`: `mitgeliefert`, `aktiv` (Namen in `vorlagen/angelernt/*.yml`), `deaktiviert` (`deaktiviert/*.yml` ohne Stempel). CLI `vorlage`: führt die Funktion aus, schreibt `{"ok", "meldung"}` nach `--ergebnis`, Exit 0/1; Log in `<konfig-ordner>/erechnung.log`.

- [ ] **Step 5: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/anlernen erechnung/__main__.py tests/test_anlernen_uac.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Aktivieren per UAC, Verwaltungs-Routen, CLI vorlage" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
