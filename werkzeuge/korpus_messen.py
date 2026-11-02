"""Messwerkzeug: liest alle PDFs mit *.soll.json unter den Ordnern und vergleicht je Feld mit dem Soll.

Verfahren: `vorlage` (heutiger Weg: lies_rechnung + Summenabgleich) und `generisch`
(erechnung.generisch.vorschlag_aus_pdf, falls das Modul existiert).
Kennzahl „bestätigt, aber falsch“: Summenabgleich ok, aber ein verglichenes Feld weicht vom Soll ab. Muss 0 sein.

Aufruf:  /root/.venvs/erechnung/bin/python werkzeuge/korpus_messen.py ORDNER... [--verfahren vorlage]
         [--json DATEI] [--jobs N] [--ohne-ocr]
"""
import argparse, json, os, sys, tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # erechnung auch beim Start als Skript
FELDER = ("nummer", "datum", "netto", "ust", "brutto", "kaeufer", "pos_anzahl", "pos_netto")
KERN = ("nummer", "datum", "netto", "brutto")
TESTDATEN = Path("/root/erechnung-testdaten")


def dec(x) -> Decimal | None:
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None


def vergleiche(soll: dict, gelesen: dict | None) -> dict[str, bool | None]:
    """Je Feld True (richtig), False (falsch oder nicht gelesen), None (im Soll nicht vorhanden → nicht bewertbar).
    `gelesen`: nummer, datum (date), netto, brutto (Decimal), steuern {Decimal: Decimal}, kaeufer (str),
    positionen [Decimal netto]; None = nichts gelesen. Beträge und Sätze werden numerisch verglichen."""
    g = gelesen or {}
    erg: dict[str, bool | None] = {}
    erg["nummer"] = g.get("nummer") == soll["nummer"] if soll.get("nummer") else None
    erg["datum"] = (g.get("datum") is not None and g["datum"].isoformat() == soll["datum"]) if soll.get("datum") else None
    for f, k in (("netto", "netto"), ("brutto", "brutto")):
        erg[f] = (g.get(k) is not None and g[k] == dec(soll[k])) if soll.get(k) is not None else None
    if soll.get("steuern"):
        s = {dec(k): dec(v) for k, v in soll["steuern"].items()}
        erg["ust"] = g.get("steuern") is not None and {k: v for k, v in g["steuern"].items()} == s
    else:
        erg["ust"] = None
    name = (soll.get("kaeufer") or {}).get("name")
    norm = lambda t: " ".join((t or "").casefold().split())
    erg["kaeufer"] = norm(g.get("kaeufer")) == norm(name) if name else None
    if soll.get("positionen"):
        p = g.get("positionen")
        erg["pos_anzahl"] = p is not None and len(p) == len(soll["positionen"])
        erg["pos_netto"] = p is not None and sorted(p) == sorted(dec(x["netto"]) for x in soll["positionen"])
    else:
        erg["pos_anzahl"] = erg["pos_netto"] = None
    return erg


def _aus_rechnung(r) -> dict:
    return dict(nummer=r.nummer, datum=r.datum, netto=r.summe_netto, brutto=r.summe_brutto, steuern=r.steuern,
                kaeufer=r.kaeufer.name, positionen=[p.netto for p in r.positionen])


def _aus_vorschlag(v) -> dict:
    return dict(nummer=v.nummer, datum=v.datum, netto=v.summe_netto, brutto=v.summe_brutto, steuern=v.steuern,
                kaeufer=v.kaeufer.name if v.kaeufer else None, positionen=[p.netto for p in v.positionen or []])


def generisch_verfuegbar() -> bool:
    try:
        from erechnung import generisch  # noqa: F401
        return True
    except ModuleNotFoundError as e:
        if e.name == "erechnung.generisch":
            return False
        raise


def _ocr(mit_ocr: bool, arbeit: Path):
    """(Lesarten-Funktion | None). Tessdata aus den Testdaten, wenn vorhanden."""
    from erechnung import ocr
    aufruf = ocr.tesseract() if mit_ocr else None
    if not aufruf:
        return None
    if (TESTDATEN / "tessdata" / "deu.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(TESTDATEN / "tessdata")
    return partial(ocr.erkenne, arbeit=arbeit, aufruf=aufruf)


def messe(sollpfad: str, verfahren: str, mit_ocr: bool) -> dict:
    """Eine Rechnung messen. status: ok | fehler | uebersprungen."""
    from erechnung.modell import Partei
    VERKAEUFER = Partei("GM IT Solutions", "Musterstraße 1", "16928", "Pritzwalk")
    sollpfad = Path(sollpfad)
    soll = json.loads(sollpfad.read_text(encoding="utf-8"))
    pdf = sollpfad.with_name(soll["datei"])
    erg = dict(datei=pdf.name, ordner=pdf.parent.name, layout=soll.get("layout", "korpus"), status="ok", meldung="",
               bestaetigt=False, bild=bool(soll.get("bild_pdf")), felder={})
    with tempfile.TemporaryDirectory(prefix="messen-") as arbeit:
        _lies(erg, verfahren, mit_ocr, arbeit, pdf, VERKAEUFER)
    return _vergleiche(erg, soll)


def _lies(erg, verfahren, mit_ocr, arbeit, pdf, VERKAEUFER):
    from erechnung import modell, vorlagen
    try:
        if verfahren == "vorlage":
            ocr = _ocr(mit_ocr, Path(arbeit))
            if erg["bild"] and ocr is None:
                erg["status"] = "uebersprungen"
                erg["meldung"] = "Bild-PDF, keine Texterkennung"
            else:
                r = vorlagen.lies_rechnung(pdf, vorlagen.lade_vorlagen(vorlagen.STANDARD), VERKAEUFER, ocr)
                erg["gelesen"] = _aus_rechnung(r)
                try:
                    modell.summenabgleich(r)
                    erg["bestaetigt"] = True
                except modell.SummenFehler as e:
                    erg["meldung"] = f"Summenabgleich: {e}"
        else:
            from erechnung import generisch
            ocr = _ocr(mit_ocr, Path(arbeit))
            if erg["bild"] and ocr is None:
                erg["status"] = "uebersprungen"
                erg["meldung"] = "Bild-PDF, keine Texterkennung"
            else:
                v = generisch.vorschlag_aus_pdf(pdf, ocr)
                erg["gelesen"] = _aus_vorschlag(v)
                erg["bestaetigt"] = bool(v.bestaetigt)
                erg["meldung"] = v.grund or ""
    except Exception as e:  # jede Rechnung einzeln; ein Fehler gilt als „nichts gelesen“
        erg["status"], erg["meldung"] = "fehler", f"{type(e).__name__}: {e}"[:300]


def _vergleiche(erg: dict, soll: dict) -> dict:
    gelesen = erg.pop("gelesen", None)
    if erg["status"] != "uebersprungen":
        try:
            erg["felder"] = vergleiche(soll, gelesen)
        except Exception as e:  # z. B. None in Positionen: gilt als „nichts richtig gelesen“
            erg["status"], erg["bestaetigt"] = "fehler", False
            erg["meldung"] = f"Vergleich: {type(e).__name__}: {e}"[:300]
            erg["felder"] = {f: False for f in FELDER}
    return erg


def lexware_pruefung(ordner: Path = TESTDATEN) -> list[dict]:
    """Die echten Lexware-Rechnungen RE*.pdf: Vorlage muss lesen, Summenabgleich bestehen, Nummer/Netto/Brutto/
    Positionen zur RE*.lexware.xml passen."""
    from erechnung import modell, vorlagen
    from erechnung.betraege import betraege
    from erechnung.modell import Partei
    erg = []
    for pdf in sorted(ordner.glob("RE*.pdf")):
        xml = pdf.with_suffix(".lexware.xml")
        try:
            r = vorlagen.lies_rechnung(pdf, vorlagen.lade_vorlagen(vorlagen.STANDARD), Partei("GM IT Solutions"))
            modell.summenabgleich(r)
            ok, meldung = True, ""
            if xml.exists():
                b = betraege(xml.read_bytes())
                ok = (r.nummer, r.summe_netto, r.summe_brutto, [p.netto for p in r.positionen]) == \
                     (b["nummer"], b["netto"], b["brutto"], b["positionen"])
                meldung = "" if ok else "Werte weichen von der Lexware-XML ab"
        except Exception as e:
            ok, meldung = False, f"{type(e).__name__}: {e}"[:200]
        erg.append(dict(datei=pdf.name, ok=ok, meldung=meldung))
    return erg


def kennzahlen(ergebnisse: list[dict]) -> dict:
    """Trefferquoten je Feld sowie vollständig richtig / bestätigt / bestätigt aber falsch (nur nicht übersprungene)."""
    e = [x for x in ergebnisse if x["status"] != "uebersprungen"]
    felder = {}
    for f in FELDER:
        bew = [x["felder"][f] for x in e if x["felder"][f] is not None]
        felder[f] = dict(richtig=sum(bew), bewertbar=len(bew), nicht_bewertbar=len(e) - len(bew))
    ok = lambda x: all(v is not False for v in x["felder"].values())
    kern = lambda x: all(x["felder"][f] is not False for f in KERN)
    return dict(anzahl=len(ergebnisse), uebersprungen=len(ergebnisse) - len(e), gemessen=len(e), felder=felder,
                vollstaendig_richtig=sum(ok(x) for x in e), bestaetigt=sum(x["bestaetigt"] for x in e),
                bestaetigt_aber_falsch=sum(x["bestaetigt"] and not ok(x) for x in e),
                bestaetigt_kern_falsch=sum(x["bestaetigt"] and not kern(x) for x in e))


def tabelle(k: dict) -> str:
    z = ["| Feld | richtig | bewertbar | Quote | nicht bewertbar |", "|---|---:|---:|---:|---:|"]
    for f, d in k["felder"].items():
        q = f"{100 * d['richtig'] / d['bewertbar']:.1f} %" if d["bewertbar"] else "-"
        z.append(f"| {f} | {d['richtig']} | {d['bewertbar']} | {q} | {d['nicht_bewertbar']} |")
    z.append("")
    z.append(f"gemessen {k['gemessen']} von {k['anzahl']} (übersprungen {k['uebersprungen']}); "
             f"vollständig richtig {k['vollstaendig_richtig']}; bestätigt {k['bestaetigt']}; "
             f"**bestätigt, aber falsch: {k['bestaetigt_aber_falsch']}**; "
             f"**bestätigt, Kern falsch (Nummer/Datum/Netto/Brutto): {k['bestaetigt_kern_falsch']}**")
    return "\n".join(z)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("ordner", nargs="+", type=Path)
    p.add_argument("--verfahren", choices=("vorlage", "generisch", "beide"), default="vorlage")
    p.add_argument("--json", type=Path, help="JSON-Bericht (außerhalb des Repos ablegen)")
    p.add_argument("--jobs", type=int, default=os.cpu_count())
    p.add_argument("--lexware", action="store_true", help="zusätzlich die echten Lexware-Rechnungen prüfen")
    p.add_argument("--ohne-ocr", action="store_true")
    a = p.parse_args(argv)
    pdfs = sorted(str(s) for o in a.ordner for s in o.rglob("*.soll.json"))
    verfahren = ["vorlage", "generisch"] if a.verfahren == "beide" else [a.verfahren]
    bericht = {}
    for v in verfahren:
        if v == "generisch" and not generisch_verfuegbar():
            print("Verfahren generisch nicht verfügbar: erechnung.generisch fehlt (Task 3).", file=sys.stderr)
            bericht[v] = None
            continue
        with ProcessPoolExecutor(a.jobs) as ex:
            erg = list(ex.map(partial(messe, verfahren=v, mit_ocr=not a.ohne_ocr), pdfs, chunksize=2))
        gruppen = defaultdict(list)
        for x in erg:
            gruppen[x["ordner"]].append(x)
        bericht[v] = dict(gesamt=kennzahlen(erg), je_ordner={o: kennzahlen(g) for o, g in gruppen.items()},
                          je_layout={l: kennzahlen(g) for l, g in
                                     ((l, [x for x in erg if x["layout"] == l]) for l in sorted({x["layout"] for x in erg}))},
                          ergebnisse=erg)
        print(f"== Verfahren {v}: {len(pdfs)} Rechnungen ==")
        for o, k in bericht[v]["je_ordner"].items():
            print(f"\n-- {o}\n{tabelle(k)}")
        print("\n-- je Layout: gemessen / vollständig richtig / bestätigt / bestätigt, aber falsch / Kern falsch")
        for l, k in bericht[v]["je_layout"].items():
            print(f"{l:8} {k['gemessen']:4} {k['vollstaendig_richtig']:4} {k['bestaetigt']:4} {k['bestaetigt_aber_falsch']:4} {k['bestaetigt_kern_falsch']:4}")
    if a.lexware:
        bericht["lexware"] = lexware_pruefung()
        for x in bericht["lexware"]:
            print(f"Lexware {x['datei']}: {'ok' if x['ok'] else 'FEHLER ' + x['meldung']}")
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(bericht, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
