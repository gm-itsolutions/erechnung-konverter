# Task 04: Positionstabelle, Folgeseiten, Übertrag; Rechnung aus Bereichen

Spezifikation: `docs/lernmodus/spezifikation.md` 6.4, 8. Global Constraints in `index.md`.

**Files:**
- Create: `tests/test_bereiche_positionen.py`
- Modify: `tests/hilfen_bereiche.py` (Parameter `skala`), `erechnung/bereiche.py`, `erechnung/vorlagen.py` (`lies_rechnung`, nur Text-Weg)

**Interfaces:**
- Consumes: Task 02 (`treffer` liefert `(x0, top, x1, satz)`, `zeilen`, `BETRAG`, `SATZ`, `Wort`, `woerter_aus_pdf`), Task 03 (`kopf_aus_bereichen`), `tests/hilfen_bereiche.py` (`werkstatt_pdf`, `MUSTER1`, `SUMMEN1`); `vorlagen._anfuegen` (Silbentrennung, lokal importieren gegen Zirkelimport); `modell.Position`, `Rechnung`, `Nachlass`, `runde`, `summenabgleich`.
- Produces:
  - `positionen_aus_bereichen(seiten: list[Seite], v: dict, ocr: bool = False, spur: dict | None = None) -> tuple[list[Position], list[str]]` (Positionen, ignorierte Zeilen)
  - `rechnung_aus_bereichen(seiten: list[Seite], v: dict, verkaeufer: Partei, ocr: bool = False, spur: dict | None = None) -> Rechnung`
  - `vorlagen.lies_rechnung` verzweigt bei `art: bereiche` (Text-PDF)

- [ ] **Step 1: Failing tests** – `tests/test_bereiche_positionen.py`

```python
from decimal import Decimal as D
from pathlib import Path
import pytest, yaml
from erechnung.bereiche import BereichsFehler, positionen_aus_bereichen, rechnung_aus_bereichen, woerter_aus_pdf
from erechnung.modell import summenabgleich
from erechnung.vorlagen import STANDARD, lade_vorlagen, lies_rechnung
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
DATEN = Path(__file__).parent / "daten"
V = yaml.safe_load((DATEN / "bereiche-beispiel.yml").read_text(encoding="utf-8"))
def seiten(tmp_path, pdf):
    p = tmp_path / "m.pdf"
    p.write_bytes(pdf)
    return woerter_aus_pdf(p)
def test_muster1(tmp_path):
    pos, ignoriert = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V)
    assert [(p.nr, p.bezeichnung, p.menge, p.einheit, p.einzelpreis, p.netto, p.ust_satz) for p in pos] == [
        ("1", "Inspektion nach Herstellervorgabe inkl. Probefahrt", D("2"), "HUR", D("95.00"), D("190.00"), D("19")),
        ("2", "Motoröl 5W-30", D("4"), "H87", D("12.50"), D("50.00"), D("19"))]
    assert ignoriert == []
@pytest.mark.parametrize("dx, dy", [(0.02, 0.03), (-0.015, -0.01)])
def test_verschoben(tmp_path, dx, dy):
    pos, _ = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=dx, dy=dy)), V)
    assert [p.netto for p in pos] == [D("190.00"), D("50.00")]
@pytest.mark.parametrize("kopf_wiederholen", [True, False])
def test_mehrseitig_mit_uebertrag(tmp_path, kopf_wiederholen):
    zeilen = [(str(i), f"Teil {i}", "1 Stk", "10,00", "10,00") for i in range(1, 31)]
    pdf = werkstatt_pdf(zeilen, ("300,00", "57,00", "357,00"), umbruch_nach=20, uebertrag="200,00",
                        kopf_wiederholen=kopf_wiederholen)
    s = seiten(tmp_path, pdf)
    assert len(s) == 2
    pos, ignoriert = positionen_aus_bereichen(s, V)
    assert [p.nr for p in pos] == [str(i) for i in range(1, 31)]
    assert all(p.bezeichnung == f"Teil {p.nr}" for p in pos)       # kein Briefkopf in einer Bezeichnung
    assert len(ignoriert) == 2 and all("Übertrag" in z for z in ignoriert)
    r = rechnung_aus_bereichen(s, V, VERKAEUFER)
    assert summenabgleich(r) == {D("19"): (D("300.00"), D("57.00"))}
def test_skaliert_wie_edge(tmp_path):
    """Edge „an Seite anpassen“: Seite um 95 % verkleinert und zentriert."""
    s = seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, skala=0.95))
    pos, _ = positionen_aus_bereichen(s, V)
    assert [(p.menge, p.einheit, p.netto) for p in pos] == [(D("2"), "HUR", D("190.00")), (D("4"), "H87", D("50.00"))]
    assert rechnung_aus_bereichen(s, V, VERKAEUFER).summe_brutto == D("285.60")
def test_kopf_fehlt(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["positionen"]["kopf"]["text"] = "Pos Artikel"
    with pytest.raises(BereichsFehler, match="Tabellenkopf"):
        positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
def test_menge_fehlt_gilt_eins(tmp_path):
    z = [("1", "Pauschale Diagnose", "", "80,00", "80,00")]
    pos, _ = positionen_aus_bereichen(seiten(tmp_path, werkstatt_pdf(z, ("80,00", "15,20", "95,20"))), V)
    assert (pos[0].menge, pos[0].einheit) == (D("1"), "C62")
def test_spur_tabelle(tmp_path):
    spur = {}
    rechnung_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V, VERKAEUFER, spur=spur)
    assert {"nummer", "summe_brutto", "positionen1"} <= set(spur)
def test_lies_rechnung_text_pdf(tmp_path):
    (tmp_path / "v").mkdir()
    (tmp_path / "v" / "b.yml").write_text((DATEN / "bereiche-beispiel.yml").read_text(encoding="utf-8"), encoding="utf-8")
    pdf = tmp_path / "r.pdf"
    pdf.write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
    r = lies_rechnung(pdf, lade_vorlagen(STANDARD, tmp_path / "v"), VERKAEUFER)
    assert (r.vorlage, r.nummer, r.summe_brutto, len(r.positionen)) == ("test-bereiche", "BW-2026-17", D("285.60"), 2)
    summenabgleich(r)
```

- [ ] **Step 1b: Testhilfe um `skala` ergänzen** – in `tests/hilfen_bereiche.py` Parameter `skala=1.0` an `werkstatt_pdf`; direkt nach `c = canvas.Canvas(...)` und nach jedem `c.showPage()`:

```python
    def skalieren():
        c.translate(W * (1 - skala) / 2, H * (1 - skala) / 2)
        c.scale(skala, skala)
    skalieren()
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_bereiche_positionen.py -q`

- [ ] **Step 3: Implementieren** – `erechnung/bereiche.py`

```python
from .modell import Nachlass, Position, Rechnung, runde
def _bester(t, rahmen):
    return min(t, key=lambda h: (h[0] - rahmen[0]) ** 2 + (h[1] - rahmen[1]) ** 2) if t else None
def _oder_none(lesen, text):
    try:
        return lesen(text) if text.strip() else None
    except ValueError:
        return None
def _menge(text: str) -> Decimal:
    m = re.fullmatch(r"-?\d[\d.]*(?:,\d+)?", text.strip())
    if not m:
        raise ValueError(text)
    return betrag(m[0])
def positionen_aus_bereichen(seiten, v, ocr=False, spur=None):
    from .vorlagen import _anfuegen          # Silbentrennung wie Regex-Vorlagen
    p, kopf, ende = v["positionen"], v["positionen"]["kopf"], v["positionen"].get("ende")
    arten = [s["art"] for s in p["spalten"]]
    grenzen0 = [p["links"], *(s["bis"] for s in p["spalten"])]
    kr = kopf["rahmen"]
    kx, sx, ergebnis, ignoriert = kr[0], 1.0, [], []   # Kopf-Lage und waagerechte Skalierung (Edge „an Seite anpassen“)
    for i, seite in enumerate(seiten):
        k = _bester(treffer(seite, kopf["text"], ocr), kopf["rahmen"])
        if i == 0 and k is None:
            raise BereichsFehler(f"Tabellenkopf „{kopf['text']}“ nicht gefunden (Vorlage {v['name']})")
        if k:
            kx, sx = k[0], (k[2] - k[0]) / (kr[2] - kr[0])
        oben = k[1] + (kr[3] - kr[1]) * sx if k else 0.0
        e = _bester(treffer(seite, ende["text"], ocr), ende["rahmen"]) if ende else None
        unten = e[1] if e else p["unten"]
        grenzen = [kx + (g - kr[0]) * sx for g in grenzen0]
        if spur is not None:
            spur[f"positionen{i + 1}"] = {"seite": i, "rahmen": [round(grenzen[0], 4), round(oben, 4), round(grenzen[-1], 4), round(unten, 4)]}
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
            netto = _oder_none(lambda s: betrag(BETRAG.findall(s)[-1]), t.get("netto", ""))
            if not begonnen and netto is None:
                continue                      # Folgeseite ohne Kopf: Briefkopf überspringen
            begonnen = True
            einheit = t.get("einheit", "").strip()
            mt = t.get("menge", "")
            if "menge_einheit" in t:
                m = re.match(r"\s*(-?\d[\d.]*(?:,\d+)?)\s*(.*)", t["menge_einheit"])
                mt, einheit = (m[1], m[2].strip()) if m else ("", "")
            menge = _oder_none(_menge, mt)
            preis = _oder_none(lambda s: betrag(BETRAG.findall(s)[-1]), t.get("einzelpreis", ""))
            if netto is not None and (menge is not None or preis is not None):
                menge = menge if menge is not None else Decimal("1")
                satz = _oder_none(lambda s: Decimal(re.search(SATZ, s)[1].replace(",", ".")), t.get("ust_satz", ""))
                ergebnis.append(Position(
                    nr=t.get("nr", "").strip() or str(len(ergebnis) + 1), bezeichnung=t["bezeichnung"].strip(),
                    menge=menge, einheit=v.get("einheiten", {}).get(einheit, "C62"),
                    einzelpreis=preis if preis is not None else runde(netto / menge), netto=netto,
                    ust_satz=satz if satz is not None else Decimal(str(p.get("ust_satz", 19)))))
            elif netto is None and t["bezeichnung"].strip() and ergebnis:
                ergebnis[-1].bezeichnung = _anfuegen(ergebnis[-1].bezeichnung, t["bezeichnung"].strip())
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
```

Prüfen, ob `Nachlass(betrag, grund)` die Reihenfolge in `modell.py` trifft (`grep -n "class Nachlass" -A6 erechnung/modell.py`); sonst Schlüsselwortargumente.

- [ ] **Step 4: `lies_rechnung` (Text-Weg)** – in `erechnung/vorlagen.py` nach `v = finde_vorlage(text, vorlagen)`:

```python
        if v.get("art") == "bereiche":
            from .bereiche import BereichsFehler, rechnung_aus_bereichen, woerter_aus_pdf
            try:
                return rechnung_aus_bereichen(woerter_aus_pdf(pdf), v, verkaeufer)
            except BereichsFehler as e:
                raise VorlagenFehler(str(e)) from None
```

(`BereichsFehler` ist bereits oben importiert, falls Task 01 das so gemacht hat; dann den lokalen Import nur für die Funktionen.)

- [ ] **Step 5: Alle Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 5b: Gegenprobe fremde Layouts (nur gm-claude, kein Test im Repo)** – mit einer von Hand nach `/root/erechnung-testdaten/fremd/D-1.pdf` gebauten `art: bereiche`-Vorlage (Koordinaten über `woerter_aus_pdf` ablesen) `rechnung_aus_bereichen` für `D-1.pdf`, `D-2.pdf`, `D-3.pdf` (3 Seiten, Übertrag, wiederholter Kopf) aufrufen und Positionen, Netto, Steuer, Brutto gegen `D-<n>.soll.json` vergleichen; Übertragszeilen dürfen nur als ignorierte Zeilen auftauchen. Ergebnis im Commit vermerken, Abweichungen der Hauptsitzung melden.

- [ ] **Step 6: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/bereiche.py erechnung/vorlagen.py tests/test_bereiche_positionen.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Positionstabelle per Spalten, Folgeseiten, Übertrag" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
