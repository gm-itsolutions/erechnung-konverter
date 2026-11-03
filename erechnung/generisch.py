"""Generische Erkennung: layoutunabhängiger Vorschlag aus dem Rechnungstext (Vorschlagsquelle für den Lernmodus).

Erzeugt nie eine E-Rechnung. Bestätigt ist ein Vorschlag nur, wenn Rechnungsnummer und Datum gefunden sind und
`modell.summenabgleich` besteht. Alle Regeln sind allgemeine Rechnungskonventionen (de/en): Schlüsselwörter,
Datumsformate, Summenblock von unten, Positionen über Menge × Einzelpreis = Betrag.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable, Iterable
from .modell import CENT, Nachlass, Partei, Position, Rechnung, runde, summenabgleich
from .vorlagen import MIN_ZEICHEN, _anfuegen, pdf_text


@dataclass
class Vorschlag:
    nummer: str | None = None
    datum: date | None = None
    leistungsdatum: date | None = None
    faellig: date | None = None
    kaeufer: Partei | None = None
    positionen: list[Position] = field(default_factory=list)
    summe_netto: Decimal | None = None
    steuern: dict[Decimal, Decimal] = field(default_factory=dict)
    summe_ust: Decimal | None = None
    summe_brutto: Decimal | None = None
    nachlaesse: list[Nachlass] = field(default_factory=list)
    fundstellen: dict[str, str] = field(default_factory=dict)   # Feld → Zeile, aus der der Wert stammt
    bestaetigt: bool = False
    grund: str = ""
    lesart: str = ""


# ---------------------------------------------------------------- Datum
MONATE = {m: i + 1 for i, ms in enumerate((
    "januar jan january janvier", "februar feb february février fevrier", "märz mär maerz mar march mars",
    "april apr avril", "mai may", "juni jun june juin", "juli jul july juillet", "august aug août aout",
    "september sep sept septembre", "oktober okt oct october octobre", "november nov novembre",
    "dezember dez dec december décembre decembre")) for m in ms.split()}
_MON = "|".join(sorted(map(re.escape, MONATE), key=len, reverse=True))
DATUM_RE = re.compile(
    r"(?<![\d.])(?P<t>\d{1,2})\.\s?(?P<m>\d{1,2})\.\s?(?P<j>\d{4}|\d{2})(?![\d])"
    r"|(?<!\d)(?P<ij>\d{4})-(?P<im>\d{2})-(?P<it>\d{2})(?!\d)"
    r"|(?<![\d/])(?P<st>\d{1,2})/(?P<sm>\d{1,2})/(?P<sj>\d{4})(?![\d/])"
    rf"|(?<!\d)(?P<nt>\d{{1,2}})\.?\s+(?P<nm>{_MON})\.?,?\s+(?P<nj>\d{{4}})(?!\d)"
    rf"|\b(?P<em>{_MON})\.?\s+(?P<et>\d{{1,2}}),?\s+(?P<ej>\d{{4}})(?!\d)", re.I)


def daten(zeile: str) -> list[tuple[date, int, int]]:
    """Alle Datumsangaben der Zeile: TT.MM.JJJJ, TT.MM.JJ, ISO, TT/MM/JJJJ, „2. November 2026“, „Nov 2, 2026“."""
    erg = []
    for m in DATUM_RE.finditer(zeile):
        g = m.groupdict()
        try:
            if g["t"]:
                j = int(g["j"]) + (2000 if len(g["j"]) == 2 else 0)
                d = date(j, int(g["m"]), int(g["t"]))
            elif g["ij"]:
                d = date(int(g["ij"]), int(g["im"]), int(g["it"]))
            elif g["st"]:
                if int(g["st"]) <= 12 and int(g["sm"]) <= 12 and g["st"] != g["sm"]:
                    continue    # 11/03/2017: Tag/Monat oder Monat/Tag (US) – nicht raten
                d = date(int(g["sj"]), int(g["sm"]), int(g["st"]))
            elif g["nt"]:
                d = date(int(g["nj"]), MONATE[g["nm"].lower()], int(g["nt"]))
            else:
                d = date(int(g["ej"]), MONATE[g["em"].lower()], int(g["et"]))
        except ValueError:
            continue
        if 1990 <= d.year <= 2100:
            erg.append((d, m.start(), m.end()))
    return erg


# ---------------------------------------------------------------- Zahlen
@dataclass
class Zahl:
    wert: Decimal
    start: int
    ende: int
    stellen: int        # Nachkommastellen
    prozent: bool

    @property
    def betrag(self) -> bool:
        return self.stellen == 2 and not self.prozent


ZAHL_RE = re.compile(r"(?<![\w.,/'-])([-−–]\s?)?(\d+(?:[.,']\d+)*)(?![\d/])(\s?%)?")


def zahl(t: str) -> tuple[Decimal, int]:
    """Zahl in deutscher oder englischer Schreibweise → (Wert, Nachkommastellen). Das letzte von „.“/„,“ ist das
    Dezimalzeichen, wenn beide vorkommen; nur Punkte mit Dreiergruppen sind Tausenderpunkte („1.500“)."""
    t = t.replace("'", "")
    if "," in t and "." in t:
        dez = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if dez == "," else ",", "").replace(dez, ".")
    elif "," in t:
        t = t.replace(",", "") if t.count(",") > 1 else t.replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", t):
        t = t.replace(".", "")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise ValueError(t) from None
    return d, max(0, -d.as_tuple().exponent)


def zahlen(zeile: str) -> list[Zahl]:
    """Zahlen der Zeile ohne Datumsangaben; Minus nur direkt vor der Zahl (nicht „A-1051“)."""
    for _, a, e in daten(zeile):
        zeile = zeile[:a] + " " * (e - a) + zeile[e:]
    erg = []
    for m in ZAHL_RE.finditer(zeile):
        try:
            w, s = zahl(m.group(2))
        except ValueError:
            continue
        erg.append(Zahl(-w if m.group(1) else w, m.start(), m.end(), s, bool(m.group(3))))
    return erg


def betraege(zeile: str) -> list[Zahl]:
    return [z for z in zahlen(zeile) if z.betrag]


# ---------------------------------------------------------------- Schlüsselwörter
def _re(*w: str) -> re.Pattern:
    return re.compile("|".join(w), re.I)


NUMMER_LABEL = _re(
    r"\b(?:rechnungs?|beleg|gutschrift(?:s)?|invoice|credit\s?note|dokument|document|faktura|storno)"
    r"[-\s]?(?:nr|nummer|no|number|n°|#)\b\.?",
    r"\b(?:rechnung|gutschrift|invoice|beleg)\s+(?:nr|no|n°)\b\.?", r"\b(?:re|rg)[-.\s]?nr\b\.?",
    r"\bfacture\s+n[°o]\.?", r"\bn°\s+(?:de\s+)?facture\b")
NUMMER_KOPF = re.compile(   # Überschrift: „Rechnung RE-1“, „Handelsrechnung (380) Nr. 471102“, „Rechnung des Versicherers Nr. 1“
    r"^\s*[\w-]*(?:rechnung|invoice|gutschrift|facture|avoir|credit\s?note)[\w-]*"
    r"(?:(?:\s*(?:\([^)]*\)|\s[^\W\d]+)){0,4}?(?P<nr>\s*\b(?:nr|no|n°)\b\.?))?[\s:#]*(?P<w>\S+)", re.I)
NUMMER_MITTE = re.compile(r"(?<![\w-])(?:rechnung|invoice|gutschrift|facture)\b[\s:#]*(?P<w>\S+)", re.I)
NICHT_NUMMER = _re(r"kunden", r"auftrag", r"bestell", r"order", r"liefer", r"steuer", r"ust", r"vat\b", r"kundennr",
                   r"zu\s+rechnung", r"bezug", r"angebot")
DATUM_STARK = _re(r"(?:rechnungs|beleg|ausstellungs|invoice\s?|issue\s?)[-\s]?(?:datum|date)", r"issued(?:\s+(?:at|on))?",
                  r"date\s+(?:de\s+)?(?:la\s+)?facture", r"date\s+of\s+(?:invoice|issue)")
DATUM_LABEL = _re(r"\b(?:rechnungs|beleg|ausstellungs|invoice\s?|issue\s?)[-\s]?(?:datum|date)\b",
                  r"\bdate\s+(?:de\s+)?(?:la\s+)?facture\b", r"\bdate\s+of\s+(?:invoice|issue)\b",
                  r"(?<![\w-])datum\b", r"(?<![\w-])date\b", r"\bissued(?:\s+(?:at|on))?")
DATUM_NICHT = _re(r"liefer", r"leistung", r"fällig", r"faellig", r"due", r"delivery", r"supply", r"order",
                  r"bestell", r"auftrag", r"zahl", r"règlement", r"reglement", r"payment", r"paiement", r"échéance", r"echeance", r"geburt", r"service")
LEISTUNG_LABEL = _re(r"leistungsdatum", r"lieferdatum", r"liefer-\s*und\s*leistungsdatum", r"leistungszeitraum",
                     r"leistungszeit", r"delivery\s+date", r"date\s+of\s+(?:supply|delivery|service)",
                     r"(?<![\w-])leistung\b", r"date\s+de\s+livraison")
FAELLIG_LABEL = _re(r"fällig\w*", r"faellig\w*", r"zahlbar\s+bis(?:\s+zum)?", r"due\s+date", r"payable\s+by",
                    r"date\s+d'échéance", r"bis\s+zum")
KOPF_WORT = re.compile(
    r"\b(pos|pos\.|position|menge|anzahl|anz\.|qty|quantity|quantité|bezeichnung|beschreibung|artikel|art\.?-?nr\.?|"
    r"leistung|description|item|einzelpreis|preis|ep|e-preis|betrag|gesamt|gesamtpreis|summe|amount|price|"
    r"unit|einheit|me|einh\.|total|prix|ust\.?|mwst\.?|rabatt|nettopreis|stück|einzel)\b", re.I)
STEUER_WORT = re.compile(r"(?<![\w-])(mwst|mw\.-?st|ust|umsatzsteuer|mehrwertsteuer|vat|tax|tva|steuer|iva|btw)"
                         r"(?![-\s]?(?:id|nr|nummer|number|ident))", re.I)
ENTHALTEN = _re(r"enthalt", r"inkl", r"incl", r"included", r"darin", r"including")
NETTO = _re(r"netto", r"warenwert", r"zwischensumme", r"summe\s+positionen", r"positionssumme", r"\bnet\b",
            r"subtotal", r"sub-total", r"total\s+ht\b", r"\bexcl", r"ohne\s+(?:ust|mwst|umsatzsteuer)",
            r"steuerbasis", r"taxable")
UST_SUMME = _re(r"summe\s+(?:der\s+)?(?:ust|mwst|umsatzsteuer|steuer)", r"steuerbetrag", r"total\s+(?:taxes|tax|vat|tva)",
                r"(?:vat|tax)\s+(?:total|amount)", r"umsatzsteuer\s+gesamt", r"^\s*(?:mwst|ust|umsatzsteuer)\.?\s*:?\s*[-\d]")
BRUTTO = _re(r"brutto", r"gesamtbetrag", r"rechnungsbetrag", r"endbetrag", r"endsumme", r"gesamtsumme", r"zu\s+zahlen",
             r"zahlbetrag", r"gutschriftbetrag", r"rechnungssumme", r"\btotal\b", r"amount\s+due", r"balance\s+due",
             r"\bttc\b", r"\bgesamt\b", r"\bsumme\b", r"betrag\b", r"\bpayable\b")
BRUTTO_STARK = _re(r"brutto", r"gesamtbetrag", r"rechnungsbetrag", r"rechnungssumme", r"endbetrag", r"endsumme",
                   r"\btotal\b", r"\bttc\b", r"inkl", r"incl")
UEBERTRAG = _re(r"übertrag", r"uebertrag", r"carried\s+forward", r"brought\s+forward", r"transfer")
RABATT = _re(r"rabatt", r"nachlass", r"abzüglich", r"abzgl", r"abschlag", r"discount", r"remise", r"allowance")
ZUSCHLAG = _re(r"zuschlag", r"versandkosten", r"fracht", r"surcharge")
SUMMENWORT = _re(r"gesamt", r"summe", r"total")
FUSS = _re(r"\biban\b", r"\bbic\b", r"ust-?id", r"steuernummer", r"\bseite\s+\d+\s*(?:von|/)\s*\d",
           r"\bblatt\s+\d+\s*(?:von|/)\s*\d", r"\bpage\s+\d+\s*(?:of|/)\s*\d",
           r"geschäftsführ", r"amtsgericht", r"\bhrb\b", r"bankverbindung", r"www\.", r"@", r"\btel\b\.?", r"\btelefon\b",
           r"\bfax\b", r"zahlbar", r"zahlungsziel", r"payment\s+terms", r"vielen\s+dank")
KLEINUNTERNEHMER = _re(r"§\s*19\s*ustg", r"kleinunternehmer", r"keine\s+umsatzsteuer", r"ohne\s+umsatzsteuer",
                       r"not\s+subject\s+to\s+vat", r"umsatzsteuerfrei", r"steuerfrei")
EINHEITEN = {"std": "HUR", "std.": "HUR", "stunde": "HUR", "stunden": "HUR", "h": "HUR", "hour": "HUR",
             "hours": "HUR", "stk": "H87", "stk.": "H87", "stück": "H87", "st": "H87", "st.": "H87", "pcs": "H87",
             "pc": "H87", "piece": "H87", "pieces": "H87", "tag": "DAY", "tage": "DAY", "day": "DAY", "days": "DAY",
             "km": "KMT", "m": "MTR", "lfm": "MTR", "m²": "MTK", "m2": "MTK", "m³": "MTQ", "m3": "MTQ",
             "kg": "KGM", "l": "LTR", "liter": "LTR", "t": "TNE", "psch": "LS", "pauschal": "LS", "pausch.": "LS"}


# ---------------------------------------------------------------- Kopffelder
def _token(rest: str) -> tuple[str, int] | None:
    """Erstes Wort nach einer Beschriftung (Trenner : # . übersprungen) → (Wert, Versatz) oder None."""
    m = re.match(r"[\s:#.]*(?:(?:nr|no|n°)\b\.?[\s:#]*)?([A-Za-z0-9][\w\-/.,]*)", rest, re.I)
    if not m:
        return None
    w = m.group(1).rstrip(".,-/")
    if re.match(r" \d", rest[m.end(1):]) or len(w) < 2:   # zerrissener Text („4 71102“): nicht raten
        return None
    if not re.search(r"\d", w) or len(w) > 30 or daten(w) or re.fullmatch(r"-?[\d.,]*[.,]\d{2}", w):
        return None
    return w, m.start(1)


def _darunter(zeilen: list[str], i: int, a: int, e: int, pruefe: Callable[[str], object]):
    """Wert unter einer Beschriftung (Kopftabelle): in den nächsten zwei Zeilen das Wort, das die Spalte [a, e)
    am meisten überlappt."""
    for z in zeilen[i + 1:i + 3]:
        besten = []
        for m in re.finditer(r"\S+(?: \S+)*", z):
            ueber = min(e, m.end()) - max(a, m.start())
            if ueber > 0:
                besten.append((ueber, m.group()))
        for _, w in sorted(besten, reverse=True):
            if (x := pruefe(w)) is not None:
                return x
        if besten:
            return None
    return None


def _nummer(zeilen: list[str]) -> tuple[str | None, str, str]:
    """(Nummer, Fundstelle, Zweifel – leer, wenn sicher). Punkte je Fundstelle: Beschriftung („Rechnungsnr.:“) und
    „Rechnung Nr. …“ 3, Überschrift „Rechnung RE-1“ (auch mitten in der Zeile) und Beschriftung mitten im Fließtext 1.
    Sicher ab 2 Punkten: eine unbeschriftete Nummer muss mindestens zweimal vorkommen (Kopf, Seitenkopf, Anschriftzeile)."""
    punkte: dict[str, int] = {}
    fund: dict[str, str] = {}

    def neu(w, z, p):
        punkte[w] = punkte.get(w, 0) + p
        fund.setdefault(w, z.strip())
    for i, z in enumerate(zeilen):
        for m in NUMMER_LABEL.finditer(z):
            if NICHT_NUMMER.search(z[max(0, m.start() - 12):m.start()]):
                continue
            t = _token(z[m.end():])
            w = t[0] if t else None
            if w is None and not re.match(r"[\s:#.]*\S*\d", z[m.end():]):
                w = _darunter(zeilen, i, m.start(), m.end(), lambda s: (_token(s) or (None,))[0])
            if w:
                prosa = len(re.findall(r"[^\W\d]{2,}", z[:m.start()])) >= 5
                neu(w, z, 1 if prosa else 3)
        for a, c in [(0, z)] + _zellen(z)[1:]:
            if (m := NUMMER_KOPF.match(c)) and (t := _token(m.group("w"))) and not (
                    m.group("nr") and NICHT_NUMMER.search(c[:m.start("nr")])):   # „Rechnung gemäß Bestellung Nr. …“
                neu(t[0], z, 3 if m.group("nr") else 1)
                break
        else:   # „Kunde GmbH  Rechnung: 4711-26“, Seitenkopf „Firma · Rechnung 4711-26 vom …“: je Fundstelle 1 Punkt
            for m in NUMMER_MITTE.finditer(z):
                if m.start() and not NUMMER_LABEL.search(z) and not NICHT_NUMMER.search(z[max(0, m.start() - 12):m.start()]) \
                        and len(re.findall(r"[^\W\d]{2,}", z[:m.start()])) < 5 and (t := _token(m.group("w"))):
                    neu(t[0], z, 1)
    if not punkte:
        return None, "", ""
    best = max(punkte.values())
    top = [w for w, p in punkte.items() if p == best]
    zweifel = "Rechnungsnummer mehrdeutig" if len(top) > 1 else \
        "Rechnungsnummer nur schwach belegt (ohne Beschriftung)" if best < 2 else ""
    return top[0], fund[top[0]], zweifel


def _datumsfeld(zeilen: list[str], label: re.Pattern, nicht: re.Pattern | None = None, stark: re.Pattern | None = None,
                nummer_zeile: str = "", brief: bool = False) -> tuple[date | None, str, bool]:
    """(Datum, Fundstelle, eindeutig). Je 3 Punkte: Datum direkt nach der Beschriftung (bis 25 Zeichen) oder darunter,
    Datum hinter der Rechnungsnummer („Rechnung Nr. 1 vom …“). Je 1 Punkt: „vom …“, Briefdatum „Ort, den …“.
    `nicht` (z. B. „Liefer-“ vor „Datum“) und Fußzeilen gelten nicht für `stark` (z. B. „Rechnungsdatum“).
    „vom …“ und Briefdatum nur mit `brief` (Rechnungsdatum)."""
    punkte: dict[date, int] = {}
    fund: dict[date, str] = {}

    def neu(d, z, p):
        punkte[d] = punkte.get(d, 0) + p
        fund.setdefault(d, z.strip())
    for i, z in enumerate(zeilen):
        for m in label.finditer(z):
            if not (stark and stark.fullmatch(m.group())) and (
                    nicht and nicht.search(z[max(0, m.start() - 20):m.end() + 2]) or FUSS.search(z)):
                continue
            rest = z[m.end():]
            d = daten(rest)
            if d and d[0][1] <= 25 and not re.search(r"[A-Za-zÄÖÜäöü]{4,}", rest[:d[0][1]].replace("vom", "")):
                neu(d[0][0], z, 3)
            elif not re.search(r"\S", rest[:20]) or re.match(r"\s*:?\s{2,}\S*[A-Za-z]", rest):
                d = _darunter(zeilen, i, m.start(), m.end(), lambda s: (daten(s) or [(None,)])[0][0])
                if d:
                    neu(d, z, 3)
        if nummer_zeile and z.strip() == nummer_zeile:
            if d := [x for x in daten(z) if re.search(r"(?i)\b(?:vom|von|from|du|dated)\s*$|\S\s{2,}$|\d\s+$",
                                                       z[:x[1]])]:
                neu(d[0][0], z, 3)
            elif re.search(r"(?i)\b(?:vom|von|dated)\s*$", z) and i + 1 < len(zeilen) and \
                    (d := daten(zeilen[i + 1])) and not zeilen[i + 1][:d[0][1]].strip():
                neu(d[0][0], z, 3)      # „Rechnung Nr. 1 vom“ + Datum in der nächsten Zeile
        for m in re.finditer(r"\bvom\s+", z, re.I) if brief else ():
            d = daten(z[m.end():])
            if d and d[0][1] == 0 and not re.search(r"(?i)version|stand|gültig|bis|\bzu\b|bezug|bestell|auftrag|"
                                                   r"liefer|angebot|order", z[:m.start()]) \
                    and not re.match(r"\s*bis\b", z[m.end() + d[0][2]:]):
                neu(d[0][0], z, 1)
        if brief and (m := re.search(r"(?:^|\s{2,})[A-ZÄÖÜ][\w.\-]+(?: [\w.\-]+)*,\s+(?:den\s+)?(\S.*?)\s*$", z)) \
                and (d := daten(m.group(1))) and d[0][1] == 0 and d[0][2] == len(m.group(1)):
            neu(d[0][0], z, 1)          # Briefdatum „Ort, den 2. November 2026“
    if not punkte:
        return None, "", False
    best = max(punkte.values())
    top = [d for d, p in punkte.items() if p == best]
    return top[0], fund[top[0]], len(top) == 1


# ---------------------------------------------------------------- Positionen
@dataclass
class _Zeile:
    i: int
    text: str
    menge: Decimal
    einheit: str
    einzelpreis: Decimal
    netto: Decimal
    rabatt: Decimal | None
    saetze: list[Decimal]      # Steuersatz-Kandidaten (Prozentzahlen/Zahlen nach dem Einzelpreis)
    geprueft: bool             # Menge × Einzelpreis (− Rabatt) = Betrag
    bezeichnung: str = ""


def _position(i: int, z: str) -> _Zeile | None:
    zs = zahlen(z)
    bt = [x for x in zs if x.betrag]
    if not bt:
        return None
    netto = bt[-1]
    nach = [x for x in zs if x.start > netto.start]
    if any(not (x.prozent or (x.stellen == 0 and x.wert < 100)) for x in nach):
        return None
    vor = [x for x in zs if x.start < netto.start]
    treffer = []
    for ep in vor:
        if ep.prozent or ep.stellen < 2 or ep.wert == 0:
            continue
        for q in vor:
            if q is ep or q.prozent:
                continue
            roh = q.wert * ep.wert
            for rab in [None] + [x for x in vor if x.prozent and x.start > ep.start]:
                wert = roh if rab is None else roh * (100 - rab.wert) / 100
                if abs(runde(wert) - netto.wert) <= CENT:
                    abstand = (rab is not None, q.start > ep.start, abs(ep.start - q.ende))
                    treffer.append((abstand, q, ep, rab))
    if treffer:
        _, q, ep, rab = min(treffer, key=lambda t: t[0])
        genutzt = {id(q), id(ep), id(netto)} | ({id(rab)} if rab else set())
        saetze = [x.wert for x in zs if id(x) not in genutzt and x.start > ep.start and (x.prozent or x.stellen in (0, 2))
                  and 0 <= x.wert <= 30]
        m = re.match(r"\s*([^\W\d][\w.²³()/]*)", z[q.ende:])
        einheit = m.group(1) if m and (m.group(1).lower() in EINHEITEN or len(m.group(1)) <= 4) else ""   # nicht „Design“
        vorne = re.sub(r"^\s*\d{1,4}[.)]?\s+", "", z[:min(q.start, ep.start)])
        bez = vorne if vorne.strip() else z[q.ende + (m.end() if einheit else 0):ep.start]
        return _Zeile(i, z, q.wert, einheit, ep.wert, netto.wert, rab.wert if rab else None, saetze, True,
                      " ".join(bez.replace("€", "").split()))
    saetze = [x.wert for x in zs if x.prozent and 0 <= x.wert <= 30]
    bez = re.sub(r"^\s*\d{1,4}[.)]?\s+", "", z[:netto.start])
    bez = re.sub(r"\s*(?:[-−]?\d[\d.,]*\s*%?|€|EUR)\s*$", "", bez.replace("€", ""))
    return _Zeile(i, z, Decimal(1), "", netto.wert, netto.wert, None, saetze, False, " ".join(bez.split()))


def _art(z: str) -> str | None:
    """Art einer Summenzeile: T (Steuer mit Satz), N, S (Steuersumme), B, R, Z, U (Übertrag) oder None."""
    if UEBERTRAG.search(z):
        return "U"
    rz = RABATT.search(z) or ZUSCHLAG.search(z)
    if not rz and (s := _steuerzeile(z)) and (STEUER_WORT.search(z) or s[2] is not None):
        return "T"     # Steuerzeile mit Satz; ohne Steuerwort nur arithmetisch belegt („7 %  160,00  11,20“)
    if NETTO.search(z) and not re.search(r"(?i)brutto|incl|inkl|ttc", z):
        return "N"
    if UST_SUMME.search(z):
        return "S"
    if RABATT.search(z):
        return "R"
    if ZUSCHLAG.search(z):
        return "Z"
    if BRUTTO.search(z):
        return "B"
    return None


def _steuer_tabelle(z: str):
    """Steuerzeile ohne %-Zeichen (Tabelle Basis | Satz | Steuer): Satz arithmetisch belegt → (Satz, Basis, Steuer)."""
    zs = zahlen(z)
    bt = [x for x in zs if x.betrag]
    if len(bt) < 2:
        return None
    steuer = bt[-1]
    for basis in bt[:-1]:
        for s in zs:
            if s is basis or s is steuer or not (0 < s.wert <= 30) or s.stellen > 2:
                continue
            if abs(runde(basis.wert * s.wert / 100) - steuer.wert) <= CENT:
                return s.wert, basis.wert, steuer.wert
    return None


def _steuerzeile(z: str) -> tuple[Decimal, Decimal, Decimal | None] | None:
    """(Satz, Steuer, Basis | None)."""
    zs = zahlen(z)
    pz = [x for x in zs if x.prozent]
    bt = [x for x in zs if x.betrag]
    if pz and bt:
        satz, steuer = pz[0].wert, bt[-1].wert
        basis = next((b.wert for b in bt[:-1] if abs(runde(b.wert * satz / 100) - steuer) <= CENT), None)
        if basis is None and len(bt) > 1:
            return None    # mehrere Beträge, keiner passt als Basis: keine Steuerzeile (z. B. Position)
        return satz, steuer, basis
    if (t := _steuer_tabelle(z)):
        return t[0], t[2], t[1]
    return None


def _satz(s: Decimal) -> Decimal:
    return s.quantize(Decimal(1)) if s == s.to_integral() else s.normalize()


# ---------------------------------------------------------------- Käufer
PLZ_RE = re.compile(r"^(?:(?:D|DE|A|AT|CH|F|FR|NL|B|L)[- ]?)?(\d{4,5})\s*([A-ZÄÖÜ][\w\-. ()]*)$")
ABSENDER = re.compile(r"[·•●|,–]\s*(?:[A-Z]{1,2}[- ])?\d{4,5}\s+[A-ZÄÖÜ]")   # „Firma · Weg 1 · 12345 Ort“
KAEUFER_LABEL = _re(r"rechnungsempfänger", r"rechnungsadresse", r"(?<!ver)käufer", r"leistungsempfänger", r"bill\s+to",
                    r"invoice\s+to", r"buyer", r"(?<![\w-])kunde\b", r"customer", r"(?<!waren)empfänger", r"client",
                    r"facturation", r"sold\s+to")
NICHT_KAEUFER = _re(r"liefer", r"leistungsort", r"delivery", r"ship\s+to", r"livraison", r"verkäufer", r"seller",
                    r"absender", r"zahlungsempf", r"supplier", r"vendor", r"versand", r"warenempfänger")
LABELWORT = set("rechnungsempfänger rechnungsadresse käufer leistungsempfänger bill to invoice buyer kunde customer "
                "empfänger client lieferanschrift lieferadresse leistungsort delivery address ship adresse de livraison "
                "verkäufer seller lieferant absender supplier vendor versand anschrift und abweichender warenempfänger "
                "an facturation sold from".split())


def _label(c: str) -> bool:
    """Beschriftungszelle: endet auf „:“ oder besteht nur aus Anschriften-Beschriftungen („Lieferanschrift / Leistungsort“)."""
    w = re.findall(r"[^\W\d_]+", c.lower())
    return c.rstrip().endswith(":") or bool(w) and all(x in LABELWORT for x in w)
STOP = _re(r"\brechnung", r"\binvoice\b", r"\bdatum\b", r"\bdate\b", r"\btel\b", r"\bfax\b", r"@", r"·", r"\|",
           r"\bseite\b", r"\bnr\b", r"\bnummer\b", r"www\.", r"\biban\b", r"\bust\b", r"\bsteuer-?(?:nummer|nr)")


def _zellen(z: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in re.finditer(r"\S+(?: \S+)*", z)]


ANSCHRIFT_FELD = re.compile(r"(?i)name|firma|anschrift|adresse|address|stra(?:ß|ss)e|company|empfänger|käufer|kunde")
VERKAEUFER_LABEL = _re(r"verkäufer", r"seller", r"lieferant", r"absender", r"supplier", r"vendor")


def _block(zeilen: list[str], i: int, a: int, zelle: str) -> tuple[list[str], int, bool, int]:
    """Anschriftenblock über der PLZ-Zelle (Spalte a): (Zeilen von oben, Zeile über dem Block, Fußzeile?, Spalte der
    Beschriftungen – bei „Name: …“ die Spalte der Schlüssel, sonst a)."""
    block, j, leer, fuss, ref = [zelle], i - 1, 0, False, a
    while j >= 0 and i - j <= 10 and len(block) < 4:
        zellen = _zellen(zeilen[j])
        if not zellen:
            leer += 1
            if leer >= 2:      # zwei Leerzeilen (Layout-Text): Block zu Ende
                break
            j -= 1
            continue
        leer = 0
        treffer = [c for s, c in zellen if abs(s - a) <= 2]
        if not treffer:
            if any(s < a + len(zelle) and s + len(c) > a - 2 for s, c in zellen):   # ragt in die Spalte: Ende
                break
            j -= 1                                    # nur andere Spalte (Datenkasten): überspringen
            continue
        c = treffer[0]
        links = [x for s, x in zellen if s < a - 2]
        if links and links[-1].rstrip().endswith(":") and not ANSCHRIFT_FELD.search(links[-1]):
            break                                     # „Nummer:   GE2020211“ (Feld in Schlüssel-Wert-Form)
        if links and links[-1].rstrip().endswith(":"):
            ref = min(ref, next(s for s, x in zellen if x is links[-1]))
        fuss = fuss or bool(FUSS.search(zeilen[j]) and not STOP.search(c))
        c = re.sub(r"\s+[^\W\d][\w.\-]*:\s*\S+\s*$", "", c)   # „Firma GmbH Datum: 02.11.2026“ (Text ohne Layout)
        if (m := re.match(r"([^:]{1,40}):\s*(.*)", c)) and not _label(c):
            if not ANSCHRIFT_FELD.search(m.group(1)) or re.search(r"\d", m.group(1)):
                if re.fullmatch(r"\S+", m.group(2)):
                    j -= 1                            # „Kundennr.: 10004“ zwischen den Anschriftzeilen
                    continue
                break
            c = m.group(2)                            # „Name: Kunden AG Mitte“
        if not c.strip() or _label(c) or ABSENDER.search(c) or (
                STOP.search(c) and not re.match(r"(?i)(herrn?|frau|z\.\s?h|attn|c/o)\b", c)):
            break
        block.insert(0, c)
        j -= 1
    return block, j, fuss, ref


def _kaeufer(zeilen: list[str]) -> tuple[Partei | None, str]:
    """Anschriftenblock mit PLZ-Zeile, der weder Verkäufer (Briefkopf, Fußzeile, „Verkäufer:“) noch Lieferanschrift ist.
    `zeilen` mit Leerzeilen: zwei Leerzeilen (Layout-Text) trennen Blöcke."""
    kopf = next((" ".join(z.split()) for z in zeilen if z.strip()), "").casefold()
    fusszeilen = " ".join(z for z in zeilen if FUSS.search(z) or ABSENDER.search(z) or "·" in z or "|" in z).casefold()
    bloecke, verkaeufer = [], set()
    for i, z in enumerate(zeilen[:-1]):    # „Verkäufer:“ allein in der Zeile, Name darunter (auch ohne erkannte PLZ)
        if VERKAEUFER_LABEL.search(z) and _label(z.strip()) and (n := next((x for x in zeilen[i + 1:] if x.strip()), "")):
            verkaeufer.add(" ".join(n.split()).casefold())
    for i, z in enumerate(zeilen):
        for a, zelle in _zellen(z):
            if not (m := PLZ_RE.match(zelle)) or re.search(r"\d{3,}", m.group(2)):
                continue
            block, j, fuss, ref = _block(zeilen, i, a, zelle)
            if len(block) < 2:
                continue
            if re.fullmatch(r"(?i)firma", block[0].strip()) and len(block) > 2:
                block = block[1:]
            name = " ".join(block[0].split())
            # nächste Beschriftung darüber in derselben Spalte (höchstens vier Zeilen)
            label = ""
            for k in range(j, max(-1, j - 4), -1):
                kand = [c for s, c in _zellen(zeilen[k]) if abs(s - ref) <= 2 and (KAEUFER_LABEL.search(c) or
                        NICHT_KAEUFER.search(c)) and (_label(c) or len(c) < 40)]
                if kand:
                    label = kand[-1]
                    break
            if VERKAEUFER_LABEL.search(label) or fuss:
                verkaeufer.add(name.casefold())
            bloecke.append((name, block, m, i, label))
    kandidaten = []
    for name, block, m, i, label in bloecke:
        if NICHT_KAEUFER.search(label) and not KAEUFER_LABEL.search(label) or re.match(r"(?i)(herrn?|frau)\b", name):
            continue
        n = name.casefold()
        if n in verkaeufer or n == kopf or (len(n) > 5 and (n in fusszeilen or n in kopf)):
            continue
        kandidaten.append((0 if label else 1, i, Partei(
            name, " ".join(block[-2].split()) if len(block) > 2 else "", m.group(1), " ".join(m.group(2).split())),
            block[0].strip()))
    if not kandidaten:
        return None, ""
    _, _, p, fund = min(kandidaten, key=lambda k: (k[0], k[1]))
    return p, fund


# ---------------------------------------------------------------- Erkennung
def _teilmenge(werte: list[Decimal], passt: Callable[[Decimal], bool]) -> int | None:
    """Eindeutige Teilmenge (Bitmaske) der Werte, deren Summe `passt`; None, wenn keine oder mehrere."""
    if len(werte) > 30:
        return None
    summen: dict[Decimal, tuple[int, int]] = {Decimal(0): (0, 1)}   # Summe → (Maske, Anzahl bis 2)
    for k, w in enumerate(werte):
        neu = dict(summen)
        for s, (maske, n) in summen.items():
            alt = neu.get(s + w, (maske | 1 << k, 0))
            neu[s + w] = (alt[0], min(2, alt[1] + n))
        summen = neu
        if len(summen) > 200_000:   # ponytail: Abbruch bei sehr vielen Teilsummen, dann keine Satzzuordnung
            return None
    treffer = [(s, m, n) for s, (m, n) in summen.items() if passt(s)]
    if len(treffer) != 1 or treffer[0][2] != 1:
        return None
    return treffer[0][1]


def erkenne(text: str) -> Vorschlag:
    """Vorschlag aus dem Rechnungstext (pdfplumber mit/ohne Layout oder Texterkennung)."""
    zeilen = [z.rstrip() for z in text.splitlines() if z.strip()]
    v = Vorschlag()
    eindeutig = {}
    v.nummer, v.fundstellen["nummer"], eindeutig["nummer"] = _nummer(zeilen)
    v.datum, v.fundstellen["datum"], eindeutig["datum"] = _datumsfeld(
        zeilen, DATUM_LABEL, DATUM_NICHT, DATUM_STARK, v.fundstellen["nummer"], brief=True)
    v.leistungsdatum, v.fundstellen["leistungsdatum"], _ = _datumsfeld(zeilen, LEISTUNG_LABEL)
    v.faellig, v.fundstellen["faellig"], _ = _datumsfeld(zeilen, FAELLIG_LABEL)
    v.kaeufer, v.fundstellen["kaeufer"] = _kaeufer(text.splitlines())

    # Positionen: Zeilen in Tabellen (nach einer Kopfzeile) bzw. ohne Kopfzeile nur arithmetisch geprüfte.
    # Steht der Betrag erst in der Folgezeile (Umbruch in der Position), werden bis zu zwei Zeilen verbunden.
    kopf = [len(set(w.lower() for w in KOPF_WORT.findall(z))) >= 2 and not betraege(z) for z in zeilen]
    mit_kopf = any(kopf)
    pos: list[_Zeile] = []
    belegt: set[int] = set()
    in_tabelle = not mit_kopf
    for i, z in enumerate(zeilen):
        if i in belegt:
            continue
        if kopf[i]:
            in_tabelle = True
            continue
        if not in_tabelle:
            continue
        art = _art(z)
        if art == "U":
            continue
        if art in ("N", "B") and re.search(r"(?i)(?:brutto|netto|einzel)preis", z):
            continue     # „Bruttopreis: 9,9000“ unter einer Position: Stückpreisangabe, kein Summenblock
        if art in ("N", "B", "T", "S") or FUSS.search(z) or (mit_kopf and pos and re.match(r"\s*[^\W\d][\w-]+:\s*$", z)):
            in_tabelle = not mit_kopf      # Summenblock, Fußzeile oder neuer Abschnitt („Zahlungsbedingungen:“)
            continue
        p = _position(i, z)
        if p is None and zahlen(z):
            for k in (1, 2):
                folge = zeilen[i + 1:i + 1 + k]
                if len(folge) < k or not betraege(folge[-1]) or any(_art(f) for f in folge) or \
                        any((q := _position(i, f)) and q.geprueft for f in folge):
                    continue
                if (q := _position(i + k, z + "   " + "   ".join(folge))) and q.geprueft:
                    p = q
                    belegt.update(range(i + 1, i + 1 + k))
                    break
        if p and (p.geprueft or (art is None and mit_kopf)):
            pos.append(p)
            belegt.add(i)
        elif p is None and pos and mit_kopf and pos[-1].i >= i - 8 and not re.search(r"\d+[.,]\d{2}\b", z):
            pos[-1].bezeichnung = _anfuegen(pos[-1].bezeichnung, " ".join(z.split())).strip()
    if any(p.geprueft for p in pos):
        ungeprueft = [p for p in pos if not p.geprueft]
        pos = [p for p in pos if p.geprueft]
    else:
        ungeprueft = []

    # Summenblock: alle Zeilen ab der ersten Position, die keine geprüfte Position sind
    ab = min([p.i for p in pos], default=0)
    zone = [(i, zeilen[i], _art(zeilen[i])) for i in range(ab, len(zeilen)) if i not in {p.i for p in pos}]
    steuern: dict[Decimal, tuple[Decimal, Decimal | None, str, bool]] = {}
    for i, z, art in zone:
        if art == "T" and (s := _steuerzeile(z)):
            steuern[_satz(s[0])] = (s[1], s[2], z.strip(), bool(ENTHALTEN.search(z)))
    kand = {k: [(i, betraege(z)[-1].wert, z.strip()) for i, z, art in zone if art == k and betraege(z)]
            for k in "NBSRZ"}
    ust = sum((s[0] for s in steuern.values()), Decimal(0))
    paar = None
    for i_n, n, zn in reversed(kand["N"]):
        for i_b, b, zb in kand["B"]:
            if steuern and n + ust == b and i_b > i_n:
                paar = (n, zn, b, zb, i_n)
                break
        if paar:
            break
    if not paar and not steuern and kand["B"]:
        i_b, b, zb = kand["B"][-1] if not kand["N"] else next(
            ((x, y, zz) for x, y, zz in kand["B"] if y == kand["N"][-1][1]), (None, None, None))
        if b is not None and (KLEINUNTERNEHMER.search(text) or kand["N"]):
            paar = (b, kand["N"][-1][2] if kand["N"] else zb, b, zb, kand["N"][-1][0] if kand["N"] else i_b)
            steuern[Decimal(0)] = (Decimal("0.00"), None, "", False)
    if not paar and steuern and kand["B"] and not kand["N"]:
        basen = [s[1] for s in steuern.values()]
        i_b, b, zb = kand["B"][-1]
        if all(x is not None for x in basen) and sum(basen) + ust == b:
            paar = (b - ust, "berechnet: Brutto − Steuer", b, zb, i_b)
    if paar:
        v.summe_netto, v.fundstellen["summe_netto"], v.summe_brutto, v.fundstellen["summe_brutto"], _ = paar
    else:
        if kand["N"]:
            _, v.summe_netto, v.fundstellen["summe_netto"] = kand["N"][-1]
        if kand["B"]:
            stark = [b for b in kand["B"] if BRUTTO_STARK.search(b[2])] or kand["B"]
            _, v.summe_brutto, v.fundstellen["summe_brutto"] = stark[-1]
    v.steuern = {s: w[0] for s, w in steuern.items()}
    if v.steuern:
        v.summe_ust = ust
        v.fundstellen["steuern"] = " | ".join(w[2] for w in steuern.values() if w[2])
    if kand["S"]:
        _, v.summe_ust, v.fundstellen["summe_ust"] = kand["S"][-1]

    # Nachlässe/Zuschläge zwischen Positionen und Netto, nur wenn die Rechnung damit aufgeht
    nl = []
    for k in "RZ":
        for i, w, z in kand[k]:
            if SUMMENWORT.search(z) or not w:
                continue
            satz = next((_satz(x.wert) for x in zahlen(z) if x.prozent and _satz(x.wert) in v.steuern), None) \
                if STEUER_WORT.search(z) else None
            nl.append(Nachlass(abs(w), " ".join(re.sub(r"[-−]?\d[\d.,]*\s*%?|€|EUR|\(\w\)", "", z).split()), satz, k == "Z"))
    summe_pos = sum((p.netto for p in pos), Decimal(0))
    ziel = v.summe_netto
    if ziel is not None and nl and summe_pos - sum(n.betrag for n in nl if not n.zuschlag) \
            + sum(n.betrag for n in nl if n.zuschlag) == ziel:
        v.nachlaesse = nl
    korrektur = sum((n.betrag for n in v.nachlaesse if not n.zuschlag), Decimal(0)) \
        - sum((n.betrag for n in v.nachlaesse if n.zuschlag), Decimal(0))
    if ziel is not None and ungeprueft and summe_pos - korrektur != ziel \
            and summe_pos + sum(p.netto for p in ungeprueft) - korrektur == ziel:
        pos = sorted(pos + ungeprueft, key=lambda p: p.i)
    brutto_pos = (v.summe_brutto is not None and v.summe_brutto != v.summe_netto and pos
                  and sum(p.netto for p in pos) == v.summe_brutto)

    # Steuersätze der Positionen: aus der Zeile, bei einem Satz dieser, sonst eindeutige Teilmenge zu den Basen
    saetze = [s for s in v.steuern if s > 0] or list(v.steuern)
    zuordnung: list[Decimal | None] = []
    for p in pos:
        s = [_satz(x) for x in p.saetze if _satz(x) in v.steuern]
        zuordnung.append(s[-1] if s else (saetze[0] if len(saetze) == 1 else None))
    if None in zuordnung and len(saetze) == 2 and not v.nachlaesse and not brutto_pos:
        offen = [k for k, s in enumerate(zuordnung) if s is None]
        r1, r2 = saetze
        fest = {r: sum((pos[k].netto for k, s in enumerate(zuordnung) if s == r), Decimal(0)) for r in saetze}
        rest = sum(pos[k].netto for k in offen)
        b1 = steuern[r1][1]

        def passt(s):
            if b1 is not None:
                return fest[r1] + s == b1
            return (abs(runde((fest[r1] + s) * r1 / 100) - v.steuern[r1]) <= CENT and
                    abs(runde((fest[r2] + rest - s) * r2 / 100) - v.steuern[r2]) <= CENT)
        if (maske := _teilmenge([pos[k].netto for k in offen], passt)) is not None:
            for n, k in enumerate(offen):
                zuordnung[k] = r1 if maske >> n & 1 else r2
    for n, (p, s) in enumerate(zip(pos, zuordnung), 1):
        ep = p.einzelpreis if p.rabatt is None or p.menge == 0 else (p.netto / p.menge).quantize(Decimal("0.0001"))
        # ponytail: Positionsrabatt steckt im effektiven Einzelpreis; Feld für Rabatt erst, wenn der Lernmodus es braucht
        v.positionen.append(Position(str(n), p.bezeichnung, p.menge, EINHEITEN.get(p.einheit.lower(), "C62"),
                                     ep, p.netto, s if s is not None else Decimal(-1)))

    # Bestätigung
    fehlt = [f for f in ("nummer", "datum", "summe_netto", "summe_brutto") if getattr(v, f) in (None, "")]
    if fehlt:
        v.grund = f"nicht gefunden: {', '.join(fehlt)}"
    elif eindeutig["nummer"]:
        v.grund = eindeutig["nummer"]
    elif not eindeutig["datum"]:
        v.grund = "Rechnungsdatum mehrdeutig"
    elif v.summe_brutto < 0:
        v.grund = "negative Summen (Gutschrift/Storno): Vorzeichen für die E-Rechnung prüfen"
    elif brutto_pos:
        v.grund = "Positionen mit Bruttopreisen (inkl. USt.): Netto je Position nicht gedruckt"
    elif any(s is None for s in zuordnung):
        v.grund = "Steuersatz der Positionen nicht eindeutig"
    else:
        try:
            summenabgleich(Rechnung(v.nummer, v.datum, Partei(""), v.kaeufer or Partei(""), v.positionen,
                                    v.summe_netto, v.summe_brutto, v.summe_ust, v.steuern, v.leistungsdatum,
                                    v.faellig, nachlaesse=v.nachlaesse))
            v.bestaetigt = True
        except ValueError as e:
            v.grund = str(e)
    for p in v.positionen:
        if p.ust_satz == -1:
            p.ust_satz = None
    v.fundstellen = {k: w for k, w in v.fundstellen.items() if w}
    return v


def _punkte(v: Vorschlag) -> int:
    return sum(x not in (None, "") for x in (v.nummer, v.datum, v.summe_netto, v.summe_brutto)) + bool(v.positionen)


def vorschlag_aus_pdf(pdf: Path, ocr: Callable[[Path], Iterable[tuple[str, str]]] | None = None) -> Vorschlag:
    """Text (mit und ohne Layout) bzw. Lesarten der Texterkennung; die erste bestätigte Lesart gewinnt, sonst die
    mit den meisten gefundenen Feldern. Bei Texterkennung muss die Nummer zweimal im Text stehen (Gegenprobe)."""
    text = pdf_text(pdf)
    vorschlaege = []
    if len(re.findall(r"\w", text)) >= MIN_ZEICHEN:
        for name, t in (("Layout", lambda: pdf_text(pdf, layout=True)), ("Text", lambda: text)):
            v = erkenne(t())
            v.lesart = name
            if v.bestaetigt:
                return v
            vorschlaege.append(v)
    elif ocr is None:
        return Vorschlag(grund="kein Text im PDF (als Bild gedruckt?), Texterkennung nicht verfügbar")
    else:
        lesarten = iter(ocr(pdf))
        try:
            for name, t in lesarten:
                v = erkenne(t)
                v.lesart = f"Texterkennung {name}"
                if v.bestaetigt and len(re.findall(rf"(?<![\w-]){re.escape(v.nummer)}(?![\w-])", t)) < 2:
                    v.bestaetigt, v.grund = False, "Texterkennung: Rechnungsnummer ohne Gegenprobe (nur einmal im Text)"
                if v.bestaetigt:
                    return v
                vorschlaege.append(v)
        except ValueError as e:
            if not vorschlaege:
                return Vorschlag(grund=str(e))
        finally:
            getattr(lesarten, "close", lambda: None)()
    return max(vorschlaege, key=_punkte) if vorschlaege else Vorschlag(grund="Texterkennung ohne Ergebnis")
