"""Rechnungsmodell (Decimal) und Pflicht-Summenabgleich (Spezifikation Abschnitt 8)."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
ZWEI = Decimal("0.01")
CENT = Decimal("0.01")
def runde(x: Decimal) -> Decimal:
    return x.quantize(ZWEI, rounding=ROUND_HALF_UP)
def betrag(text: str) -> Decimal:
    """Deutscher Betrag: Tausenderpunkt/Leerzeichen, Dezimalkomma, optional €/EUR.
    Texterkennung: Ein Punkt vor genau zwei Endziffern ist das Dezimalzeichen (Tausenderpunkte stehen vor drei)."""
    t = re.sub(r"€|EUR|\s", "", text)
    t = t[:-3].replace(".", "") + "," + t[-2:] if re.search(r"\.\d{2}$", t) else t
    t = t.replace(".", "").replace(",", ".")
    try:
        d = Decimal(t)
    except InvalidOperation:
        raise ValueError(f"kein Betrag: {text!r}") from None
    if not d.is_finite():
        raise ValueError(f"kein Betrag: {text!r}")
    return d
def datum(text: str) -> date:
    return datetime.strptime(text.strip().replace("O", "0"), "%d.%m.%Y").date()  # O statt 0 (Texterkennung)
def de(x: Decimal) -> str:
    """Betrag für Fehlermeldungen: 1.234,56"""
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
@dataclass
class Partei:
    name: str
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    land: str = "DE"
    ust_id: str = ""
    steuernummer: str = ""
    email: str = ""
    iban: str = ""
    bic: str = ""
@dataclass
class Position:
    nr: str
    bezeichnung: str
    menge: Decimal
    einheit: str          # UN/ECE Rec 20, z. B. HUR, H87, C62
    einzelpreis: Decimal
    netto: Decimal
    ust_satz: Decimal
@dataclass
class Rechnung:
    nummer: str
    datum: date
    verkaeufer: Partei
    kaeufer: Partei
    positionen: list[Position]
    summe_netto: Decimal
    summe_brutto: Decimal
    summe_ust: Decimal | None = None
    steuern: dict[Decimal, Decimal] = field(default_factory=dict)  # Satz -> gedruckter Steuerbetrag
    leistungsdatum: date | None = None
    faellig: date | None = None
    waehrung: str = "EUR"
    vorlage: str = ""
    ocr_text: str = ""    # gesetzt, wenn per Texterkennung gelesen
class SummenFehler(ValueError):
    pass
def summenabgleich(r: Rechnung) -> dict[Decimal, tuple[Decimal, Decimal]]:
    """Prüft alle Summen; liefert {Satz: (Basis, Steuer)} für die XML oder wirft SummenFehler."""
    if not r.positionen:
        raise SummenFehler("keine Positionen erkannt")
    basis: dict[Decimal, Decimal] = {}
    for p in r.positionen:
        if p.ust_satz <= 0:
            raise SummenFehler(f"Position {p.nr}: Steuersatz 0 % wird im ersten Wurf nicht unterstützt")
        if abs(runde(p.menge * p.einzelpreis) - p.netto) > CENT:
            raise SummenFehler(f"Position {p.nr}: Menge × Einzelpreis = {de(runde(p.menge * p.einzelpreis))} ≠ {de(p.netto)}")
        basis[p.ust_satz] = basis.get(p.ust_satz, Decimal(0)) + p.netto
    summe = sum(basis.values(), Decimal(0))
    if summe != r.summe_netto:
        raise SummenFehler(f"Netto: Positionen {de(summe)} ≠ Rechnung {de(r.summe_netto)}")
    ergebnis = {}
    for satz, b in basis.items():
        steuer = runde(b * satz / 100)
        if satz in r.steuern:
            if abs(r.steuern[satz] - steuer) > CENT:
                raise SummenFehler(f"Umsatzsteuer {satz} %: berechnet {de(steuer)} ≠ Rechnung {de(r.steuern[satz])}")
            steuer = r.steuern[satz]
        ergebnis[satz] = (b, steuer)
    ust = sum((s for _, s in ergebnis.values()), Decimal(0))
    if r.summe_ust is not None and ust != r.summe_ust:
        raise SummenFehler(f"Umsatzsteuer: berechnet {de(ust)} ≠ Rechnung {de(r.summe_ust)}")
    if r.summe_netto + ust != r.summe_brutto:
        raise SummenFehler(f"Brutto: {de(r.summe_netto)} + {de(ust)} ≠ Rechnung {de(r.summe_brutto)}")
    return ergebnis
