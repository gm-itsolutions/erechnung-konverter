# Task 05: Überwacher, Konfiguration, CLI

Spezifikation: Abschnitt 3, 3.1, 6, 7. Global Constraints in `index.md`.

**Files:**
- Create: `erechnung/ueberwachen.py`, `tests/test_ueberwachen.py`
- Replace: `erechnung/__main__.py`

**Interfaces:**
- Consumes: `lies_rechnung`, `lade_vorlagen`, `STANDARD`, `VorlagenFehler` (Task 04); `summenabgleich`, `SummenFehler`, `Partei` (Task 01); `erzeuge_cii`, `bette_ein` (Task 03); Testhilfen `VERKAEUFER`, `pdf_aus_text` (Task 01), `VORLAGE`, `TEXT` aus `tests/test_vorlagen.py` (Task 04).
- Produces: `Konfig`, `lade_konfig(datei: Path) -> Konfig`, `pruefe_ordner(k: Konfig) -> None`, `verarbeite(pdf: Path, k: Konfig) -> Path`, `bearbeite(pdf: Path, k: Konfig) -> tuple[bool, str]`, `schritt(k: Konfig) -> int`, `ueberwache(k: Konfig, takt: float = 0.5) -> None`. CLI: `python -m erechnung --version | ueberwachen --konfig K | umwandeln PDF --konfig K`.

- [ ] **Step 1: Failing tests** – `tests/test_ueberwachen.py`

```python
import json, os, subprocess, sys
from pathlib import Path
import pytest
from facturx import get_xml_from_pdf
from erechnung import __version__
from erechnung.ueberwachen import lade_konfig, pruefe_ordner, schritt
from hilfen import pdf_aus_text
from test_vorlagen import TEXT, VORLAGE
REPO = Path(__file__).parents[1]
VERK = {"name": "GM IT Solutions", "strasse": "Musterstraße 1", "plz": "16928", "ort": "Pritzwalk",
        "ust_id": "DE123456789", "iban": "DE02120300000000202051"}
@pytest.fixture
def k(tmp_path):
    for n in ("Eingang", "E-Rechnungen", "Originale", "Fehler", "prog/vorlagen"):
        (tmp_path / n).mkdir(parents=True)
    (tmp_path / "prog/vorlagen/test.yml").write_text(VORLAGE, encoding="utf-8")
    datei = tmp_path / "prog/konfig.json"
    datei.write_text("﻿" + json.dumps({"eingang": str(tmp_path / "Eingang"), "ausgabe": str(tmp_path / "E-Rechnungen"),
        "originale": str(tmp_path / "Originale"), "fehler": str(tmp_path / "Fehler"), "verkaeufer": VERK}), encoding="utf-8")
    k = lade_konfig(datei)
    pruefe_ordner(k)
    return k
def drucke(k, text=TEXT, name="rechnung.pdf"):
    (k.eingang / name).write_bytes(pdf_aus_text(text.splitlines()))
def namen(ordner):
    return sorted(p.name for p in ordner.iterdir())
def test_konfig(k):
    assert k.arbeit.name == "arbeit" and k.arbeit.is_dir()
    assert {"test-layout", "lexware-gm-it"} <= {v["name"] for v in k.vorlagen}
def test_konfig_ohne_iban(tmp_path, k):
    d = json.loads((k.arbeit.parent / "konfig.json").read_text(encoding="utf-8-sig"))
    del d["verkaeufer"]["iban"]
    (tmp_path / "k2.json").write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ValueError, match="iban"):
        lade_konfig(tmp_path / "k2.json")
def test_erfolg(k):
    drucke(k)
    assert schritt(k) == 1
    assert namen(k.eingang) == [] and namen(k.arbeit) == []
    assert namen(k.ausgabe) == ["RE9001.pdf", "RE9001.xml"]
    assert len(namen(k.originale)) == 1
    name, xml = get_xml_from_pdf((k.ausgabe / "RE9001.pdf").read_bytes(), check_xsd=True)
    assert xml == (k.ausgabe / "RE9001.xml").read_bytes()
def test_gleiche_nummer_zweimal(k):
    drucke(k)
    schritt(k)
    drucke(k)
    schritt(k)
    assert namen(k.ausgabe) == ["RE9001-2.pdf", "RE9001-2.xml", "RE9001.pdf", "RE9001.xml"]
def test_summenfehler(k):
    drucke(k, TEXT.replace("Brutto 238,00", "Brutto 239,00"))
    schritt(k)
    assert namen(k.ausgabe) == []
    f = namen(k.fehler)
    grund = next(n for n in f if n.endswith(".fehler.txt"))
    assert len(f) == 2
    assert "Brutto" in (k.fehler / grund).read_text(encoding="utf-8")
def test_unvollstaendig(k):
    (k.eingang / "rechnung.pdf").write_bytes(pdf_aus_text(TEXT.splitlines())[:-200])
    schritt(k)
    assert "unvollständig" in next(k.fehler.glob("*.fehler.txt")).read_text(encoding="utf-8")
def test_spooler_schreibt_noch(k, monkeypatch):
    drucke(k)
    echt = os.replace
    def gesperrt(a, b):
        if Path(a).parent == k.eingang:
            raise PermissionError(32, "Sharing violation")
        return echt(a, b)
    monkeypatch.setattr(os, "replace", gesperrt)
    assert schritt(k) == 0
    assert namen(k.eingang) == ["rechnung.pdf"]
def test_verknuepfung_abgelehnt(k, tmp_path):
    os.rmdir(k.ausgabe)
    (tmp_path / "anderswo").mkdir()
    os.symlink(tmp_path / "anderswo", k.ausgabe)
    with pytest.raises(ValueError, match="Verknüpfung"):
        pruefe_ordner(k)
def test_cli_version():
    aus = subprocess.run([sys.executable, "-m", "erechnung", "--version"], capture_output=True, text=True, check=True, cwd=REPO)
    assert aus.stdout.strip() == __version__
def test_cli_umwandeln(k, tmp_path):
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(pdf_aus_text(TEXT.splitlines()))
    aus = subprocess.run([sys.executable, "-m", "erechnung", "umwandeln", str(pdf), "--konfig", str(k.arbeit.parent / "konfig.json")],
                         capture_output=True, text=True, cwd=REPO)
    assert aus.returncode == 0, aus.stdout + aus.stderr
    assert (k.ausgabe / "RE9001.xml").exists() and pdf.exists()
```

- [ ] **Step 2: Tests scheitern** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests/test_ueberwachen.py -q`

- [ ] **Step 3: `erechnung/ueberwachen.py`**

```python
"""Ordnerüberwachung: Eingang → E-Rechnung oder Fehlerdatei (Spezifikation Abschnitt 3, 6, 7)."""
import json, logging, os, re, shutil, time, traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from .cii import bette_ein, erzeuge_cii
from .modell import Partei, summenabgleich
from .vorlagen import STANDARD, lade_vorlagen, lies_rechnung
log = logging.getLogger("erechnung")
@dataclass
class Konfig:
    eingang: Path
    ausgabe: Path
    originale: Path
    fehler: Path
    arbeit: Path
    verkaeufer: Partei
    vorlagen: list[dict]
def lade_konfig(datei: Path) -> Konfig:
    d = json.loads(datei.read_text(encoding="utf-8-sig"))  # PowerShell schreibt gern mit BOM
    v = Partei(**d["verkaeufer"])
    if not (v.name and (v.ust_id or v.steuernummer) and v.iban):
        raise ValueError("konfig.json: verkaeufer braucht name, ust_id oder steuernummer und iban")
    return Konfig(Path(d["eingang"]), Path(d["ausgabe"]), Path(d["originale"]), Path(d["fehler"]),
                  datei.parent / "arbeit", v, lade_vorlagen(STANDARD, datei.parent / "vorlagen"))
def pruefe_ordner(k: Konfig) -> None:
    """Keine Junction/Symlink, alles auf einem Laufwerk (os.replace), Arbeitsordner anlegen."""
    k.arbeit.mkdir(exist_ok=True)
    for o in (k.eingang, k.ausgabe, k.originale, k.fehler, k.arbeit):
        if o.is_symlink() or o.is_junction():
            raise ValueError(f"{o} ist eine Verknüpfung (Junction/Symlink)")
        if not o.is_dir():
            raise ValueError(f"{o} fehlt")
        if o.stat().st_dev != k.arbeit.stat().st_dev:
            raise ValueError(f"{o} liegt nicht auf dem Laufwerk des Arbeitsordners")
def _frei(ordner: Path, name: str, *endungen: str) -> str:
    # ponytail: Prüfen-dann-Verschieben ohne Sperre; nur der Überwacher schreibt in diese Ordner
    basis, n = name, 1
    while any((ordner / f"{basis}{e}").exists() for e in endungen):
        n += 1
        basis = f"{name}-{n}"
    return basis
def verarbeite(pdf: Path, k: Konfig) -> Path:
    if b"%%EOF" not in pdf.read_bytes()[-1024:]:
        raise ValueError("PDF unvollständig (kein %%EOF)")
    r = lies_rechnung(pdf, k.vorlagen, k.verkaeufer)
    xml = erzeuge_cii(r, summenabgleich(r))
    zugferd = bette_ein(pdf.read_bytes(), xml)
    tmp_pdf, tmp_xml = pdf.parent / (pdf.name + ".out.pdf"), pdf.parent / (pdf.name + ".out.xml")
    tmp_xml.write_bytes(xml)
    tmp_pdf.write_bytes(zugferd)
    basis = _frei(k.ausgabe, re.sub(r"[^A-Za-z0-9._-]", "_", r.nummer), ".pdf", ".xml")
    os.replace(tmp_xml, k.ausgabe / f"{basis}.xml")
    os.replace(tmp_pdf, k.ausgabe / f"{basis}.pdf")
    os.replace(pdf, k.originale / f"{_frei(k.originale, pdf.stem, '.pdf')}.pdf")
    log.info("%s → %s (Vorlage %s)", pdf.name, basis, r.vorlage)
    return k.ausgabe / f"{basis}.pdf"
def bearbeite(pdf: Path, k: Konfig) -> tuple[bool, str]:
    """Erfolg → (True, Pfad); jeder Fehler → Original + .fehler.txt nach Fehler, (False, Grund)."""
    try:
        return True, str(verarbeite(pdf, k))
    except Exception as e:
        grund = str(e) if isinstance(e, ValueError) else traceback.format_exc()
        log.warning("%s: %s", pdf.name, grund)
        basis = _frei(k.fehler, pdf.stem, ".pdf", ".fehler.txt")
        (k.fehler / f"{basis}.fehler.txt").write_text(f"{grund}\n", encoding="utf-8")
        os.replace(pdf, k.fehler / f"{basis}.pdf")
        return False, grund
def schritt(k: Konfig) -> int:
    for f in sorted(k.eingang.iterdir()):
        if f.is_file() and f.suffix.lower() == ".pdf":
            stempel = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            try:
                os.replace(f, k.arbeit / f"{stempel}-{f.name}")
            except (PermissionError, FileNotFoundError):
                continue  # Spooler schreibt noch (Freigabeverletzung) → nächster Takt
    n = 0
    for pdf in sorted(k.arbeit.glob("*.pdf")):
        if not pdf.name.endswith(".out.pdf"):
            bearbeite(pdf, k)
            n += 1
    return n
def ueberwache(k: Konfig, takt: float = 0.5) -> None:
    pruefe_ordner(k)
    for rest in list(k.arbeit.glob("*.out.*")):  # Reste eines abgebrochenen Laufs
        rest.unlink()
    log.info("Überwachung gestartet: %s", k.eingang)
    while True:
        try:
            schritt(k)
        except Exception:
            log.exception("Fehler im Überwachungsschritt")
        time.sleep(takt)
def umwandeln(pdf: Path, k: Konfig) -> tuple[bool, str]:
    pruefe_ordner(k)
    kopie = k.arbeit / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{pdf.name}"
    shutil.copyfile(pdf, kopie)
    return bearbeite(kopie, k)
```

`Path.is_junction()` gibt es ab Python 3.12 (Ziel 3.14: passt).

- [ ] **Step 4: `erechnung/__main__.py` ersetzen**

```python
import argparse, logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from . import __version__
def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="erechnung")
    p.add_argument("--version", action="store_true", help="Version ausgeben (lädt alle Abhängigkeiten, Probe für gm-update)")
    sub = p.add_subparsers(dest="befehl")
    u = sub.add_parser("ueberwachen")
    u.add_argument("--konfig", type=Path, required=True)
    w = sub.add_parser("umwandeln")
    w.add_argument("pdf", type=Path)
    w.add_argument("--konfig", type=Path, required=True)
    a = p.parse_args(argv)
    if a.version:
        import facturx, lxml, pdfplumber, yaml  # noqa: F401 – Probe: Paket vollständig?
        from . import ueberwachen  # noqa: F401
        print(__version__)
        return 0
    if not a.befehl:
        p.print_usage()
        return 2
    from .ueberwachen import lade_konfig, ueberwache, umwandeln
    h = RotatingFileHandler(a.konfig.parent / "erechnung.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[h], format="%(asctime)s %(levelname)s %(message)s")
    k = lade_konfig(a.konfig)
    if a.befehl == "ueberwachen":
        ueberwache(k)  # läuft dauerhaft; unter pythonw.exe gibt es kein stdout
        return 1
    ok, text = umwandeln(a.pdf, k)
    print(text)
    return 0 if ok else 1
if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q`

- [ ] **Step 6: Commit und Push**

```bash
git -C /root/erechnung-konverter add erechnung/ueberwachen.py erechnung/__main__.py tests/test_ueberwachen.py
git -C /root/erechnung-konverter commit -m "Überwacher, Konfiguration und CLI" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
