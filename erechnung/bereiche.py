"""Angelernte Vorlagen: Felder per Rahmen und Anker, keine Regex (docs/lernmodus/spezifikation.md 5, 6)."""
import re
FORMAT = 1
PFLICHT_FELDER = ("nummer", "datum", "summe_netto", "summe_brutto", "kaeufer")
FELDER = (*PFLICHT_FELDER, "nummer_kontrolle", "leistungsdatum", "faellig", "zahlungsziel_tage", "summe_ust", "nachlass")
SPALTEN = ("nr", "bezeichnung", "menge", "einheit", "menge_einheit", "einzelpreis", "ust_satz", "netto", "ignorieren")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,39}")
class BereichsFehler(ValueError):
    pass
def _ja(bedingung, meldung: str) -> None:
    if not bedingung:
        raise BereichsFehler(meldung)
def _schluessel(d, erlaubt: set, wo: str) -> None:
    _ja(isinstance(d, dict), f"{wo}: Abschnitt fehlt")
    fremd = set(d) - erlaubt
    _ja(not fremd, f"{wo}: unbekannt: {', '.join(sorted(map(str, fremd)))}")
def _zahl(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1
def _rahmen(r, wo: str) -> None:
    _ja(isinstance(r, list) and len(r) == 4 and all(map(_zahl, r)) and r[0] < r[2] and r[1] < r[3],
        f"{wo}: rahmen braucht [x0, y0, x1, y1] in 0..1 mit x0 < x1, y0 < y1")
def _text(t, wo: str, mini=1, maxi=80) -> None:
    _ja(isinstance(t, str) and mini <= len(t) <= maxi, f"{wo}: Text mit {mini}–{maxi} Zeichen nötig")
def _anker(a, wo: str, platzhalter: bool = False) -> None:
    _schluessel(a, {"text", "rahmen"}, f"{wo}.anker")
    _text(a.get("text"), f"{wo}.anker")
    _ja(a["text"].count("{satz}") <= (1 if platzhalter else 0), f"{wo}.anker: {{satz}} nicht erlaubt")
    _rahmen(a.get("rahmen"), f"{wo}.anker")
def _satz(x, wo: str) -> None:
    _ja(isinstance(x, (int, float)) and not isinstance(x, bool) and 0 < x <= 30, f"{wo}: ust_satz/satz muss 0 < x ≤ 30 sein")
def _feld(f, wo: str) -> None:
    _schluessel(f, {"seite", "rahmen", "anker"}, wo)
    _ja(f.get("seite") in ("erste", "letzte"), f"{wo}: seite muss erste oder letzte sein")
    _rahmen(f.get("rahmen"), wo)
    if "anker" in f:
        _anker(f["anker"], wo)
def pruefe_bereichsvorlage(v: dict) -> dict:
    _schluessel(v, {"name", "art", "format", "schluesselwoerter", "angelernt", "felder", "steuern", "positionen", "einheiten"}, "Vorlage")
    _ja(v.get("art") == "bereiche", "art muss bereiche sein")
    _ja(isinstance(v.get("name"), str) and NAME.fullmatch(v["name"]), "name: nur a-z, 0-9, -, 2–40 Zeichen")
    _ja(v.get("format") == FORMAT, f"format muss {FORMAT} sein")
    sw = v.get("schluesselwoerter")
    _ja(isinstance(sw, list) and 1 <= len(sw) <= 5, "schluesselwoerter: 1–5 Texte")
    for s in sw:
        _text(s, "schluesselwoerter", 3, 80)
    if "angelernt" in v:
        _schluessel(v["angelernt"], {"am", "muster"}, "angelernt")
    felder = v.get("felder")
    _schluessel(felder, set(FELDER), "felder")
    for n in PFLICHT_FELDER:
        _ja(n in felder, f"felder: {n} fehlt")
    for n, f in felder.items():
        _feld(f, f"felder.{n}")
    if "steuern" in v:
        s = v["steuern"]
        _schluessel(s, {"seite", "anker", "rahmen", "satz"}, "steuern")
        _ja("anker" in s, "steuern: anker fehlt")
        _feld({k: s[k] for k in ("seite", "rahmen") if k in s}, "steuern")
        _anker(s["anker"], "steuern", platzhalter=True)
        if "{satz}" not in s["anker"]["text"]:
            _ja("satz" in s, "steuern: ohne {satz} im Anker ist satz Pflicht")
            _satz(s["satz"], "steuern")
    p = v.get("positionen")
    _schluessel(p, {"kopf", "ende", "unten", "links", "spalten", "ust_satz"}, "positionen")
    _anker(p.get("kopf"), "positionen.kopf")
    if "ende" in p:
        _anker(p["ende"], "positionen.ende")
    _ja(_zahl(p.get("unten")) and _zahl(p.get("links")), "positionen: unten und links in 0..1")
    sp = p.get("spalten")
    _ja(isinstance(sp, list) and 2 <= len(sp) <= 12, "positionen.spalten: 2–12 Spalten")
    for s in sp:
        _schluessel(s, {"bis", "art"}, "positionen.spalten")
        _ja(s.get("art") in SPALTEN, f"positionen.spalten: art {s.get('art')!r} unbekannt")
        _ja(_zahl(s.get("bis")), "positionen.spalten: bis in 0..1")
    grenzen = [p["links"], *(s["bis"] for s in sp)]
    _ja(all(a < b for a, b in zip(grenzen, grenzen[1:])), "positionen.spalten: bis streng steigend, links davor")
    arten = [s["art"] for s in sp]
    _ja(arten.count("bezeichnung") == 1, "positionen.spalten: genau eine bezeichnung")
    _ja(arten.count("netto") == 1, "positionen.spalten: genau eine netto")
    _ja(arten.count("menge") + arten.count("menge_einheit") <= 1, "positionen.spalten: höchstens eine menge/menge_einheit")
    if "ust_satz" in p:
        _satz(p["ust_satz"], "positionen.ust_satz")
    e = v.get("einheiten", {})
    _ja(isinstance(e, dict) and len(e) <= 50 and all(isinstance(k, str) and 1 <= len(k) <= 20 and isinstance(w, str)
        and re.fullmatch(r"[A-Z0-9]{2,3}", w) for k, w in e.items()), "einheiten: höchstens 50, Code wie HUR")
    return v
