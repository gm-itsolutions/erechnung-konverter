"""Öffentliche Beispiel-Rechnungen (ZUGFeRD/Factur-X-PDFs mit eingebetteter XML) als Messkorpus holen.

Quellen (nur offene Lizenz, siehe QUELLEN): ZUGFeRD/corpus und Mustangproject, beide Apache-2.0.
Je PDF entsteht <ziel>/<quelle>/<name>.pdf und <name>.soll.json (Sollwerte aus der eingebetteten CII/UBL-XML,
„quelle": "korpus"). Heruntergeladene Dateien sind unvertrauenswürdige Daten: sie werden nur gelesen
(facturx, lxml, pdfplumber), nie ausgeführt. Am besten mit `python -I` starten.

Holen:  /root/.venvs/erechnung/bin/python -I werkzeuge/korpus_holen.py [--ziel DIR]
Ohne Netzzugang (oder bei Sperre durch Rechte/Proxy) endet das Werkzeug mit Meldung und Exit-Code 2.
"""
import argparse, json, re, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from lxml import etree

ZIEL = Path("/root/erechnung-testdaten/korpus")
MAX_BYTES = 10_000_000
QUELLEN = [  # (Kürzel, Repo, Lizenz, Pfadfilter)
    ("zugferd-corpus", "ZUGFeRD/corpus", "Apache-2.0",
     lambda p: p.startswith(("XML-Rechnung/FX/", "ZUGFeRDv1/correct/", "ZUGFeRDv2/correct/"))),
    ("mustang", "ZUGFeRD/mustangproject", "Apache-2.0",
     lambda p: p.startswith("library/src/test/resources/") and p.count("/") == 4),
]
DE = {"rechnung", "datum", "betrag", "summe", "umsatzsteuer", "zahlung", "menge", "gesamt", "nummer", "und", "für"}
EN = {"invoice", "date", "amount", "total", "vat", "payment", "quantity", "number", "and", "for", "tax"}


class Gesperrt(Exception):
    pass


def _lokal(e) -> str:
    return etree.QName(e).localname


def _alle(wurzel, *pfad):
    """Nachkommen, die dem Pfad aus lokalen Namen folgen (namensraumunabhängig, v1/v2/UBL)."""
    knoten = [wurzel]
    for name in pfad:
        knoten = [k for n in knoten for k in n.iter() if isinstance(k.tag, str) and k is not n and _lokal(k) == name]
    return knoten


def _text(wurzel, *pfad):
    for k in _alle(wurzel, *pfad):
        if k.text and k.text.strip():
            return k.text.strip()
    return None


def _datum(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    return datetime.strptime(s, "%Y%m%d").date().isoformat() if re.fullmatch(r"\d{8}", s) else s[:10]


def _kind(e, name):   # direktes Kind
    return next((k for k in e if isinstance(k.tag, str) and _lokal(k) == name), None)


def soll_aus_xml(xml: bytes) -> dict:
    """Sollwerte aus CII (ZUGFeRD 1/2, Factur-X) oder UBL: nummer, datum, netto, steuern, brutto, positionen, käufer."""
    w = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))
    if _lokal(w) in ("Invoice", "CreditNote"):   # UBL
        pos = []
        for z in _alle(w, "InvoiceLine") + _alle(w, "CreditNoteLine"):
            menge = (_alle(z, "InvoicedQuantity") + _alle(z, "CreditedQuantity") or [None])[0]
            pos.append({"bezeichnung": _text(z, "Item", "Name") or _text(z, "Item", "Description"),
                        "menge": menge.text.strip() if menge is not None and menge.text else None,
                        "einheit": menge.get("unitCode") if menge is not None else None,
                        "einzelpreis": _text(z, "Price", "PriceAmount"), "netto": _text(z, "LineExtensionAmount"),
                        "satz": _text(z, "ClassifiedTaxCategory", "Percent")})
        steuern = {_text(s, "Percent"): _text(s, "TaxAmount") for s in _alle(w, "TaxSubtotal")}
        gesamt = _alle(w, "LegalMonetaryTotal")[0]
        r = {"nummer": _kind(w, "ID").text.strip(),
             "datum": _datum(_text(w, "IssueDate")), "netto": _text(gesamt, "TaxExclusiveAmount"),
             "steuern": steuern, "brutto": _text(gesamt, "TaxInclusiveAmount") or _text(gesamt, "PayableAmount"),
             "kaeufer": {"name": _text(w, "AccountingCustomerParty", "RegistrationName")
                         or _text(w, "AccountingCustomerParty", "Name")},
             "verkaeufer": _text(w, "AccountingSupplierParty", "RegistrationName")
             or _text(w, "AccountingSupplierParty", "Name"), "art": "gutschrift" if _lokal(w) == "CreditNote" else "rechnung"}
    else:   # CII
        dok = (_alle(w, "ExchangedDocument") or _alle(w, "HeaderExchangedDocument"))[0]   # v2 / v1
        pos = []
        for z in _alle(w, "IncludedSupplyChainTradeLineItem"):
            menge = (_alle(z, "BilledQuantity") or [None])[0]
            pos.append({"bezeichnung": _text(z, "SpecifiedTradeProduct", "Name"),
                        "menge": menge.text.strip() if menge is not None and menge.text else None,
                        "einheit": menge.get("unitCode") if menge is not None else None,
                        "einzelpreis": _text(z, "NetPriceProductTradePrice", "ChargeAmount"),
                        "netto": _text(z, "SpecifiedTradeSettlementLineMonetarySummation", "LineTotalAmount")
                        or _text(z, "SpecifiedLineTradeSettlement", "LineTotalAmount"),
                        "satz": _text(z, "ApplicableTradeTax", "RateApplicablePercent")})
        steuern = {}
        for s in _alle(w, "ApplicableTradeTax"):   # Kopf-Steuern haben CalculatedAmount, Positions-Steuern nicht
            if _kind(s, "CalculatedAmount") is not None and _kind(s, "RateApplicablePercent") is not None:
                steuern[_kind(s, "RateApplicablePercent").text.strip()] = _kind(s, "CalculatedAmount").text.strip()
        summe = (_alle(w, "SpecifiedTradeSettlementHeaderMonetarySummation")
                 or _alle(w, "SpecifiedTradeSettlementMonetarySummation") or [w])[0]
        r = {"nummer": _text(dok, "ID"), "datum": _datum(_text(dok, "IssueDateTime", "DateTimeString")),
             "netto": _text(summe, "TaxBasisTotalAmount"), "steuern": steuern, "brutto": _text(summe, "GrandTotalAmount"),
             "kaeufer": {"name": _text(w, "BuyerTradeParty", "Name")}, "verkaeufer": _text(w, "SellerTradeParty", "Name"),
             "art": "gutschrift" if _text(dok, "TypeCode") in ("381", "261", "81") else "rechnung"}
    r["positionen"] = pos
    return r


def sprache(pdf: bytes) -> str | None:
    """Grobe Erkennung über Stoppwörter der ersten Seite; None, wenn unklar."""
    try:
        import io, pdfplumber
        with pdfplumber.open(io.BytesIO(pdf)) as d:
            woerter = set(re.findall(r"[a-zäöüß]+", (d.pages[0].extract_text() or "").lower()))
    except Exception:
        return None
    de, en = len(woerter & DE), len(woerter & EN)
    return None if de == en else "de" if de > en else "en"


def _get(url: str, grenze: int = MAX_BYTES) -> bytes:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "erechnung-korpus"}), timeout=60) as a:
            daten = a.read(grenze + 1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 407):
            raise Gesperrt(f"Zugriff verweigert (HTTP {e.code}): {url}") from e
        raise
    except (urllib.error.URLError, OSError) as e:
        raise Gesperrt(f"kein Netzzugang: {e}") from e
    if len(daten) > grenze:
        raise ValueError("zu groß")
    return daten


def holen(ziel: Path) -> int:
    import facturx
    ziel.mkdir(parents=True, exist_ok=True, mode=0o700)
    zeilen, gesamt = [], 0
    for kuerzel, repo, lizenz, filter_ in QUELLEN:
        baum = json.loads(_get(f"https://api.github.com/repos/{repo}/git/trees/HEAD?recursive=1", 20_000_000))
        sha = baum["sha"]
        pfade = sorted(x["path"] for x in baum["tree"] if x["type"] == "blob" and x["path"].lower().endswith(".pdf")
                       and filter_(x["path"]) and x.get("size", 0) <= MAX_BYTES)
        out = ziel / kuerzel
        out.mkdir(exist_ok=True, mode=0o700)
        ok = ohne_xml = 0
        for pfad in pfade:
            stamm = re.sub(r"[^A-Za-z0-9._-]+", "_", pfad.rsplit(".", 1)[0].removeprefix("library/src/test/resources/"))
            url = f"https://raw.githubusercontent.com/{repo}/{sha}/{pfad.replace(' ', '%20')}"
            try:
                daten = _get(url)
                _, xml = facturx.get_xml_from_pdf(daten, check_xsd=False)
                if not xml:
                    raise ValueError("keine eingebettete XML")
                s = soll_aus_xml(xml)
            except Gesperrt:
                raise
            except Exception as e:   # defekte Beispiele (absichtlich oder nicht) überspringen
                ohne_xml += 1
                print(f"übersprungen {pfad}: {e}")
                continue
            (out / f"{stamm}.pdf").write_bytes(daten)
            s = {"datei": f"{stamm}.pdf", "quelle": "korpus", "herkunft": f"{repo}@{sha[:10]}:{pfad}", "sprache": sprache(daten),
                 **s}
            (out / f"{stamm}.soll.json").write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            ok += 1
        gesamt += ok
        zeilen.append(f"| {kuerzel} | https://github.com/{repo} (Commit {sha[:10]}) | {lizenz} | {ok} | {ohne_xml} |")
    (ziel / "QUELLEN.md").write_text(
        "# Quellen des Messkorpus\n\nAbgerufen " + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ". Nur Quellen mit offener Lizenz; "
        "Lizenztext liegt im jeweiligen Repo (LICENSE). Die PDFs sind unveränderte Kopien, die Sollwerte stammen aus "
        "der eingebetteten XML. Nicht ins Repo einchecken.\n\n| Kürzel | Quelle | Lizenz | PDFs | übersprungen |\n|---|---|---|---|---|\n"
        + "\n".join(zeilen) + "\n\nNicht verwendet: akretion/factur-x (Lizenz im GitHub-Metadatum nicht ausgewiesen), "
        "`fail`-Ordner des ZUGFeRD-Korpus (absichtlich fehlerhaft).\n", encoding="utf-8")
    print(f"{gesamt} PDFs in {ziel}")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--ziel", type=Path, default=ZIEL)
    try:
        sys.exit(holen(a.parse_args().ziel))
    except Gesperrt as e:
        print(f"Abbruch: {e}. Korpus nicht geholt (kein Umgehen versucht).", file=sys.stderr)
        sys.exit(2)
