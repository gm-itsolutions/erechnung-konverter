"""Test-Rechnungen in fremden Layouts (nicht Lexware/GM IT): Testdaten für den Lernmodus (docs/lernmodus/)
und Gegenprobe, dass der Konverter fremde Layouts sauber abweist.

Alle Firmen, Personen und Adressen sind frei erfunden. IBANs sind veröffentlichte Test-IBANs,
USt-IdNr. und Steuernummern Testmuster. Deterministisch (fester Seed): gleiche Ausgabe bei jedem Lauf.

Erzeugen:     /root/.venvs/erechnung/bin/python werkzeuge/fremdrechnungen.py [--ziel DIR] [--layout A ...] [--ohne-bild] [--varianten N]
Gegenprobe:   /root/.venvs/erechnung/bin/python werkzeuge/fremdrechnungen.py --gegenprobe [--ziel DIR]
Je Rechnung <layout>-<n>.pdf und <layout>-<n>.soll.json, je Layout zusätzlich <layout>-1-bild.pdf (200 dpi, ohne Text).
"""
import argparse, json, random, subprocess, sys, tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

ZIEL = Path("/root/erechnung-testdaten/fremd")
SEED = 20261102
ANZAHL = 3            # Exemplare je Layout (Lernmodus braucht mindestens 2 Muster)
BILD_DPI = 200
FEST = datetime(2026, 11, 2).timetuple()   # PIL erwartet struct_time
TEILBAR = {"Std", "Std.", "m³", "m²", "lfm", "km"}   # Einheiten mit Dezimalmengen
W, H = A4
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember")
KUNDEN = [  # frei erfunden
    {"name": "Bäckerei Quandt OHG", "strasse": "Am Mühlenteich 7", "plz": "19357", "ort": "Kleinow-Süd"},
    {"name": "Praxis Dr. Henrike Voss", "strasse": "Lindenallee 23a", "plz": "16866", "ort": "Kyritz-Ausbau"},
    {"name": "Autohaus Pelzer & Lüdtke GmbH", "strasse": "Gewerbering 4", "plz": "14641", "ort": "Neuwerder"},
    {"name": "Ferienhof Sandkrug GbR", "strasse": "Dorfstraße 112", "plz": "16909", "ort": "Wittstock-Heide"},
    {"name": "Steuerkanzlei Albrecht Dunst", "strasse": "Marktplatz 2", "plz": "19348", "ort": "Großwalde"},
]
LIEFERORTE = [  # E: ablenkende zweite Anschrift
    {"name": "Baustelle Lagerhalle Nord", "strasse": "Hafenweg 9", "plz": "19322", "ort": "Elbhagen"},
    {"name": "Filiale Bahnhofstraße", "strasse": "Bahnhofstraße 40", "plz": "16928", "ort": "Kemnitz-Dorf"},
]


def runde(x: D) -> D:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def eur(x: D) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def zahl(m: D) -> str:
    s = f"{m:f}"
    return (s.rstrip("0").rstrip(".") if "." in s else s).replace(".", ",")


def tmj(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def summen(posten: list[dict], rabatt_prozent: D | None) -> dict:
    """Netto je Position gerundet, Rabatt auf die Zwischensumme, Steuer je Satz auf die Summe des Satzes."""
    zwischen = sum((p["netto"] for p in posten), D("0"))
    basis = defaultdict(lambda: D("0"))
    for p in posten:
        basis[p["satz"]] += p["netto"]
    rabatt = runde(zwischen * rabatt_prozent / 100) if rabatt_prozent else D("0")
    if rabatt:
        assert len(basis) == 1, "Rabatt nur bei einem Steuersatz eindeutig"
        basis[next(iter(basis))] -= rabatt
    steuern = {s: runde(b * s / 100) for s, b in sorted(basis.items())}
    netto = zwischen - rabatt
    return {"zwischensumme": zwischen, "rabatt": rabatt, "netto": netto, "basis": dict(sorted(basis.items())),
            "steuern": steuern, "brutto": netto + sum(steuern.values(), D("0"))}


def summen_brutto(posten: list[dict]) -> dict:
    """Positionen sind Bruttobeträge: Steuer je Satz aus der Bruttosumme herausgerechnet (Satz/(100+Satz))."""
    brutto_basis = defaultdict(lambda: D("0"))
    for p in posten:
        brutto_basis[p["satz"]] += p["netto"]
    steuern = {s: runde(b * s / (100 + s)) for s, b in sorted(brutto_basis.items())}
    basis = {s: b - steuern[s] for s, b in sorted(brutto_basis.items())}
    netto = sum(basis.values(), D("0"))
    return {"zwischensumme": netto, "rabatt": D("0"), "netto": netto, "basis": basis, "steuern": steuern,
            "brutto": netto + sum(steuern.values(), D("0"))}


# --- Zeichenhilfen (y in mm von oben) ---------------------------------------------------------------------------

def t(c: Canvas, x, y, s, font="Helvetica", size=9, rechts=False, mitte=False):
    c.setFont(font, size)
    f = c.drawRightString if rechts else c.drawCentredString if mitte else c.drawString
    f(x * mm, H - y * mm, s)


def linie(c: Canvas, x0, y0, x1, y1, w=0.5):
    c.setLineWidth(w)
    c.line(x0 * mm, H - y0 * mm, x1 * mm, H - y1 * mm)


def kasten(c: Canvas, x, y, b, h, grau=None):
    if grau is not None:
        c.setFillGray(grau)
    c.rect(x * mm, H - (y + h) * mm, b * mm, h * mm, fill=grau is not None, stroke=grau is None)
    c.setFillGray(0)


def zeilen(c: Canvas, x, y, liste, abstand=4.2, **kw):
    for i, s in enumerate(liste):
        t(c, x, y + i * abstand, s, **kw)


def anschrift(k: dict) -> list[str]:
    return [k["name"], k["strasse"], f"{k['plz']} {k['ort']}"]


# --- Layouts ----------------------------------------------------------------------------------------------------

def zeichne_a(c: Canvas, r: dict):
    """Handwerker: Kopf links, Rechnungsdaten-Kasten rechts, Tabelle mit Linien, Menge|Einheit|Bezeichnung|EP|Gesamt."""
    v = r["v"]
    t(c, 20, 22, v["name"], "Helvetica-Bold", 16)
    zeilen(c, 20, 28, [v["inhaber"], v["strasse"], f"{v['plz']} {v['ort']}", f"Tel. {v['tel']}"], size=9)
    t(c, 20, 50, f"{v['name']} · {v['strasse']} · {v['plz']} {v['ort']}", size=6.5)
    zeilen(c, 20, 56, anschrift(r["kaeufer"]), 5, size=10.5)
    kasten(c, 120, 45, 70, 30)
    for i, (k, w) in enumerate([("Rechnungsnr.:", r["nummer"]), ("Rechnungsdatum:", tmj(r["datum"])),
                                ("Kundennr.:", r["kundennr"]), ("Leistungsdatum:", tmj(r["leistungsdatum"]))]):
        t(c, 123, 52 + i * 6, k, size=9)
        t(c, 187, 52 + i * 6, w, "Helvetica-Bold", 9, rechts=True)
    t(c, 20, 92, "RECHNUNG", "Helvetica-Bold", 14)
    t(c, 20, 100, "Für die ausgeführten Arbeiten berechnen wir Ihnen wie folgt:", size=9.5)
    kanten = [20, 36, 52, 128, 158, 190]
    y = 106
    kasten(c, 20, y, 170, 7, grau=0.85)
    for x, k, re in zip(kanten, ["Menge", "Einheit", "Bezeichnung", "Einzelpreis", "Gesamt"], [0, 0, 0, 1, 1]):
        t(c, x + 2 if not re else kanten[kanten.index(x) + 1] - 2, y + 5, k, "Helvetica-Bold", 9, rechts=bool(re))
    y += 7
    for p in r["positionen"]:
        teile = simpleSplit(p["bezeichnung"], "Helvetica", 9, (kanten[3] - kanten[2] - 4) * mm)
        h = 3 + 4.2 * len(teile)
        t(c, 34, y + 5, zahl(p["menge"]), rechts=True)
        t(c, 38, y + 5, p["einheit"])
        zeilen(c, 54, y + 5, teile)
        t(c, 156, y + 5, eur(p["einzelpreis"]), rechts=True)
        t(c, 188, y + 5, eur(p["netto"]), rechts=True)
        y += h
        linie(c, 20, y, 190, y, 0.3)
    for x in kanten:
        linie(c, x, 106, x, y, 0.3)
    linie(c, 20, 106, 190, 106, 0.3)
    s = r["summen"]
    y += 8
    for k, w, f in [("Zwischensumme (netto)", eur(s["zwischensumme"]), "Helvetica"),
                    *[(f"zzgl. {zahl(sz)} % MwSt.", eur(b), "Helvetica") for sz, b in s["steuern"].items()],
                    ("Rechnungsbetrag", eur(s["brutto"]) + " EUR", "Helvetica-Bold")]:
        t(c, 128, y, k, f, 10)
        t(c, 188, y, w, f, 10, rechts=True)
        y += 6
    linie(c, 128, y - 10, 190, y - 10, 0.8)
    t(c, 20, y + 6, f"Zahlbar innerhalb von {r['ziel']} Tagen ohne Abzug.", size=9.5)
    t(c, 20, y + 11, "Vielen Dank für Ihren Auftrag!", size=9.5)
    fuss(c, v, 282)


def fuss(c: Canvas, v: dict, y: float, size=7):
    linie(c, 20, y - 4, 190, y - 4, 0.3)
    t(c, 20, y, f"{v['bank']} · IBAN {v['iban']} · BIC {v['bic']}", size=size)
    t(c, 20, y + 3.5, f"{v['name']} · {v['inhaber']} · USt-IdNr. {v['ust_id']}", size=size)


def b_eur(x: D) -> str:
    return "€ " + eur(x)


def zeichne_b(c: Canvas, r: dict):
    """Online-Tool-Stil: Tabelle ohne Linien, „€“ vorne, Summenkasten unten rechts, 19 % und 7 % getrennt."""
    v = r["v"]
    c.setFillColorRGB(0.10, 0.45, 0.55)
    t(c, 190, 22, v["name"].split()[0].lower() + ".", "Helvetica-Bold", 22, rechts=True)
    c.setFillGray(0)
    t(c, 20, 47, f"{v['name']}, {v['strasse']}, {v['plz']} {v['ort']}", size=7)
    zeilen(c, 20, 53, anschrift(r["kaeufer"]), 4.6, size=10)
    meta = [("Rechnungsnummer", r["nummer"]), ("Rechnungsdatum", tmj(r["datum"])),
            ("Lieferdatum", tmj(r["leistungsdatum"])), ("Ihre Kundennummer", r["kundennr"])]
    for i, (k, w) in enumerate(meta):
        t(c, 130, 53 + i * 5, k, size=8.5)
        t(c, 190, 53 + i * 5, w, size=8.5, rechts=True)
    t(c, 20, 90, f"Rechnung {r['nummer']}", "Helvetica-Bold", 15)
    t(c, 20, 99, "Hallo, vielen Dank für Ihre Bestellung. Wir stellen Ihnen folgende Leistungen in Rechnung:", size=9)
    sp = [(20, "Pos.", 0), (32, "Beschreibung", 0), (130, "Menge", 1), (155, "Preis", 1), (170, "USt.", 1),
          (190, "Betrag", 1)]
    y = 110
    for x, k, re in sp:
        t(c, x, y, k, "Helvetica-Bold", 8.5, rechts=bool(re))
    y += 7
    for i, p in enumerate(r["positionen"], 1):
        t(c, 20, y, str(i))
        t(c, 32, y, p["bezeichnung"])
        t(c, 130, y, f"{zahl(p['menge'])} {p['einheit']}", rechts=True)
        t(c, 155, y, b_eur(p["einzelpreis"]), rechts=True)
        t(c, 170, y, f"{zahl(p['satz'])} %", rechts=True)
        t(c, 190, y, b_eur(p["netto"]), rechts=True)
        y += 6.5
    s = r["summen"]
    reihen = [("Gesamt netto", b_eur(s["netto"]))]
    reihen += [(f"zzgl. USt. {zahl(sz)} % auf {b_eur(s['basis'][sz])}", b_eur(st)) for sz, st in s["steuern"].items()]
    y = max(y + 8, 200)
    kasten(c, 105, y, 87, 7 * len(reihen) + 12, grau=0.93)
    for i, (k, w) in enumerate(reihen):
        t(c, 108, y + 6 + i * 7, k, size=9)
        t(c, 189, y + 6 + i * 7, w, size=9, rechts=True)
    yb = y + 6 + len(reihen) * 7 + 2
    t(c, 108, yb, "Gesamt brutto", "Helvetica-Bold", 10.5)
    t(c, 189, yb, b_eur(s["brutto"]), "Helvetica-Bold", 10.5, rechts=True)
    t(c, 20, yb + 16, f"Zahlungsbedingungen: {r['ziel']} Tage netto. Bitte geben Sie die Rechnungsnummer an.", size=9)
    zeilen(c, 20, 276, [v["name"], v["strasse"], f"{v['plz']} {v['ort']}"], 3.3, size=7)
    zeilen(c, 80, 276, [f"Inhaber: {v['inhaber']}", f"USt-IdNr.: {v['ust_id']}", f"E-Mail: {v['email']}"], 3.3, size=7)
    zeilen(c, 140, 276, [v["bank"], f"IBAN: {v['iban']}", f"BIC: {v['bic']}"], 3.3, size=7)


def zeichne_c(c: Canvas, r: dict):
    """Word-Vorlage: Fließtext-Kopf, Datum ausgeschrieben, Tabelle Pos.|Beschreibung|Betrag, „Zu zahlender Betrag“."""
    v, f, fb = r["v"], "Times-Roman", "Times-Bold"
    t(c, W / mm / 2, 20, v["name"], fb, 15, mitte=True)
    t(c, W / mm / 2, 26, f"{v['inhaber']} · {v['strasse']} · {v['plz']} {v['ort']} · {v['email']}", f, 9, mitte=True)
    linie(c, 25, 29, 185, 29, 0.4)
    zeilen(c, 25, 48, anschrift(r["kaeufer"]), 5, font=f, size=11)
    d = r["datum"]
    t(c, 185, 75, f"{v['ort']}, {d.day}. {MONATE[d.month - 1]} {d.year}", f, 11, rechts=True)
    t(c, 25, 88, f"Rechnung Nr. {r['nummer']}", fb, 13)
    zeilen(c, 25, 98, ["Sehr geehrte Damen und Herren,", "",
                       "für meine Leistungen im vergangenen Monat erlaube ich mir, Ihnen Folgendes zu berechnen:"],
           5, font=f, size=11)
    y = 118
    linie(c, 25, y, 185, y)
    t(c, 27, y + 5, "Pos.", fb, 11)
    t(c, 40, y + 5, "Beschreibung", fb, 11)
    t(c, 183, y + 5, "Betrag", fb, 11, rechts=True)
    y += 7
    linie(c, 25, y, 185, y)
    for i, p in enumerate(r["positionen"], 1):
        teile = simpleSplit(p["bezeichnung"], f, 11, 120 * mm)
        t(c, 27, y + 5.5, f"{i}.", f, 11)
        zeilen(c, 40, y + 5.5, teile, 5, font=f, size=11)
        t(c, 183, y + 5.5, eur(p["netto"]) + " €", f, 11, rechts=True)
        y += 3 + 5 * len(teile)
    linie(c, 25, y + 1, 185, y + 1)
    s = r["summen"]
    y += 8
    for k, w, ff in [("Summe netto", eur(s["netto"]) + " €", f),
                     *[(f"zuzüglich {zahl(sz)} % Umsatzsteuer", eur(st) + " €", f) for sz, st in s["steuern"].items()],
                     ("Zu zahlender Betrag", eur(s["brutto"]) + " €", fb)]:
        t(c, 110, y, k, ff, 11)
        t(c, 183, y, w, ff, 11, rechts=True)
        y += 6
    zeilen(c, 25, y + 8, [f"Bitte überweisen Sie den Betrag innerhalb von {r['ziel']} Tagen auf das unten genannte Konto.",
                          "", "Mit freundlichen Grüßen", "", v["inhaber"]], 5, font=f, size=11)
    zeilen(c, 25, 275, [f"Bankverbindung: {v['bank']}, IBAN {v['iban']}, BIC {v['bic']}",
                        f"Steuernummer {v['steuernr']} · USt-IdNr. {v['ust_id']}"], 4, font=f, size=8.5)


D_ERSTE, D_FOLGE = 13, 17   # Positionen auf Seite 1 bzw. Folgeseiten (35 Positionen → 3 Seiten)


def d_seiten(n: int) -> int:
    return 1 + max(0, -(-(n - D_ERSTE) // D_FOLGE))


def zeichne_d(c: Canvas, r: dict):
    """Mehrseitig: wiederholter Tabellenkopf, Übertrag, „Seite x von y“, verkürzter Kopf auf Folgeseiten."""
    v, pos = r["v"], r["positionen"]
    seiten = d_seiten(len(pos))
    sp = [(20, "Pos", 0), (30, "Art.-Nr.", 0), (52, "Artikel", 0), (138, "Menge", 1), (141, "ME", 0),
          (170, "Preis/ME", 1), (190, "Betrag", 1)]
    lauf, i = D("0"), 0
    for seite in range(1, seiten + 1):
        if seite == 1:
            t(c, 20, 20, v["name"], "Helvetica-Bold", 14)
            t(c, 20, 25, f"{v['strasse']} · {v['plz']} {v['ort']} · Tel. {v['tel']}", size=8)
            zeilen(c, 20, 45, anschrift(r["kaeufer"]), 4.6, size=10)
            for j, (k, w) in enumerate([("Rechnung", r["nummer"]), ("Datum", tmj(r["datum"])),
                                        ("Kunde", r["kundennr"]), ("Lieferschein", r["lieferschein"])]):
                t(c, 135, 45 + j * 5, k + ":", size=9)
                t(c, 190, 45 + j * 5, w, size=9, rechts=True)
            t(c, 20, 78, f"Rechnung {r['nummer']}", "Helvetica-Bold", 13)
            y, n = 88, D_ERSTE
        else:
            t(c, 20, 18, f"{v['name']} · Rechnung {r['nummer']} vom {tmj(r['datum'])}", "Helvetica-Bold", 9)
            linie(c, 20, 21, 190, 21, 0.3)
            y, n = 30, D_FOLGE
            t(c, 120, y, "Übertrag von Seite " + str(seite - 1), "Helvetica-Oblique", 9)
            t(c, 190, y, eur(lauf), "Helvetica-Oblique", 9, rechts=True)
            y += 7
        kasten(c, 20, y - 4.5, 170, 6.5, grau=0.88)
        for x, k, re in sp:
            t(c, x, y, k, "Helvetica-Bold", 8.5, rechts=bool(re))
        y += 7
        for p in pos[i:i + n]:
            i += 1
            t(c, 20, y, str(i), size=8.5)
            t(c, 30, y, p["artnr"], size=8.5)
            t(c, 52, y, p["bezeichnung"], size=8.5)
            t(c, 138, y, zahl(p["menge"]), size=8.5, rechts=True)
            t(c, 141, y, p["einheit"], size=8.5)
            t(c, 170, y, eur(p["einzelpreis"]), size=8.5, rechts=True)
            t(c, 190, y, eur(p["netto"]), size=8.5, rechts=True)
            lauf += p["netto"]
            y += 9.5 if seite == 1 else 12
        linie(c, 120, y - 4, 190, y - 4, 0.3)
        if seite < seiten:
            t(c, 120, y + 1, "Übertrag", "Helvetica-Oblique", 9)
            t(c, 190, y + 1, eur(lauf), "Helvetica-Oblique", 9, rechts=True)
        else:
            s = r["summen"]
            for k, w, f in [("Warenwert netto", eur(s["netto"]), "Helvetica"),
                            *[(f"MwSt. {zahl(sz)} %", eur(st), "Helvetica") for sz, st in s["steuern"].items()],
                            ("Endbetrag EUR", eur(s["brutto"]), "Helvetica-Bold")]:
                y += 6
                t(c, 120, y, k, f, 9.5)
                t(c, 190, y, w, f, 9.5, rechts=True)
            t(c, 20, y + 12, f"Zahlbar bis {tmj(r['faellig'])} ohne Abzug. Es gelten unsere AGB.", size=9)
        t(c, W / mm / 2, 287, f"Seite {seite} von {seiten}", size=8, mitte=True)
        fuss(c, v, 278, 6.5)
        c.showPage()


def zeichne_e(c: Canvas, r: dict):
    """Schmale Ränder (8 mm), zweispaltiger Kopf mit ablenkender Lieferanschrift, Rabatt %/Betrag, Menge 2,5 Std."""
    v, L, R = r["v"], 8, 202
    kasten(c, L, 8, R - L, 16, grau=0.2)
    c.setFillGray(1)
    t(c, L + 3, 18, v["name"], "Helvetica-Bold", 13)
    t(c, R - 3, 18, f"{v['strasse']} | {v['plz']} {v['ort']} | {v['tel']}", size=8, rechts=True)
    c.setFillGray(0)
    t(c, L, 32, "Rechnungsempfänger", "Helvetica-Bold", 8)
    zeilen(c, L, 37, anschrift(r["kaeufer"]), 4.4, size=9.5)
    t(c, 108, 32, "Lieferanschrift / Leistungsort", "Helvetica-Bold", 8)
    zeilen(c, 108, 37, anschrift(r["lieferort"]), 4.4, size=9.5)
    y = 58
    linie(c, L, y - 4.5, R, y - 4.5, 0.3)
    felder = [("Beleg-Nr.", r["nummer"]), ("Belegdatum", tmj(r["datum"])), ("Kunden-Nr.", r["kundennr"]),
              ("Leistung", tmj(r["leistungsdatum"])), ("Seite", "1")]
    for j, (k, w) in enumerate(felder):
        t(c, L + j * 39, y, k, size=7.5)
        t(c, L + j * 39, y + 4.5, w, "Helvetica-Bold", 9.5)
    linie(c, L, y + 7, R, y + 7, 0.3)
    t(c, L, y + 18, "Rechnung", "Helvetica-Bold", 12)
    sp = [(L, "Nr", 0), (L + 10, "Leistung", 0), (150, "Menge", 1), (153, "Einh.", 0), (180, "Preis", 1),
          (R, "Summe", 1)]
    y += 27
    for x, k, re in sp:
        t(c, x, y, k, "Helvetica-Bold", 8.5, rechts=bool(re))
    linie(c, L, y + 2, R, y + 2, 0.3)
    y += 7
    for i, p in enumerate(r["positionen"], 1):
        t(c, L, y, f"{i:02d}", size=8.5)
        t(c, L + 10, y, p["bezeichnung"], size=8.5)
        t(c, 150, y, zahl(p["menge"]), size=8.5, rechts=True)
        t(c, 153, y, p["einheit"], size=8.5)
        t(c, 180, y, eur(p["einzelpreis"]), size=8.5, rechts=True)
        t(c, R, y, eur(p["netto"]), size=8.5, rechts=True)
        y += 5.5
    linie(c, L, y - 2, R, y - 2, 0.3)
    s, (sz, st) = r["summen"], next(iter(r["summen"]["steuern"].items()))
    y += 5
    for k, w, f in [("Summe Positionen", eur(s["zwischensumme"]), "Helvetica"),
                    (f"abzüglich {zahl(r['rabatt_prozent'])} % Rabatt", "-" + eur(s["rabatt"]), "Helvetica"),
                    ("Nettobetrag", eur(s["netto"]), "Helvetica-Bold"),
                    (f"Umsatzsteuer {zahl(sz)} %", eur(st), "Helvetica"),
                    ("Gesamtbetrag EUR", eur(s["brutto"]), "Helvetica-Bold")]:
        t(c, 130, y, k, f, 9)
        t(c, R, y, w, f, 9, rechts=True)
        y += 5
    t(c, L, y + 6, f"Zahlungsziel: {r['ziel']} Tage. Leistungsort ist die oben genannte Lieferanschrift.", size=8.5)
    zeilen(c, L, 284, [f"{v['name']} · Inh. {v['inhaber']} · USt-IdNr. {v['ust_id']} · {v['email']}",
                       f"{v['bank']} · IBAN {v['iban']} · BIC {v['bic']}"], 3.5, size=7)


def zeichne_f(c: Canvas, r: dict):
    """Kleinunternehmer § 19 UStG: keine Umsatzsteuer (Satz 0, Grenzfall)."""
    v = r["v"]
    t(c, 20, 25, v["name"], "Helvetica-Bold", 18)
    t(c, 20, 31, v["inhaber"] + " – " + v["zusatz"], "Helvetica-Oblique", 10)
    zeilen(c, 140, 22, [v["strasse"], f"{v['plz']} {v['ort']}", v["tel"], v["email"]], 4.2, size=8.5)
    zeilen(c, 20, 55, anschrift(r["kaeufer"]), 5, size=10.5)
    t(c, 20, 85, "Rechnung", "Helvetica-Bold", 14)
    zeilen(c, 20, 93, [f"Rechnungsnummer: {r['nummer']}", f"Rechnungsdatum: {tmj(r['datum'])}",
                       f"Leistungszeitraum: {tmj(r['leistungsdatum'])}"], 5, size=10)
    sp = [(20, "Leistung", 0), (130, "Anzahl", 1), (160, "Einzelpreis", 1), (190, "Gesamtpreis", 1)]
    y = 118
    for x, k, re in sp:
        t(c, x, y, k, "Helvetica-Bold", 9.5, rechts=bool(re))
    linie(c, 20, y + 2, 190, y + 2, 0.8)
    y += 8
    for p in r["positionen"]:
        t(c, 20, y, p["bezeichnung"], size=9.5)
        t(c, 130, y, f"{zahl(p['menge'])} {p['einheit']}", size=9.5, rechts=True)
        t(c, 160, y, eur(p["einzelpreis"]) + " €", size=9.5, rechts=True)
        t(c, 190, y, eur(p["netto"]) + " €", size=9.5, rechts=True)
        y += 6.5
    linie(c, 20, y - 3, 190, y - 3, 0.8)
    t(c, 130, y + 3, "Gesamtbetrag", "Helvetica-Bold", 11)
    t(c, 190, y + 3, eur(r["summen"]["brutto"]) + " €", "Helvetica-Bold", 11, rechts=True)
    zeilen(c, 20, y + 16, ["Gemäß § 19 UStG wird keine Umsatzsteuer berechnet (Kleinunternehmerregelung).",
                           f"Bitte überweisen Sie den Gesamtbetrag innerhalb von {r['ziel']} Tagen.",
                           "", "Herzlichen Dank!"], 5, size=10)
    zeilen(c, 20, 278, [f"{v['bank']} · IBAN {v['iban']} · BIC {v['bic']}", f"Steuernummer: {v['steuernr']}"],
           3.8, size=7.5)


def zeichne_g(c: Canvas, r: dict):
    """Farbband-Kopf, Nummer mit Buchstaben/Schrägstrich, Datum TT.MM.JJ, Fälligkeitsdatum, 19 % und 7 % gemischt."""
    v = r["v"]
    c.setFillColorRGB(0.18, 0.42, 0.22)
    c.rect(0, H - 34 * mm, W, 34 * mm, fill=1, stroke=0)
    c.setFillGray(1)
    t(c, 20, 17, v["name"], "Helvetica-Bold", 15)
    t(c, 20, 24, f"{v['strasse']} · {v['plz']} {v['ort']} · {v['tel']} · {v['email']}", size=8.5)
    c.setFillGray(0)
    zeilen(c, 20, 50, anschrift(r["kaeufer"]), 4.8, size=10)
    meta = [("Rechnung", r["nummer"]), ("vom", r["datum"].strftime("%d.%m.%y")), ("Kunden-Nr.", r["kundennr"]),
            ("Fällig am", tmj(r["faellig"]))]
    for j, (k, w) in enumerate(meta):
        t(c, 135, 50 + j * 5.5, k, size=9)
        t(c, 190, 50 + j * 5.5, w, "Helvetica-Bold", 9, rechts=True)
    t(c, 20, 84, "Rechnung " + r["nummer"], "Helvetica-Bold", 13)
    sp = [(20, "Bezeichnung", 0), (115, "Menge", 1), (118, "Einheit", 0), (155, "Einzelpreis €", 1),
          (170, "MwSt %", 1), (190, "Netto €", 1)]
    y = 96
    c.setFillColorRGB(0.18, 0.42, 0.22)
    for x, k, re in sp:
        t(c, x, y, k, "Helvetica-Bold", 8.5, rechts=bool(re))
    c.setFillGray(0)
    y += 7
    for i, p in enumerate(r["positionen"]):
        if i % 2:
            kasten(c, 19, y - 4.2, 172, 6, grau=0.94)
        t(c, 20, y, p["bezeichnung"], size=8.5)
        t(c, 115, y, zahl(p["menge"]), size=8.5, rechts=True)
        t(c, 118, y, p["einheit"], size=8.5)
        t(c, 155, y, eur(p["einzelpreis"]), size=8.5, rechts=True)
        t(c, 170, y, zahl(p["satz"]), size=8.5, rechts=True)
        t(c, 190, y, eur(p["netto"]), size=8.5, rechts=True)
        y += 6
    s = r["summen"]
    y += 6
    for k, w, f in [("Summe netto", eur(s["netto"]), "Helvetica"),
                    *[(f"MwSt. {zahl(sz)} % aus {eur(s['basis'][sz])}", eur(st), "Helvetica")
                      for sz, st in s["steuern"].items()],
                    ("Rechnungsbetrag", eur(s["brutto"]), "Helvetica-Bold")]:
        t(c, 115, y, k, f, 9.5)
        t(c, 190, y, w, f, 9.5, rechts=True)
        y += 5.5
    t(c, 20, y + 8, f"Bitte begleichen Sie den Rechnungsbetrag bis zum {tmj(r['faellig'])}.", size=9.5)
    fuss(c, v, 282)


# --- Parametrisierte Layouts H–O (Programmstile über ein Stil-Wörterbuch) ----------------------------------------

def iso(d: date) -> str:
    return d.isoformat()


def tmj_kurz(d: date) -> str:
    return d.strftime("%d.%m.%y")


def monat_kurz(d: date) -> str:
    return f"{d.day:02d}. {MONATE[d.month - 1][:3]}. {d.year}"


def monat_lang(d: date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def eur_hinten(x: D) -> str:
    return eur(x) + " EUR"


def eur_roh(x: D) -> str:
    """Ohne Tausenderpunkt, Komma als Dezimaltrenner."""
    return f"{x:.2f}".replace(".", ",")


def eur_roh_hinten(x: D) -> str:
    return eur_roh(x) + " EUR"


def seitenzahl_p(n: int, erste: int, folge: int) -> int:
    return 1 + max(0, -(-(n - erste) // folge))


def zelle(key: str, p: dict, i: int, G) -> str:
    return {"pos": str(i), "artnr": p.get("artnr", ""), "bez": p["bezeichnung"], "menge": zahl(p["menge"]),
            "me": p["einheit"], "ep": G(p["einzelpreis"]), "rab": f"{zahl(p['rabatt'])} %" if p.get("rabatt") else "",
            "gesamt": G(p["netto"]), "satz": zahl(p["satz"])}[key]


def zeichne_p(c: Canvas, r: dict):
    """Gemeinsamer Zeichner für H–O: Kopf, Rechnungsdaten, Tabelle (auch mehrseitig), Summenzeilen laut Stil."""
    st, v, pos = r["stil"], r["v"], r["positionen"]
    f, fb, g, G, GS = st["font"], st["fontb"], st["gr"], st["geld"], st["geld_sum"]
    seiten = seitenzahl_p(len(pos), st["erste"], st["folge"])
    lauf, i = D("0"), 0
    for seite in range(1, seiten + 1):
        if seite == 1:
            if st["kopf"] == "band":
                c.setFillColorRGB(*st["farbe"])
                c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
                c.setFillGray(1)
                t(c, 20, 14, v["name"], fb, 15)
                t(c, 20, 21, f"{v['strasse']} · {v['plz']} {v['ort']} · {v['email']}", f, 8)
                c.setFillGray(0)
            elif st["kopf"] == "mitte":
                t(c, W / mm / 2, 18, v["name"], fb, 14, mitte=True)
                t(c, W / mm / 2, 24, f"{v['strasse']}, {v['plz']} {v['ort']} – Tel. {v['tel']}", f, 8, mitte=True)
                linie(c, 20, 27, 190, 27, 0.4)
            else:
                t(c, 20, 18, v["name"], fb, 14)
                zeilen(c, 20, 24, [v["strasse"], f"{v['plz']} {v['ort']}", f"Tel. {v['tel']}"], 3.8, font=f, size=8)
            zeilen(c, 20, 48, anschrift(r["kaeufer"]), 4.8, font=f, size=g + 1)
            meta = st["meta"](r)
            if st["metaform"] == "kasten":
                kasten(c, 125, 42, 65, 5 + 5 * len(meta))
                for j, (k, w) in enumerate(meta):
                    t(c, 128, 48 + j * 5, k, f, g - 0.5)
                    t(c, 187, 48 + j * 5, w, fb, g - 0.5, rechts=True)
                y = 48 + 5 * len(meta) + 20
            else:
                for j, (k, w) in enumerate(meta):
                    t(c, 20 + j * 170 / len(meta), 76, k, f, g - 1.5)
                    t(c, 20 + j * 170 / len(meta), 80.5, w, fb, g)
                y = 96
            t(c, 20, y - 5, f"{st['titel']} {st['nr_label']} {r['nummer']}" if st["titel_nr"] else st["titel"], fb, g + 4)
            for j, z in enumerate(st["vorzeile"](r)):
                t(c, 20, y + 1 + j * 4.5, z, f, g)
            y += 5 + 4.5 * len(st["vorzeile"](r))
            n = st["erste"]
        else:
            t(c, 20, 16, f"{v['name']} · {st['nr_label']} {r['nummer']} vom {st['datum'](r['datum'])}", fb, g)
            linie(c, 20, 19, 190, 19, 0.3)
            t(c, 120, 28, "Übertrag", f, g)
            t(c, 190, 28, GS(lauf), f, g, rechts=True)
            y, n = 38, st["folge"]
        kasten(c, 20, y - 4.5, 170, 6.5, grau=st.get("kopfgrau", 0.88))
        for key, titel, x, re in st["spalten"]:
            t(c, x, y, titel, fb, g - 0.5, rechts=bool(re))
        y += 7
        for p in pos[i:i + n]:
            i += 1
            for key, titel, x, re in st["spalten"]:
                t(c, x, y, zelle(key, p, i, G), f, g - 0.5, rechts=bool(re))
            lauf += p["netto"]
            y += st["zeile"]
        linie(c, 20, y - 3.5, 190, y - 3.5, 0.3)
        if seite < seiten:
            t(c, 120, y + 1, "Übertrag", f, g)
            t(c, 190, y + 1, GS(lauf), f, g, rechts=True)
        else:
            y += 3
            for k, w, fett in st["summen"](r["summen"], GS):
                t(c, 110, y, k, fb if fett else f, g)
                t(c, 190, y, w, fb if fett else f, g, rechts=True)
                y += 5.2
            for j, z in enumerate(st["schluss"](r)):
                t(c, 20, y + 6 + j * 4.5, z, f, g - 0.5)
        if seiten > 1:
            t(c, W / mm / 2, 288, st["seitentext"].format(s=seite, n=seiten), f, 8, mitte=True)
        fuss(c, v, 280, 6.5)
        c.showPage()


def firma(name, inhaber, strasse, plz, ort, iban, bic, bank, **rest):
    return {"name": name, "inhaber": inhaber, "strasse": strasse, "plz": plz, "ort": ort, "iban": iban, "bic": bic,
            "bank": bank, "tel": "0000 123456", "email": "rechnung@example.org", "ust_id": "DE123456789",
            "steuernr": "000/000/00000", **rest}


def katalog(*zeilen_):  # (Bezeichnung, Einheit, Einzelpreis, Satz)
    return [(b, e, D(p), D(s)) for b, e, p, s in zeilen_]


def _d_katalog():
    basis = [("Kopierpapier A4 80 g", "Pak", "4.85"), ("Ordner breit", "Stk", "2.39"), ("Kugelschreiber blau", "Stk", "0.89"),
             ("Haftnotizen 76x76", "Blk", "1.15"), ("Toner Laser schwarz", "Stk", "64.90"), ("Briefumschlag C4", "Pak", "7.40"),
             ("Klarsichthülle", "Pak", "3.25"), ("Textmarker gelb", "Stk", "0.95"), ("Heftklammern 24/6", "Pak", "1.20"),
             ("Locher 30 Blatt", "Stk", "9.80"), ("Etiketten 70x36", "Pak", "12.60"), ("Archivkarton", "Stk", "3.70")]
    var = ["", " grau", " rot", " recycling"]
    return [(f"{b}{z}", e, D(p), D("19"), f"{100 + i * 7:05d}-{j}") for i, (b, e, p) in enumerate(basis)
            for j, z in enumerate(var)]



def kat(*zeilen_):  # wie katalog, zusätzlich Artikelnummer als 5. Wert
    return [(b, e, D(pr), D(sz), f"A-{1000 + i * 17}") for i, (b, e, pr, sz) in enumerate(zeilen_)]


def _st(**kw):
    basis = {"font": "Helvetica", "fontb": "Helvetica-Bold", "gr": 9, "geld": eur, "geld_sum": eur, "datum": tmj,
             "kopf": "einfach", "farbe": (0.2, 0.2, 0.5), "metaform": "kasten", "titel": "Rechnung", "titel_nr": True,
             "nr_label": "Nr.", "erste": 40, "folge": 40, "zeile": 6, "seitentext": "Seite {s} von {n}",
             "vorzeile": lambda r: [], "schluss": lambda r: [f"Zahlbar innerhalb von {r['ziel']} Tagen ohne Abzug."]}
    return {**basis, **kw}


def _meta(nr, dat="Datum", extra=()):
    return lambda r: [(nr, r["nummer"]), (dat, r["stil"]["datum"](r["datum"])), ("Kunden-Nr.", r["kundennr"]),
                      *[(k, fn(r)) for k, fn in extra]]


def _steuerzeilen(fmt):
    return lambda s, G: [(fmt(sz, s["basis"][sz], st, G), G(st), False) for sz, st in s["steuern"].items()]


def _summen_netto(l_netto, fmt, l_brutto):
    def f(s, G):
        return [(l_netto, G(s["netto"]), False), *_steuerzeilen(fmt)(s, G), (l_brutto, G(s["brutto"]), True)]
    return f


def _summen_brutto(s, G):
    return [("Gesamtbetrag brutto", G(s["brutto"]), True), *[(f"darin enthaltene MwSt {zahl(sz)} %", G(st), False)
            for sz, st in s["steuern"].items()], ("Nettobetrag", G(s["netto"]), False)]


def _summen_klein(s, G):
    return [("Rechnungsbetrag", G(s["brutto"]), True)]


SP_VOLL = [("pos", "Pos", 20, 0), ("artnr", "Art.-Nr.", 29, 0), ("bez", "Bezeichnung", 49, 0), ("menge", "Menge", 117, 1),
           ("me", "ME", 119, 0), ("ep", "EP", 144, 1), ("rab", "Rabatt %", 163, 1), ("gesamt", "Gesamt", 190, 1)]


LAYOUTS = {
    "A": {"titel": "Handwerker, Datenkasten rechts, Tabelle mit Linien, Menge|Einheit|Bezeichnung|EP|Gesamt",
          "zeichne": zeichne_a, "nummer": lambda n: f"2026-{311 + n * 4}", "ziel": 14, "pos": (3, 6),
          "v": firma("Tischlerei Brandhorst", "Meister Jörg Brandhorst", "Sägewerkstraße 3", "16949", "Holzhausen-Ost",
                     "DE89370400440532013000", "COBADEFFXXX", "Testbank Nord"),
          "katalog": katalog(("Einbauschrank Flur, Eiche massiv, nach Aufmaß gefertigt inklusive Montage vor Ort", "Stk", "1840.00", "19"),
                             ("Arbeitszeit Geselle", "Std", "58.50", "19"), ("Arbeitszeit Meister", "Std", "72.00", "19"),
                             ("Zimmertür Buche, Zarge und Drückergarnitur", "Stk", "489.00", "19"),
                             ("Fensterbank innen Marmor 1,20 m", "Stk", "96.40", "19"), ("Kleinmaterial", "psch", "23.80", "19"),
                             ("Anfahrt", "psch", "35.00", "19"), ("Entsorgung Altholz", "m³", "41.00", "19")),
          "mengen": ["1", "1", "2", "3", "4.5", "7.25"]},
    "B": {"titel": "Online-Tool-Stil, Tabelle ohne Linien, € vorne, Summenkasten, 19 % und 7 % getrennt",
          "zeichne": zeichne_b, "nummer": lambda n: f"B-{10421 + n}", "ziel": 10, "pos": (4, 7),
          "v": firma("Kantwerk Medienhaus UG", "Lea Kantorek", "Speicherhof 12", "14776", "Brandenhain",
                     "DE02500105170137075030", "INGDDEFFXXX", "Musterbank Digital"),
          "katalog": katalog(("Fachbuch Netzwerktechnik", "Stk", "39.90", "7"), ("Broschüre Druck 500 Ex.", "Stk", "0.84", "19"),
                             ("Layout-Pauschale", "Std", "65.00", "19"), ("E-Book Lizenz", "Stk", "12.50", "7"),
                             ("Zeitschrift Jahresabo", "Stk", "54.00", "7"), ("Webhosting Paket M", "Mon", "9.90", "19"),
                             ("Fotoretusche", "Std", "48.00", "19"), ("Kalender 2027", "Stk", "14.95", "7")),
          "mengen": ["1", "2", "3", "5", "12"]},
    "C": {"titel": "Word-Vorlage, Datum ausgeschrieben, Pos.|Beschreibung|Betrag, „Zu zahlender Betrag“",
          "zeichne": zeichne_c, "nummer": lambda n: f"2026-{814 + n:04d}", "ziel": 30, "pos": (2, 5),
          "v": firma("Lektorat Lindqvist", "Anna Lindqvist", "Lindenhain 8", "16818", "Lindenhain",
                     "DE02100500000054540402", "BELADEBEXXX", "Testsparkasse Ost", email="buero@example.org"),
          "katalog": katalog(("Lektorat Jahresbericht 2026, 84 Normseiten, inklusive zweiter Korrekturrunde", "", "1260.00", "19"),
                             ("Übersetzung Produktbroschüre Deutsch–Schwedisch", "", "945.50", "19"),
                             ("Korrektorat Website-Texte", "", "310.00", "19"),
                             ("Redaktionelle Beratung (Telefontermine Oktober)", "", "180.00", "19"),
                             ("Pauschale Satzkorrektur Druckvorlage", "", "95.00", "19")),
          "mengen": ["1"]},
    "D": {"titel": "Mehrseitig (3 Seiten), wiederholter Tabellenkopf, Übertrag, Seite x von y, kurzer Folgekopf",
          "zeichne": zeichne_d, "nummer": lambda n: f"471{n}-26", "ziel": 21, "pos": (33, 37),
          "v": firma("Elbtal Bürobedarf Wiesner KG", "Geschäftsführer Tobias Wiesner", "Am Güterbahnhof 15", "19309",
                     "Elbtal-Süd", "DE02300209000106531065", "CMCIDEDDXXX", "Beispielbank West"),
          "katalog": _d_katalog(), "mengen": ["1", "2", "3", "5", "10", "25"]},
    "E": {"titel": "Schmale Ränder, zweispaltiger Kopf mit Lieferanschrift, Rabatt in % und Betrag, Menge 2,5 Std.",
          "zeichne": zeichne_e, "nummer": lambda n: f"RE{88420 + n}", "ziel": 7, "pos": (4, 6), "rabatt": D("5"),
          "v": firma("Nordlicht Systemhaus Kröger e.K.", "Sven Kröger", "Leuchtturmweg 2", "19395", "Seeblick",
                     "DE02120300000000202051", "BYLADEM1001", "Testbank Mitte"),
          "katalog": katalog(("Netzwerkinstallation Techniker", "Std.", "84.00", "19"), ("Patchkabel Cat6a 2 m", "Stk.", "4.90", "19"),
                             ("Switch 24 Port verwaltet", "Stk.", "389.00", "19"), ("Fahrtkosten", "km", "0.65", "19"),
                             ("Dokumentation Netzplan", "Std.", "72.00", "19"), ("Datendose Unterputz", "Stk.", "18.30", "19"),
                             ("Fehlersuche Verkabelung", "Std.", "84.00", "19")),
          "mengen": ["1", "2.5", "1.5", "4", "6", "120"]},
    "F": {"titel": "Kleinunternehmer § 19 UStG, keine Umsatzsteuer (Grenzfall Satz 0)",
          "zeichne": zeichne_f, "nummer": lambda n: f"F{26050 + n}", "ziel": 14, "pos": (2, 4),
          "v": firma("Fotografie Mira Szabo", "Mira Szabo", "Atelierhof 5", "16928", "Kemnitz-Dorf",
                     "DE89370400440532013000", "COBADEFFXXX", "Testbank Nord", zusatz="Fotografie & Bildbearbeitung"),
          "katalog": katalog(("Fotoshooting Mitarbeiterporträts", "Std", "85.00", "0"), ("Bildbearbeitung je Bild", "Stk", "6.50", "0"),
                             ("Anfahrt pauschal", "psch", "30.00", "0"), ("Nutzungsrecht Website", "psch", "150.00", "0"),
                             ("Fotobuch A4 Hardcover", "Stk", "64.00", "0")),
          "mengen": ["1", "2", "3", "24", "40"]},
    "G": {"titel": "Farbband-Kopf, Nummer RG-2026/117, Datum TT.MM.JJ, Fälligkeitsdatum, 19 % und 7 % gemischt",
          "zeichne": zeichne_g, "nummer": lambda n: f"RG-2026/{116 + n}", "faellig_tage": 14, "pos": (4, 7),
          "v": firma("Havelgrün Garten- und Landschaftsbau GmbH", "GF Petra Holm", "Gärtnerweg 21", "14715", "Havelaue",
                     "DE02500105170137075030", "INGDDEFFXXX", "Musterbank Digital"),
          "katalog": katalog(("Rasenpflege inkl. Vertikutieren", "Std", "52.00", "19"), ("Heckenschnitt Liguster", "lfm", "6.80", "19"),
                             ("Rhododendron 40-50 cm", "Stk", "24.90", "7"), ("Rindenmulch 40 l", "Sack", "5.95", "7"),
                             ("Obstbaum Halbstamm", "Stk", "79.00", "7"), ("Grünschnittentsorgung", "m³", "28.00", "19"),
                             ("Pflasterarbeiten Gehweg", "m²", "46.50", "19"), ("Blumenzwiebeln Mischung", "Pak", "8.40", "7")),
          "mengen": ["1", "2", "3", "5", "8", "12.5"]},
    "H": {"titel": "Kassen-/Warenwirtschaftsstil (Courier), Beleg-Nr., ISO-Datum, Positionsrabatt, MwSt 19 % auf …, 19/7 gemischt",
          "zeichne": zeichne_p, "nummer": lambda n: f"B{260400 + n * 7}", "ziel": 14, "pos": (4, 9), "pos_rabatt": True,
          "stil": _st(font="Courier", fontb="Courier-Bold", gr=8.5, datum=iso, nr_label="Beleg-Nr.", titel="Beleg",
                      titel_nr=False, spalten=SP_VOLL, metaform="zeile", zeile=5.5,
                      meta=_meta("Beleg-Nr.", "Belegdatum"),
                      summen=_summen_netto("Summe netto", lambda sz, b, st, G: f"MwSt {zahl(sz)} % auf {G(b)}", "Summe brutto")),
          "v": firma("Getränke Rehfeld e.K.", "Inh. Uwe Rehfeld", "Dorfplatz 1", "19339", "Rehfeld", "DE02500105170137075030",
                     "INGDDEFFXXX", "Musterbank Digital"),
          "katalog": kat(("Mineralwasser 12x0,7 l", "Kst", "7.49", "19"), ("Apfelsaft naturtrüb 6x1 l", "Kst", "9.90", "19"),
                         ("Bio-Landbrot 750 g", "Stk", "3.60", "7"), ("Eier Freiland 10er", "Pak", "3.10", "7"),
                         ("Bier Pils 20x0,5 l", "Kst", "15.99", "19"), ("Kaffee Bohnen 1 kg", "Pak", "13.80", "7"),
                         ("Pfand Kasten", "Stk", "1.50", "19"), ("Butter 250 g", "Stk", "2.39", "7"),
                         ("Reinigungsmittel 5 l", "Kan", "11.40", "19")),
          "mengen": ["1", "2", "3", "6", "10"]},
    "I": {"titel": "Englische Beschriftung (Invoice No., VAT … on …), ISO-Datum, Beträge mit EUR hinten, Farbband-Kopf",
          "zeichne": zeichne_p, "nummer": lambda n: f"INV-2026-{1040 + n}", "ziel": 30, "pos": (3, 6),
          "stil": _st(kopf="band", farbe=(0.55, 0.12, 0.12), datum=iso, geld=eur, geld_sum=eur_hinten, titel="Invoice",
                      nr_label="No.", metaform="zeile",
                      spalten=[("pos", "Item", 20, 0), ("bez", "Description", 32, 0), ("menge", "Qty", 118, 1),
                               ("me", "Unit", 121, 0), ("ep", "Unit price", 156, 1), ("gesamt", "Amount", 190, 1)],
                      meta=_meta("Invoice No.", "Invoice date", [("Due date", lambda r: iso(r["faellig"]))]),
                      summen=_summen_netto("Net amount", lambda sz, b, st, G: f"VAT {zahl(sz)} % on {G(b)}", "Total amount due"),
                      schluss=lambda r: [f"Payment terms: {r['ziel']} days net. Please quote the invoice number."]),
          "v": firma("Ostsee Marine Supply GmbH", "MD Karsten Brandt", "Kai 4", "17033", "Neubrandenhagen",
                     "DE89370400440532013000", "COBADEFFXXX", "Testbank Nord"),
          "katalog": katalog(("Anchor line 20 m", "pcs", "84.00", "19"), ("Fender set large", "set", "129.50", "19"),
                             ("Consulting hours", "h", "95.00", "19"), ("Chart table", "pcs", "42.90", "19"),
                             ("Rigging service", "h", "78.00", "19")),
          "mengen": ["1", "2", "4", "8"]},
    "J": {"titel": "„Rechnung Nr.“, Datum TT.MM.JJ, Beträge ohne Tausenderpunkt mit EUR hinten, Steuerzeile „19 % MwSt: …“",
          "zeichne": zeichne_p, "nummer": lambda n: f"{2026}{n:04d}", "ziel": 14, "pos": (3, 6),
          "stil": _st(datum=tmj_kurz, geld=eur_roh, geld_sum=eur_roh_hinten, nr_label="Nr.", metaform="kasten",
                      spalten=[("menge", "Menge", 36, 1), ("me", "Einh.", 39, 0), ("bez", "Bezeichnung", 56, 0),
                               ("ep", "Einzelpreis", 158, 1), ("gesamt", "Gesamtpreis", 190, 1)],
                      meta=_meta("Rechnung Nr.", "Datum"),
                      summen=_summen_netto("Zwischensumme", lambda sz, b, st, G: f"{zahl(sz)} % MwSt:", "Rechnungsbetrag")),
          "v": firma("Metallbau Oderbruch Pohl", "Dirk Pohl", "Werkstattgasse 6", "15324", "Oderbruch-Nord",
                     "DE02100500000054540402", "BELADEBEXXX", "Testsparkasse Ost"),
          "katalog": katalog(("Stahltreppe feuerverzinkt", "Stk", "4890.00", "19"), ("Geländer Edelstahl", "lfm", "212.00", "19"),
                             ("Schweißarbeiten vor Ort", "Std", "69.00", "19"), ("Carport Konstruktion", "Stk", "3350.00", "19"),
                             ("Kran und Transport", "psch", "640.00", "19"), ("Stahlträger IPE 200", "lfm", "58.40", "19")),
          "mengen": ["1", "2", "6", "12"]},
    "K": {"titel": "Brutto-Positionen mit enthaltener MwSt (Preise inkl.), Datum mit Monatsnamen, Summe darin enthaltener MwSt",
          "zeichne": zeichne_p, "nummer": lambda n: f"R-{7300 + n * 3}", "ziel": 7, "pos": (3, 7), "brutto": True,
          "stil": _st(font="Times-Roman", fontb="Times-Bold", gr=10, datum=monat_lang, nr_label="Nr.", metaform="zeile",
                      spalten=[("pos", "Pos.", 20, 0), ("bez", "Leistung", 32, 0), ("menge", "Anz.", 128, 1),
                               ("ep", "Preis inkl. MwSt", 158, 1), ("gesamt", "Gesamt inkl.", 190, 1)],
                      meta=_meta("Rechnungsnummer", "Rechnungsdatum"), summen=_summen_brutto,
                      vorzeile=lambda r: ["Alle Preise verstehen sich inklusive der gesetzlichen Mehrwertsteuer."]),
          "v": firma("Café & Bistro Seeblick", "Hanna Wöhler", "Uferpromenade 9", "17192", "Waren-Ufer",
                     "DE02300209000106531065", "CMCIDEDDXXX", "Beispielbank West"),
          "katalog": katalog(("Catering Buffet pro Person", "Pers", "24.50", "7"), ("Getränkepauschale", "Pers", "11.90", "19"),
                             ("Saalmiete", "psch", "250.00", "19"), ("Torte nach Wunsch", "Stk", "68.00", "7"),
                             ("Servicepersonal", "Std", "29.00", "19"), ("Blumendeko Tische", "psch", "85.00", "19")),
          "mengen": ["1", "2", "20", "35", "50"]},
    "L": {"titel": "Gutschrift (Storno) mit Bezug auf eine Rechnung, negative Mengen und Beträge",
          "zeichne": zeichne_p, "nummer": lambda n: f"GS-26-{120 + n}", "ziel": 14, "pos": (2, 4), "gutschrift": True,
          "stil": _st(titel="Gutschrift", nr_label="Nr.", metaform="kasten",
                      spalten=[("pos", "Pos", 20, 0), ("bez", "Bezeichnung", 30, 0), ("menge", "Menge", 120, 1),
                               ("ep", "Einzelpreis", 154, 1), ("gesamt", "Betrag", 190, 1)],
                      meta=_meta("Gutschrift-Nr.", "Datum"),
                      vorzeile=lambda r: [f"Gutschrift zu Rechnung {r['bezug_nummer']} vom {tmj(r['bezug_datum'])}"],
                      summen=_summen_netto("Gutschrift netto", lambda sz, b, st, G: f"MwSt {zahl(sz)} % auf {G(b)}",
                                           "Gutschriftbetrag"),
                      schluss=lambda r: ["Der Betrag wird mit Ihrer nächsten Rechnung verrechnet oder erstattet."]),
          "v": firma("Funk & Sicherheit Dommer GmbH", "GF Ines Dommer", "Antennenstraße 3", "19288", "Ludwigsfeld",
                     "DE02120300000000202051", "BYLADEM1001", "Testbank Mitte"),
          "katalog": katalog(("Funkmelder Rauch", "Stk", "39.90", "19"), ("Montage Melder", "Std", "64.00", "19"),
                             ("Zentrale Alarm 8 Zonen", "Stk", "412.00", "19"), ("Wartungsvertrag Quartal", "psch", "180.00", "19")),
          "mengen": ["1", "2", "3"]},
    "M": {"titel": "Tabelle Pos|Art.-Nr.|Bezeichnung|Menge|ME|EP|Rabatt %|Gesamt, Datum „02. Nov. 2026“, Rechnung Nr., Positionsrabatt, 19/7 gemischt",
          "zeichne": zeichne_p, "nummer": lambda n: f"RE-26-{3100 + n}", "ziel": 21, "pos": (5, 9), "pos_rabatt": True,
          "stil": _st(kopf="mitte", datum=monat_kurz, nr_label="Nr.", spalten=SP_VOLL, metaform="kasten",
                      meta=_meta("Rechnung Nr.", "Datum", [("Lieferschein", lambda r: r["lieferschein"])]),
                      summen=_summen_netto("Nettosumme", lambda sz, b, st, G: f"zzgl. {zahl(sz)} % MwSt auf {G(b)}",
                                           "Zahlbetrag")),
          "v": firma("Agrarhandel Prignitz GmbH", "GF Frank Lemke", "Silostraße 11", "16928", "Pritzhagen",
                     "DE89370400440532013000", "COBADEFFXXX", "Testbank Nord"),
          "katalog": kat(("Saatgut Raps 25 kg", "Sack", "168.00", "7"), ("Düngemittel NPK 50 kg", "Sack", "42.50", "19"),
                         ("Pflanzenschutz 10 l", "Kan", "96.80", "19"), ("Futtergerste 1 t", "t", "215.00", "7"),
                         ("Strohballen Rund", "Stk", "28.00", "7"), ("Silofolie 12x50 m", "Rol", "184.00", "19"),
                         ("Arbeitshandschuhe", "Paar", "6.90", "19"), ("Weidezaundraht 250 m", "Rol", "39.90", "19"),
                         ("Mineralfutter 25 kg", "Sack", "31.40", "7")),
          "mengen": ["1", "4", "10", "24"]},
    "N": {"titel": "Mehrseitig (Blatt x/y), wenige Positionen je Seite, Übertrag, Beträge mit EUR hinten, Positionsrabatt",
          "zeichne": zeichne_p, "nummer": lambda n: f"{n:03d}/2026", "ziel": 30, "pos": (26, 34), "pos_rabatt": True,
          "stil": _st(kopf="band", farbe=(0.1, 0.1, 0.1), geld=eur, geld_sum=eur_hinten, nr_label="Nr.", spalten=SP_VOLL,
                      metaform="zeile", erste=14, folge=22, zeile=7.5, seitentext="Blatt {s}/{n}",
                      meta=_meta("Rechnungsnr.", "Rechnungsdatum"),
                      summen=_summen_netto("Netto", lambda sz, b, st, G: f"MwSt {zahl(sz)} % auf {G(b)}", "Brutto")),
          "v": firma("Heizung Sanitär Wegener & Söhne", "Bernd Wegener", "Kesselstraße 27", "14727", "Premnitz-Heide",
                     "DE02300209000106531065", "CMCIDEDDXXX", "Beispielbank West"),
          "katalog": _d_katalog(),
          "mengen": ["1", "2", "5", "10"]},
    "O": {"titel": "Kleinunternehmer § 19 UStG im Tabellenstil, ISO-Datum, EUR hinten, ohne Tausenderpunkt, Satz 0",
          "zeichne": zeichne_p, "nummer": lambda n: f"{2026}-K{n:03d}", "ziel": 10, "pos": (2, 5),
          "stil": _st(datum=iso, geld=eur_roh, geld_sum=eur_roh_hinten, nr_label="Nr.", metaform="zeile",
                      spalten=[("pos", "Pos", 20, 0), ("bez", "Leistung", 30, 0), ("menge", "Menge", 120, 1),
                               ("ep", "Preis", 154, 1), ("gesamt", "Summe", 190, 1)],
                      meta=_meta("Rechnungs-Nr.", "Rechnungsdatum"), summen=_summen_klein,
                      vorzeile=lambda r: ["Kleinunternehmer gemäß § 19 UStG, es wird keine Umsatzsteuer ausgewiesen."]),
          "v": firma("Webdesign Tilda Rehm", "Tilda Rehm", "Fliederweg 14", "16866", "Kyritz-Ausbau",
                     "DE02100500000054540402", "BELADEBEXXX", "Testsparkasse Ost"),
          "katalog": katalog(("Webseite Relaunch 5 Seiten", "psch", "1850.00", "0"), ("Pflege Webseite", "Std", "55.00", "0"),
                             ("Logo Entwurf", "psch", "420.00", "0"), ("Hosting Jahresgebühr", "Jahr", "120.00", "0"),
                             ("Schulung Redakteure", "Std", "70.00", "0")),
          "mengen": ["1", "2", "3", "8"]},
}
ERWARTET_LERNMODUS = {
    "A": "anlernbar (Bezeichnung teils zweizeilig)",
    "B": "anlernbar; Steuerzeilen mit {satz}-Anker",
    "C": "Fehler erwartet: Datum mit Monatsnamen (Lernmodus-Spezifikation 2), ohne Menge/Einzelpreis gilt Menge 1",
    "D": "anlernbar; Folgeseiten, Übertrag als ignorierte Zeile",
    "E": "anlernbar; Nachlass auf Rechnungsebene, Lieferanschrift darf nicht als Käufer gelesen werden",
    "F": "nicht anlernbar: Satz 0 / § 19 UStG wird nicht unterstützt (Schema ust_satz 0 < x <= 30)",
    "G": "anlernbar; Nummer mit / und -, Datum TT.MM.JJ, faellig statt zahlungsziel_tage",
    "H": "anlernbar; Positionsrabatt-Spalte, Steuerzeile „MwSt 19 % auf …“, ISO-Datum, Beleg-Nr.",
    "I": "Fehler erwartet: englische Beschriftung, Steuerzeile „VAT … on …“",
    "J": "anlernbar; Beträge ohne Tausenderpunkt, Steuerzeile nur „19 % MwSt:“ ohne Basis",
    "K": "Fehler erwartet: Positionen brutto (Preise inkl. MwSt), Netto nur als Rückrechnung",
    "L": "Fehler erwartet: Gutschrift mit negativen Beträgen (art gutschrift)",
    "M": "anlernbar; Datum mit abgekürztem Monatsnamen, Positionsrabatt, 19/7 gemischt",
    "N": "anlernbar; Blatt x/y, Übertrag, bis zu 3 Seiten",
    "O": "nicht anlernbar: Satz 0 / § 19 UStG (Schema ust_satz 0 < x <= 30)",
}


def rechnung(layout: str, n: int, rng: random.Random) -> dict:
    L = LAYOUTS[layout]
    datum_ = date(2026, 11, 2) + timedelta(days=rng.randrange(0, 21))
    k = min(rng.randint(*L["pos"]), len(L["katalog"]))
    posten = []
    for eintrag in rng.sample(L["katalog"], k):
        bez, einheit, ep, satz = eintrag[:4]
        menge = D(rng.choice(L["mengen"]))
        if einheit not in TEILBAR:
            menge = menge.to_integral_value(rounding=ROUND_CEILING)
        if L.get("gutschrift"):
            menge = -menge
        p = {"bezeichnung": bez, "menge": menge, "einheit": einheit, "einzelpreis": ep,
             "netto": runde(menge * ep), "satz": satz}
        if L.get("pos_rabatt"):
            rab = D(rng.choice(["0", "0", "5", "10", "15"]))
            if rab:
                p["rabatt"], p["netto"] = rab, runde(menge * ep * (100 - rab) / 100)
        if len(eintrag) > 4:
            p["artnr"] = eintrag[4]
        posten.append(p)
    if layout == "E" and not any(p["menge"] % 1 for p in posten):   # mindestens eine Dezimalmenge (2,5 Std.)
        p = next(p for p in posten if p["einheit"] == "Std.")   # E: 3 von 7 Katalogzeilen, mindestens 4 gezogen
        p["menge"], p["netto"] = D("2.5"), runde(D("2.5") * p["einzelpreis"])
    ziel = L.get("ziel")
    faellig = datum_ + timedelta(days=ziel or L["faellig_tage"])
    bezug = {"bezug_nummer": f"RE-{rng.randrange(1000, 9999)}", "bezug_datum": datum_ - timedelta(days=rng.randrange(20, 60))} \
        if L.get("gutschrift") else {}
    return {**bezug, "layout": layout, "v": L["v"], "nummer": L["nummer"](n), "datum": datum_, "stil": L.get("stil"),
            "leistungsdatum": datum_ - timedelta(days=rng.randrange(1, 10)), "faellig": faellig, "ziel": ziel,
            "kaeufer": rng.choice(KUNDEN), "lieferort": rng.choice(LIEFERORTE) if layout == "E" else None,
            "kundennr": f"K{rng.randrange(10000, 99999)}", "lieferschein": f"LS-{rng.randrange(1000, 9999)}",
            "positionen": posten, "rabatt_prozent": L.get("rabatt"),
            "summen": summen_brutto(posten) if L.get("brutto") else summen(posten, L.get("rabatt"))}


def pdf(r: dict) -> bytes:
    puffer = BytesIO()
    c = Canvas(puffer, pagesize=A4, invariant=1)   # invariant: gleiche Bytes bei jedem Lauf
    c.setTitle(f"Rechnung {r['nummer']}")
    c.setAuthor(r["v"]["name"])
    LAYOUTS[r["layout"]]["zeichne"](c, r)
    if r["layout"] != "D" and not r["stil"]:   # D und H–O schließen jede Seite selbst ab
        c.showPage()
    c.save()
    return puffer.getvalue()


def bild_pdf(daten: bytes, dpi: int = BILD_DPI) -> bytes:
    """Jede Seite als Graustufenbild, wieder als PDF, ohne Text (wie Edge-Druck auf Microsoft Print to PDF)."""
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(daten)
    bilder = [s.render(scale=dpi / 72, grayscale=True).to_pil() for s in d]
    d.close()
    puffer = BytesIO()
    bilder[0].save(puffer, format="PDF", save_all=True, append_images=bilder[1:], resolution=dpi,
                   creationDate=FEST, modDate=FEST)   # feste Zeitstempel: gleiche Bytes je Lauf
    return puffer.getvalue()


def soll(r: dict, datei: str, bild: bool, seiten: int) -> dict:
    s, txt = r["summen"], str
    pos = [{"bezeichnung": p["bezeichnung"], "menge": txt(p["menge"]), "einheit": p["einheit"] or None,
            "einzelpreis": txt(p["einzelpreis"]), "netto": txt(p["netto"]), "satz": txt(p["satz"]),
            **({"rabatt_prozent": txt(p["rabatt"])} if p.get("rabatt") else {})}
           for p in r["positionen"]]
    L = LAYOUTS[r["layout"]]
    return {"datei": datei, "layout": r["layout"], "layout_beschreibung": LAYOUTS[r["layout"]]["titel"],
            "bild_pdf": bild, "seiten": seiten, "nummer": r["nummer"], "datum": r["datum"].isoformat(),
            "leistungsdatum": r["leistungsdatum"].isoformat(), "faellig": r["faellig"].isoformat(),
            "zahlungsziel_tage": r["ziel"], "verkaeufer": r["v"]["name"], "kaeufer": r["kaeufer"],
            "lieferanschrift": r["lieferort"], "positionen": pos, "zwischensumme": txt(s["zwischensumme"]),
            "rabatt": {"prozent": txt(r["rabatt_prozent"]), "betrag": txt(s["rabatt"])} if s["rabatt"] else None,
            "netto": txt(s["netto"]), "steuern": {txt(k): txt(v) for k, v in s["steuern"].items()},
            "brutto": txt(s["brutto"]),
            "art": "gutschrift" if L.get("gutschrift") else "rechnung",
            "brutto_positionen": bool(L.get("brutto")),   # true: einzelpreis/netto der Positionen sind Bruttobeträge
            "sprache": "en" if r["layout"] == "I" else "de",
            **({"bezug_nummer": r["bezug_nummer"], "bezug_datum": r["bezug_datum"].isoformat()}
               if "bezug_nummer" in r else {}),
            "erwartet_heute": {"ergebnis": "fehler", "meldung_enthaelt": "keine Vorlage passt"},
            "erwartet_lernmodus": ERWARTET_LERNMODUS[r["layout"]]}


def seitenzahl(r: dict) -> int:
    n = len(r["positionen"])
    if r["layout"] == "D":
        return d_seiten(n)
    return seitenzahl_p(n, r["stil"]["erste"], r["stil"]["folge"]) if r["stil"] else 1


def erzeuge(ziel: Path, layouts=None, bild: bool = True, seed: int = SEED, varianten: int = 0) -> list[Path]:
    """Je Layout ANZAHL Exemplare + Bild-PDF des ersten; `varianten` weitere Exemplare (gleicher Seed-Strom, die
    ersten ANZAHL bleiben dadurch unverändert)."""
    ziel.mkdir(parents=True, exist_ok=True)
    dateien = []
    for layout in layouts or LAYOUTS:
        rng = random.Random(f"{seed}-{layout}")
        for n in range(1, ANZAHL + varianten + 1):
            r = rechnung(layout, n, rng)
            daten = pdf(r)
            seiten = seitenzahl(r)
            ausgaben = [(f"{layout}-{n}", daten, False)]
            if bild and n == 1:
                ausgaben.append((f"{layout}-{n}-bild", bild_pdf(daten), True))
            for stamm, inhalt, ist_bild in ausgaben:
                (ziel / f"{stamm}.pdf").write_bytes(inhalt)
                (ziel / f"{stamm}.soll.json").write_text(
                    json.dumps(soll(r, f"{stamm}.pdf", ist_bild, seiten), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                dateien.append(ziel / f"{stamm}.pdf")
    return dateien


def gegenprobe(ordner: Path) -> int:
    """Jede PDF durch `python -m erechnung umwandeln` mit den mitgelieferten Vorlagen (Kopie, Original bleibt).
    Erwartet überall Fehler mit „keine Vorlage passt“; eine erzeugte E-Rechnung ist ein Befund."""
    repo = Path(__file__).resolve().parents[1]
    befunde = 0
    with tempfile.TemporaryDirectory(prefix="fremd-") as tmp:
        tmp = Path(tmp)
        ordner_ = {n: tmp / n for n in ("eingang", "ausgabe", "originale", "fehler")}
        for o in ordner_.values():
            o.mkdir()
        konfig = tmp / "konfig.json"
        konfig.write_text(json.dumps({**{k: str(v) for k, v in ordner_.items()}, "verkaeufer": {
            "name": "Testverkäufer", "strasse": "Teststraße 1", "plz": "00000", "ort": "Testort", "land": "DE",
            "ust_id": "DE123456789", "email": "rechnung@example.org", "iban": "DE02120300000000202051",
            "bic": "BYLADEM1001"}}), encoding="utf-8")
        for p in sorted(ordner.glob("*.pdf")):
            e = subprocess.run([sys.executable, "-m", "erechnung", "umwandeln", str(p), "--konfig", str(konfig)],
                               cwd=repo, capture_output=True, text=True, timeout=900)
            ausgabe = (e.stdout + e.stderr).strip()
            ok = e.returncode == 1 and "keine Vorlage passt" in ausgabe and not any(ordner_["ausgabe"].iterdir())
            befunde += not ok
            print(f"{'ok    ' if ok else 'BEFUND'} {p.name}: rc={e.returncode} {ausgabe.splitlines()[0] if ausgabe else ''}")
    print(f"{befunde} Befund(e)")
    return 1 if befunde else 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--ziel", type=Path, default=ZIEL)
    a.add_argument("--layout", nargs="*", choices=sorted(LAYOUTS))
    a.add_argument("--ohne-bild", action="store_true")
    a.add_argument("--varianten", type=int, default=0, help="zusätzliche Exemplare je Layout (großer Korpus)")
    a.add_argument("--gegenprobe", action="store_true")
    x = a.parse_args()
    if x.gegenprobe:
        sys.exit(gegenprobe(x.ziel))
    for d in erzeuge(x.ziel, x.layout, not x.ohne_bild, varianten=x.varianten):
        print(d)
