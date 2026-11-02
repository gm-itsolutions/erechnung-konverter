"""Angelernte Vorlagen: Felder per Rahmen und Anker, keine Regex (docs/lernmodus/spezifikation.md 5, 6)."""
import difflib
import re
import statistics
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import pdfplumber

from .modell import Nachlass, Partei, Position, Rechnung, betrag, runde

FORMAT = 1
PFLICHT_FELDER = ("nummer", "datum", "summe_netto", "summe_brutto", "kaeufer")
FELDER = (*PFLICHT_FELDER, "nummer_kontrolle", "leistungsdatum", "faellig", "zahlungsziel_tage", "summe_ust", "nachlass")
SPALTEN = ("nr", "bezeichnung", "menge", "einheit", "menge_einheit", "einzelpreis", "ust_satz", "netto", "ignorieren")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,39}")
GERAETE = {"con", "prn", "aux", "nul", *(f"{g}{i}" for g in ("com", "lpt") for i in range(10))}   # Windows-Gerätenamen
MUSTER, MAX_PDF = re.compile(r"m[0-9]{1,3}"), 10 * 1024 * 1024   # Muster-ID im Entwurf, Größe je Muster-PDF
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
RAND = 0.005
BETRAG = re.compile(r"-?\d[\d. ]*[,.] ?\d{2}")
DATUM = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})")
SATZ = r"(\d{1,2}(?:[,.]\d{1,2})?)"
class Wort(NamedTuple):
    text: str
    x0: float
    top: float
    x1: float
    bottom: float
Seite = list[Wort]
def woerter_aus_pdf(pdf: Path) -> list[Seite]:
    with pdfplumber.open(pdf) as d:
        return [[Wort(w["text"], w["x0"] / s.width, w["top"] / s.height, w["x1"] / s.width, w["bottom"] / s.height)
                 for w in s.extract_words()] for s in d.pages]
def zeilen(woerter: Seite) -> list[list[Wort]]:
    if not woerter:
        return []
    tol = statistics.median(w.bottom - w.top for w in woerter) / 2
    mitte = lambda w: (w.top + w.bottom) / 2
    ergebnis: list[list[Wort]] = []
    for w in sorted(woerter, key=mitte):
        if ergebnis and mitte(w) - mitte(ergebnis[-1][0]) <= tol:
            ergebnis[-1].append(w)
        else:
            ergebnis.append([w])
    return [sorted(z, key=lambda w: w.x0) for z in ergebnis]
def _norm(t: str) -> str:
    return "".join(t.split()).lower()
def treffer(seite: Seite, text: str, ocr: bool = False) -> list[tuple[float, float, float, str | None]]:
    """Wortfolgen einer Zeile, die dem Ankertext entsprechen; {satz} liest eine Zahl."""
    teile = _norm(text).split("{satz}")
    muster = re.compile(SATZ.join(map(re.escape, teile))) if len(teile) == 2 else None
    ziel, n = _norm(text), len(text.split()) + 2
    genau, unscharf = [], []
    for z in zeilen(seite):
        for i in range(len(z)):
            for j in range(i + 1, min(i + n, len(z)) + 1):
                kette = _norm("".join(w.text for w in z[i:j]))
                if muster:
                    m = muster.fullmatch(kette)
                    if m:
                        genau.append((z[i].x0, z[i].top, z[j - 1].x1, m.group(1).replace(",", ".")))
                elif kette == ziel:
                    genau.append((z[i].x0, z[i].top, z[j - 1].x1, None))
                elif ocr and difflib.SequenceMatcher(None, kette, ziel).ratio() >= 0.85:
                    unscharf.append((z[i].x0, z[i].top, z[j - 1].x1, None))
    return genau or unscharf
def finde_anker(seiten, anker, seite, ocr=False):
    x, y = anker["rahmen"][:2]
    reihenfolge = range(len(seiten)) if seite == "erste" else range(len(seiten) - 1, -1, -1)
    for i in reihenfolge:
        t = treffer(seiten[i], anker["text"], ocr)
        if t:
            tx, ty, _, _ = min(t, key=lambda h: (h[0] - x) ** 2 + (h[1] - y) ** 2)
            return i, tx - x, ty - y
    return None
def woerter_im_rahmen(seite, rahmen, dx=0.0, dy=0.0):
    x0, y0, x1, y1 = rahmen[0] + dx - RAND, rahmen[1] + dy - RAND, rahmen[2] + dx + RAND, rahmen[3] + dy + RAND
    return [w for w in seite if x0 <= (w.x0 + w.x1) / 2 <= x1 and y0 <= (w.top + w.bottom) / 2 <= y1]
def _spur(rahmen, dx: float, dy: float) -> list[float]:
    """Rahmen um den Seitenversatz verschoben, auf 4 Stellen gerundet (für die Spur)."""
    return [round(rahmen[0] + dx, 4), round(rahmen[1] + dy, 4), round(rahmen[2] + dx, 4), round(rahmen[3] + dy, 4)]
def feld_text(seiten, v, name, ocr=False, spur=None):
    if not seiten:
        raise BereichsFehler("PDF ohne Seiten")
    f = v["felder"].get(name)
    if not f:
        return None
    if "anker" in f:
        gefunden = finde_anker(seiten, f["anker"], f["seite"], ocr)
        if gefunden is None:
            if name in PFLICHT_FELDER:
                raise BereichsFehler(f"Anker „{f['anker']['text']}“ nicht gefunden (Vorlage {v['name']})")
            return None
        i, dx, dy = gefunden
    else:   # ohne Anker: Seitenversatz des Nummer-Ankers übernehmen (Druckweg verschiebt die ganze Seite)
        i, dx, dy = (0 if f["seite"] == "erste" else len(seiten) - 1), 0.0, 0.0
        n = v["felder"].get("nummer")
        if name != "nummer" and n and "anker" in n:
            g = finde_anker(seiten, n["anker"], n["seite"], ocr)
            if g and g[0] == i:
                dx, dy = g[1], g[2]
    if spur is not None:
        spur[name] = {"seite": i, "rahmen": _spur(f["rahmen"], dx, dy)}
    return i, [" ".join(w.text for w in z) for z in zeilen(woerter_im_rahmen(seiten[i], f["rahmen"], dx, dy))]

def _wert(seiten, v, name, ocr, spur, lesen):
    t = feld_text(seiten, v, name, ocr, spur)
    if t is None or not " ".join(t[1]).strip():
        if name in PFLICHT_FELDER:
            raise BereichsFehler(f"Feld {name} leer (Vorlage {v['name']})")
        return None
    try:
        return lesen(" ".join(t[1]))
    except ValueError as e:
        raise BereichsFehler(f"Feld {name}: {e}") from None
def _betrag(t: str) -> Decimal:
    m = BETRAG.findall(t)
    if not m:
        raise ValueError(f"kein Betrag in {t!r}")
    return abs(betrag(m[-1]))
def _datum(t: str) -> date:
    m = DATUM.search(t.replace("O", "0"))
    if not m:
        raise ValueError(f"kein Datum in {t!r}")
    j = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
    return date(j, int(m[2]), int(m[1]))
def _tage(t: str) -> int:
    m = re.search(r"\d{1,3}", t)
    if not m or not 1 <= int(m[0]) <= 365:
        raise ValueError(f"keine Tageszahl in {t!r}")
    return int(m[0])
def _nummer(t: str) -> str:
    n = "".join(t.split())
    if not re.fullmatch(r"[A-Za-z0-9./_-]{1,30}", n):
        raise ValueError(f"Rechnungsnummer {n!r} enthält unzulässige Zeichen")
    return n
def kopf_aus_bereichen(seiten, v, ocr=False, spur=None) -> dict:
    w = lambda n, f: _wert(seiten, v, n, ocr, spur, f)
    k = {"nummer": w("nummer", _nummer), "datum": w("datum", _datum), "leistungsdatum": w("leistungsdatum", _datum),
         "summe_netto": w("summe_netto", _betrag), "summe_ust": w("summe_ust", _betrag),
         "summe_brutto": w("summe_brutto", _betrag), "nachlass": w("nachlass", _betrag)}
    kontrolle = w("nummer_kontrolle", _nummer)
    if kontrolle is not None and (re.sub(r"O0?", "0", kontrolle) if ocr else kontrolle) != k["nummer"]:
        raise BereichsFehler(f"Rechnungsnummer uneinheitlich gelesen: {k['nummer']} / {kontrolle}")
    k["faellig"] = w("faellig", _datum)
    tage = w("zahlungsziel_tage", _tage)
    if k["faellig"] is None and tage:
        k["faellig"] = k["datum"] + timedelta(days=tage)
    t = feld_text(seiten, v, "kaeufer", ocr, spur)
    if t is None:
        raise BereichsFehler(f"Feld kaeufer fehlt (Vorlage {v['name']})")
    z = t[1]
    plz = [i for i, s in enumerate(z) if re.match(r"\d{5} ", s)]
    if not plz or plz[-1] < 2:
        raise BereichsFehler(f"Käuferblock ohne Name, Straße, PLZ/Ort (Vorlage {v['name']})")
    p = plz[-1]
    k["kaeufer"] = Partei(z[0].strip(), z[p - 1].strip(), z[p][:5], z[p][6:].strip())
    k["steuern"] = _steuern(seiten, v, ocr, spur)
    return k
def _steuern(seiten, v, ocr, spur) -> dict[Decimal, Decimal]:
    s = v.get("steuern")
    if not s:
        return {}
    if not seiten:
        raise BereichsFehler("PDF ohne Seiten")
    reihenfolge = range(len(seiten)) if s["seite"] == "erste" else range(len(seiten) - 1, -1, -1)
    i = next((j for j in reihenfolge if treffer(seiten[j], s["anker"]["text"], ocr)), reihenfolge[0])
    ax, ay = s["anker"]["rahmen"][:2]
    ergebnis = {}
    for n, (x, y, _, satz) in enumerate(treffer(seiten[i], s["anker"]["text"], ocr)):
        dx, dy = x - ax, y - ay
        text = " ".join(w.text for w in woerter_im_rahmen(seiten[i], s["rahmen"], dx, dy))
        try:
            ergebnis[Decimal(satz) if satz else Decimal(str(s["satz"]))] = _betrag(text)
        except ValueError as e:
            raise BereichsFehler(f"Steuerzeile: {e}") from None
        if spur is not None:
            spur[f"steuern{n + 1}"] = {"seite": i, "rahmen": _spur(s["rahmen"], dx, dy)}
    return ergebnis

def _posbetrag(t: str) -> Decimal:
    """Betrag mit Vorzeichen (Positionszeilen können negativ sein); ValueError bei Unlesbarem."""
    m = BETRAG.findall(t)
    if not m:
        raise ValueError(f"kein Betrag in {t!r}")
    return betrag(m[-1])
def _menge(t: str) -> Decimal:
    m = re.fullmatch(r"-?\d[\d.]*(?:,\d+)?", t.strip())
    if not m:
        raise ValueError(f"keine Menge in {t!r}")
    return betrag(m[0])
def _satz_posbetrag(t: str) -> Decimal:
    m = re.search(SATZ, t)
    if not m:
        raise ValueError(f"kein Steuersatz in {t!r}")
    return Decimal(m[1].replace(",", "."))
def _oder_none(lesen, text: str):
    try:
        return lesen(text) if text.strip() else None
    except (ValueError, ArithmeticError):
        return None
def _naechster(t, rahmen):
    return min(t, key=lambda h: (h[0] - rahmen[0]) ** 2 + (h[1] - rahmen[1]) ** 2) if t else None
def positionen_aus_bereichen(seiten, v, ocr=False, spur=None):
    from .vorlagen import _anfuegen          # Silbentrennung wie Regex-Vorlagen; lokal gegen Zirkelimport
    p, kopf, ende = v["positionen"], v["positionen"]["kopf"], v["positionen"].get("ende")
    arten = [s["art"] for s in p["spalten"]]
    grenzen0 = [p["links"], *(s["bis"] for s in p["spalten"])]
    kr = kopf["rahmen"]
    kx, sx, ergebnis, ignoriert = kr[0], 1.0, [], []   # Lage und Maßstab des Kopfs (Edge „an Seite anpassen“)
    for i, seite in enumerate(seiten):
        k = _naechster(treffer(seite, kopf["text"], ocr), kr)
        if i == 0 and k is None:
            raise BereichsFehler(f"Tabellenkopf „{kopf['text']}“ nicht gefunden (Vorlage {v['name']})")
        if k:
            kx, sx = k[0], (k[2] - k[0]) / (kr[2] - kr[0])
        oben = k[1] + (kr[3] - kr[1]) * sx if k else 0.0
        e = _naechster(treffer(seite, ende["text"], ocr), ende["rahmen"]) if ende else None
        unten = e[1] if e else p["unten"]
        grenzen = [kx + (g - kr[0]) * sx for g in grenzen0]
        if spur is not None:
            spur[f"positionen{i + 1}"] = {"seite": i, "rahmen": [round(grenzen[0], 4), round(oben, 4),
                                                                 round(grenzen[-1], 4), round(unten, 4)]}
        begonnen = k is not None
        for z in zeilen([w for w in seite if oben <= (w.top + w.bottom) / 2 < unten]):
            zelle = {a: [] for a in arten}
            for w in z:
                xm = (w.x0 + w.x1) / 2
                for a, l, r in zip(arten, grenzen, grenzen[1:]):
                    if l <= xm < r:
                        zelle[a].append(w.text)
                        break
            t = {a: " ".join(ws) for a, ws in zelle.items()}
            netto = _oder_none(_posbetrag, t.get("netto", ""))
            if not begonnen and netto is None:
                continue                      # Folgeseite ohne Kopf: Briefkopf überspringen
            begonnen = True
            einheit, mt = t.get("einheit", "").strip(), t.get("menge", "")
            if "menge_einheit" in t:
                m = re.match(r"\s*(-?\d[\d.]*(?:,\d+)?)\s*(.*)", t["menge_einheit"])
                mt, einheit = (m[1], m[2].strip()) if m else ("", "")
            menge = _oder_none(_menge, mt)
            preis = _oder_none(_posbetrag, t.get("einzelpreis", ""))
            bez = t.get("bezeichnung", "").strip()
            if netto is not None and (menge is not None or preis is not None):
                menge = menge if menge is not None else Decimal("1")
                satz = _oder_none(_satz_posbetrag, t.get("ust_satz", ""))
                if preis is None:
                    preis = runde(netto / menge) if menge else netto
                ergebnis.append(Position(
                    nr=t.get("nr", "").strip() or str(len(ergebnis) + 1), bezeichnung=bez, menge=menge,
                    einheit=v.get("einheiten", {}).get(einheit, "C62"), einzelpreis=preis, netto=netto,
                    ust_satz=satz if satz is not None else Decimal(str(p.get("ust_satz", 19)))))
            elif netto is None and bez and ergebnis:
                ergebnis[-1].bezeichnung = _anfuegen(ergebnis[-1].bezeichnung, bez)
            elif any(s.strip() for s in t.values()):
                ignoriert.append(" ".join(w.text for w in z))
        if e:
            break
    if not ergebnis:
        raise BereichsFehler(f"keine Positionen gefunden (Vorlage {v['name']})")
    return ergebnis, ignoriert
def rechnung_aus_bereichen(seiten, v, verkaeufer, ocr=False, spur=None):
    k = kopf_aus_bereichen(seiten, v, ocr, spur)
    pos, _ = positionen_aus_bereichen(seiten, v, ocr, spur)
    return Rechnung(
        nummer=k["nummer"], datum=k["datum"], verkaeufer=verkaeufer, kaeufer=k["kaeufer"], positionen=pos,
        summe_netto=k["summe_netto"], summe_brutto=k["summe_brutto"], summe_ust=k["summe_ust"], steuern=k["steuern"],
        leistungsdatum=k["leistungsdatum"], faellig=k["faellig"], vorlage=v["name"],
        nachlaesse=[Nachlass(k["nachlass"], "Nachlass")] if k["nachlass"] else [])
