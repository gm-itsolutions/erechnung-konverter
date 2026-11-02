"""Probelauf, Aktivieren, Verwalten und Export angelernter Vorlagen (docs/lernmodus/spezifikation.md 4, 7.3, 7.4).
`aktivieren`/`deaktivieren`/`reaktivieren`/`loeschen` laufen erhöht (UAC) und vertrauen dem Entwurf nicht."""
import hashlib
import json
import os
from datetime import date, datetime
from pathlib import Path
import yaml
from ..bereiche import GERAETE, NAME, positionen_aus_bereichen, pruefe_bereichsvorlage, rechnung_aus_bereichen, woerter_aus_pdf
from ..cii import erzeuge_cii
from ..modell import de, summenabgleich
from ..ueberwachen import ANGELERNT, lade_konfig
from ..vorlagen import MAX_BYTES, STANDARD, _lade_datei, lade_vorlagen, lies_rechnung

MIN_MUSTER = 2
def _konfig(konfig: Path, arbeit: Path):            # in Tests ersetzbar
    return lade_konfig(konfig, arbeit=arbeit)
def _muster(entwurf: Path) -> list[Path]:
    return sorted((entwurf / "muster").glob("m*.pdf"), key=lambda p: int(p.stem[1:]))
def _mitgeliefert(k) -> set[str]:
    """Namen der mitgelieferten und der Zusatz-Vorlagen (Programmordner `vorlagen\\`, nicht `angelernt`)."""
    zusatz = [o for o in k.vorlagen_ordner if o.name != ANGELERNT]
    return {v["name"] for v in lade_vorlagen(STANDARD, *zusatz, tolerant=True)}
def _ein_muster(pdf: Path, v: dict, andere: list[dict], k) -> dict:
    erg = {"id": pdf.stem, "ok": False, "fehler": None, "werte": {}, "positionen": [], "ignoriert": [], "spur": {}, "mustang": None}
    gelesen = {}                                    # Wortlage der Lesart, die lies_rechnung zuletzt geprüft hat
    def ocr(p):
        g = iter(k.ocr(p))
        try:
            for lesart in g:
                gelesen["seiten"] = lesart[2] if len(lesart) > 2 else None
                yield lesart
        finally:
            getattr(g, "close", lambda: None)()
    try:
        # derselbe Weg wie der Überwacher: Vorlagensuche (Konflikt „mehrere Vorlagen“), Lesarten der Texterkennung
        r = lies_rechnung(pdf, [*andere, v], k.verkaeufer, ocr=ocr if k.ocr else None)
        if r.vorlage != v["name"]:
            raise ValueError(f"Muster passt zur Vorlage {r.vorlage}, nicht zu dieser")
        mit_ocr = bool(r.ocr_text)
        seiten = gelesen.get("seiten") if mit_ocr else woerter_aus_pdf(pdf)
        r = rechnung_aus_bereichen(seiten, v, k.verkaeufer, ocr=mit_ocr, spur=erg["spur"])   # noch einmal, für die Rahmen
        erg["werte"] = {"nummer": r.nummer, "datum": f"{r.datum:%d.%m.%Y}", "faellig": f"{r.faellig:%d.%m.%Y}" if r.faellig else "",
                        "kaeufer": " / ".join(filter(None, (r.kaeufer.name, r.kaeufer.strasse, f"{r.kaeufer.plz} {r.kaeufer.ort}".strip()))),
                        "summe_netto": de(r.summe_netto), "summe_brutto": de(r.summe_brutto),
                        "steuern": {str(s): de(b) for s, b in r.steuern.items()}}
        erg["positionen"] = [[p.nr, p.bezeichnung, str(p.menge), p.einheit, de(p.einzelpreis), str(p.ust_satz), de(p.netto)]
                             for p in r.positionen]
        erg["ignoriert"] = positionen_aus_bereichen(seiten, v, mit_ocr)[1]
        xml = erzeuge_cii(r, summenabgleich(r))
        if not k.pruefe:
            raise ValueError("Mustang-Prüfung nicht verfügbar")
        datei = k.arbeit / f"probe-{pdf.stem}.xml"
        datei.write_bytes(xml)
        try:
            erg["mustang"] = k.pruefe(datei)
        finally:
            datei.unlink(missing_ok=True)
        erg["ok"] = True
    except (ValueError, OSError) as e:             # OSError: Muster oder Arbeitsordner nicht lesbar
        erg["fehler"] = str(e)
    return erg
def _vorlage(entwurf: Path) -> dict:
    return json.loads((entwurf / "vorlage.json").read_text(encoding="utf-8"))
def probelauf(entwurf: Path, k, v: dict | None = None) -> dict:
    """`v` übergibt `aktivieren`: geprüft wird genau die Fassung, die danach geschrieben wird."""
    try:
        v = _vorlage(entwurf) if v is None else v
        pruefe_bereichsvorlage(v)
        if v["name"] in GERAETE:
            raise ValueError(f"Name {v['name']} ist unter Windows reserviert")
        if v["name"] in _mitgeliefert(k):
            raise ValueError(f"Name {v['name']} ist mitgeliefert, bitte anderen Namen wählen")
    except ValueError as e:
        return {"vorlage_fehler": str(e), "muster": [], "bereit": False}
    k.arbeit.mkdir(parents=True, exist_ok=True)     # Texterkennung und Mustang arbeiten dort
    andere = [x for x in k.vorlagen if x["name"] != v["name"]]   # gleichnamige aktive wird ersetzt (Spec 7.4)
    muster = [_ein_muster(p, v, andere, k) for p in _muster(entwurf)]
    return {"vorlage_fehler": None, "muster": muster, "bereit": len(muster) >= MIN_MUSTER and all(m["ok"] for m in muster)}

def _stempel() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
def _protokoll(angelernt: Path, aktion: str, name: str, benutzer: str, datei: Path | None = None, muster: int = 0) -> None:
    admin = f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}"
    teile = [datetime.now().isoformat(timespec="seconds"), f"benutzer={benutzer}", f"admin={admin}", aktion, name]
    if datei:
        teile.append(f"sha256={hashlib.sha256(datei.read_bytes()).hexdigest()}")
    teile.append(f"muster={muster}")
    with open(angelernt / "protokoll.txt", "a", encoding="utf-8") as f:
        f.write("\t".join(teile) + "\n")
def _ordner(konfig: Path) -> Path:
    angelernt = konfig.parent / "vorlagen" / ANGELERNT
    (angelernt / "deaktiviert").mkdir(parents=True, exist_ok=True)
    return angelernt
def _weg(datei: Path, angelernt: Path, name: str) -> None:
    """Vorhandene Datei mit Stempel nach deaktiviert/ (ersetzte oder verdrängte Fassung)."""
    if datei.exists():
        os.replace(datei, angelernt / "deaktiviert" / f"{name}-{_stempel()}.yml")
def aktivieren(entwurf: Path, konfig: Path, benutzer: str, arbeit: Path | None = None) -> dict:
    try:
        angelernt = _ordner(konfig)
        k = _konfig(konfig, arbeit or konfig.parent / "arbeit")
        v = _vorlage(entwurf)                      # einmal lesen: der Entwurf kann sich während der Prüfung ändern
        p = probelauf(entwurf, k, v)               # Schema, Namen, alle Muster, Konflikte, Mustang
        if p["vorlage_fehler"]:
            return {"ok": False, "meldung": p["vorlage_fehler"]}
        if not p["bereit"]:
            fehler = next((f"{m['id']}: {m['fehler']}" for m in p["muster"] if m["fehler"]), None)
            return {"ok": False, "meldung": fehler or f"mindestens {MIN_MUSTER} fehlerfreie Muster nötig"}
        v["angelernt"] = {"am": date.today().isoformat(), "muster": len(p["muster"])}
        text = yaml.safe_dump(v, allow_unicode=True, sort_keys=False)
        if len(text.encode("utf-8")) > MAX_BYTES:
            return {"ok": False, "meldung": f"Vorlage zu groß (höchstens {MAX_BYTES} Byte)"}
        pruefe_bereichsvorlage(yaml.safe_load(text))
        name = v["name"]
        ziel = angelernt / f"{name}.yml"
        tmp = angelernt / f"{name}.yml.tmp"
        tmp.write_text(text, encoding="utf-8")
        _weg(ziel, angelernt, name)
        os.replace(tmp, ziel)
        _protokoll(angelernt, "aktiviert", name, benutzer, ziel, len(p["muster"]))
        return {"ok": True, "meldung": f"Vorlage {name} aktiviert"}
    except (ValueError, OSError) as e:
        return {"ok": False, "meldung": str(e)}
def _verwalte(name, konfig: Path, benutzer: str, aktion: str) -> dict:
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in GERAETE:
        return {"ok": False, "meldung": "Name ungültig: 2–40 Zeichen a–z, 0–9, Bindestrich"}
    try:
        angelernt = _ordner(konfig)
        aktiv, aus = angelernt / f"{name}.yml", angelernt / "deaktiviert" / f"{name}.yml"
        if aktion == "deaktiviert":
            if not aktiv.exists():
                return {"ok": False, "meldung": f"Vorlage {name} nicht gefunden"}
            _weg(aus, angelernt, name)
            os.replace(aktiv, aus)
            datei = aus
        elif aktion == "reaktiviert":
            if not aus.exists():
                return {"ok": False, "meldung": f"Vorlage {name} nicht gefunden"}
            if aktiv.exists():
                return {"ok": False, "meldung": f"Vorlage {name} ist schon aktiv"}
            _lade_datei(aus)                         # Größe, YAML, Schema
            os.replace(aus, aktiv)
            datei = aktiv
        else:                                        # gelöscht: aktive, sonst deaktivierte; gestempelte Altstände bleiben
            datei = aktiv if aktiv.exists() else aus
            if not datei.exists():
                return {"ok": False, "meldung": f"Vorlage {name} nicht gefunden"}
            _protokoll(angelernt, aktion, name, benutzer, datei)   # vorher, solange die Prüfsumme lesbar ist
            datei.unlink()
            return {"ok": True, "meldung": f"Vorlage {name} gelöscht"}
        _protokoll(angelernt, aktion, name, benutzer, datei)
        return {"ok": True, "meldung": f"Vorlage {name} {aktion}"}
    except (ValueError, OSError) as e:
        return {"ok": False, "meldung": str(e)}
def deaktivieren(name, konfig: Path, benutzer: str) -> dict:
    return _verwalte(name, konfig, benutzer, "deaktiviert")
def reaktivieren(name, konfig: Path, benutzer: str) -> dict:
    return _verwalte(name, konfig, benutzer, "reaktiviert")
def loeschen(name, konfig: Path, benutzer: str) -> dict:
    return _verwalte(name, konfig, benutzer, "gelöscht")

def exportieren(entwurf: Path, ziel: Path) -> Path:
    """Nur die Vorlage als YAML (F2): keine Muster-PDFs, keine Seitenbilder, keine Wortlisten."""
    v = pruefe_bereichsvorlage(_vorlage(entwurf))
    datei = ziel / f"erechnung-vorlage-{v['name']}-{date.today().isoformat()}.yml"
    datei.write_text(yaml.safe_dump(v, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return datei
