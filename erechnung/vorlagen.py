"""Vorlagen je Layout (YAML, angelehnt an invoice2data) → Rechnung. Spezifikation Abschnitt 5."""
import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
import yaml
from .modell import Partei, Position, Rechnung, betrag, datum
STANDARD = Path(__file__).parent / "vorlagen"
PFLICHT = ("nummer", "datum", "summe_netto", "summe_brutto")
class VorlagenFehler(ValueError):
    pass
def pdf_text(pdf: Path, layout: bool = False) -> str:
    with pdfplumber.open(pdf) as d:
        return "\n".join(s.extract_text(layout=layout) or "" for s in d.pages)
def _pruefe(v: dict, datei: Path) -> dict:
    try:
        assert v.get("name") and v.get("schluesselwoerter"), "name/schluesselwoerter fehlen"
        assert all(f in v.get("felder", {}) for f in PFLICHT), f"felder brauchen {', '.join(PFLICHT)}"
        assert all(k in v.get("positionen", {}) for k in ("start", "ende", "zeile")), "positionen: start/ende/zeile"
        muster = [*v["felder"].values(), v.get("steuern"), v.get("kaeufer"),
                  *(v["positionen"][k] for k in ("start", "ende", "zeile")), *v["positionen"].get("ignorieren", [])]
        for m in muster:
            if m:
                re.compile(m)
    except (AssertionError, re.error) as e:
        raise VorlagenFehler(f"Vorlage {datei.name}: {e}") from None
    return v
def lade_vorlagen(*ordner: Path) -> list[dict]:
    vorlagen = []
    for o in ordner:
        if o.is_dir():
            for datei in sorted(o.glob("*.yml")):
                vorlagen.append(_pruefe(yaml.safe_load(datei.read_text(encoding="utf-8")) or {}, datei))
    return vorlagen
def finde_vorlage(text: str, vorlagen: list[dict]) -> dict:
    passend = [v for v in vorlagen if all(k in text for k in v["schluesselwoerter"])]
    if not passend:
        raise VorlagenFehler("keine Vorlage passt zu diesem Layout")
    if len(passend) > 1:
        raise VorlagenFehler("mehrere Vorlagen: " + ", ".join(v["name"] for v in passend))
    return passend[0]
def _feld(text: str, v: dict, name: str) -> str | None:
    muster = v["felder"].get(name)
    m = re.search(muster, text, re.MULTILINE) if muster else None
    if not m and name in PFLICHT:
        raise VorlagenFehler(f"Feld {name} nicht gefunden (Vorlage {v['name']})")
    return m.group(1).strip() if m else None
def _satz(t: str) -> Decimal:
    return Decimal(t.replace(",", ".").replace("%", "").strip())
def _positionen(text: str, v: dict) -> list[Position]:
    p = v["positionen"]
    zeilen = text.splitlines()
    try:
        von = next(i for i, z in enumerate(zeilen) if re.search(p["start"], z))
        bis = max(i for i, z in enumerate(zeilen) if re.search(p["ende"], z))
    except (StopIteration, ValueError):
        raise VorlagenFehler(f"Positionsblock nicht gefunden (Vorlage {v['name']})") from None
    ergebnis: list[Position] = []
    for z in zeilen[von + 1:bis]:
        if not z.strip() or any(re.search(m, z) for m in p.get("ignorieren", [])) or re.search(p["start"], z):
            continue
        m = re.search(p["zeile"], z)
        if m:
            g = m.groupdict()
            ergebnis.append(Position(
                nr=g.get("nr") or str(len(ergebnis) + 1), bezeichnung=g["bezeichnung"].strip(),
                menge=betrag(g["menge"]), einheit=v.get("einheiten", {}).get((g.get("einheit") or "").strip(), "C62"),
                einzelpreis=betrag(g["einzelpreis"]), netto=betrag(g["netto"]),
                ust_satz=_satz(g["ust_satz"]) if g.get("ust_satz") else Decimal(str(p.get("ust_satz", 19)))))
        elif ergebnis:
            ergebnis[-1].bezeichnung += " " + z.strip()
    return ergebnis
def rechnung_aus_text(text: str, vorlage: dict, verkaeufer: Partei) -> Rechnung:
    v = vorlage
    kaeufer = Partei("")
    if v.get("kaeufer"):
        m = re.search(v["kaeufer"], text, re.MULTILINE)
        if not m:
            raise VorlagenFehler(f"Käufer nicht gefunden (Vorlage {v['name']})")
        kaeufer = Partei(**{k: w.strip() for k, w in m.groupdict().items() if w})
    steuern = {_satz(m["satz"]): betrag(m["betrag"]) for m in re.finditer(v["steuern"], text, re.MULTILINE)} if v.get("steuern") else {}
    opt = lambda n: _feld(text, v, n)
    return Rechnung(
        nummer=opt("nummer"), datum=datum(opt("datum")), verkaeufer=verkaeufer, kaeufer=kaeufer,
        positionen=_positionen(text, v), summe_netto=betrag(opt("summe_netto")), summe_brutto=betrag(opt("summe_brutto")),
        summe_ust=betrag(opt("summe_ust")) if opt("summe_ust") else None, steuern=steuern,
        leistungsdatum=datum(opt("leistungsdatum")) if opt("leistungsdatum") else None,
        faellig=datum(opt("faellig")) if opt("faellig") else None, vorlage=v["name"])
def lies_rechnung(pdf: Path, vorlagen: list[dict], verkaeufer: Partei) -> Rechnung:
    text = pdf_text(pdf)
    if not text.strip():
        raise VorlagenFehler("kein Text im PDF (als Bild gedruckt?)")
    v = finde_vorlage(text, vorlagen)
    if v.get("layout"):
        text = pdf_text(pdf, layout=True)
    return rechnung_aus_text(text, v, verkaeufer)
