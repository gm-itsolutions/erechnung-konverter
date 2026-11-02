# Task 03: Kopf- und Summenfelder, Steuerzeilen

Spezifikation: `docs/lernmodus/spezifikation.md` 6.3. Global Constraints in `index.md`.

**Files:**
- Create: `tests/test_bereiche_felder.py`
- Modify: `erechnung/bereiche.py` (ergänzen)

**Interfaces:**
- Consumes: Task 02 (`feld_text`, `treffer`, `woerter_im_rahmen`, `BETRAG`, `DATUM`, `woerter_aus_pdf`, `tests/hilfen_bereiche.py`); `modell.betrag`, `modell.Partei`.
- Produces (in `bereiche.py`):
  - Leser `_betrag(t) -> Decimal` (ohne Vorzeichen), `_datum(t) -> date`, `_tage(t) -> int`, `_nummer(t) -> str` (für die Vorschau in Task 08)
  - `kopf_aus_bereichen(seiten, v, ocr=False, spur=None) -> dict` mit Schlüsseln `nummer, datum, leistungsdatum, faellig, kaeufer, summe_netto, summe_ust, summe_brutto, steuern, nachlass`

- [ ] **Step 1: Failing tests** – `tests/test_bereiche_felder.py`

```python
from datetime import date
from decimal import Decimal as D
from pathlib import Path
import pytest, yaml
from erechnung.bereiche import BereichsFehler, kopf_aus_bereichen, woerter_aus_pdf
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
V = yaml.safe_load((Path(__file__).parent / "daten" / "bereiche-beispiel.yml").read_text(encoding="utf-8"))
def seiten(tmp_path, pdf: bytes):
    p = tmp_path / "m.pdf"
    p.write_bytes(pdf)
    return woerter_aus_pdf(p)
@pytest.mark.parametrize("dx, dy", [(0, 0), (0.02, 0.03), (-0.01, -0.02)])
def test_kopf_werte(tmp_path, dx, dy):
    k = kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, dx=dx, dy=dy)), V)
    assert k["nummer"] == "BW-2026-17" and k["datum"] == date(2026, 11, 5) and k["faellig"] == date(2026, 11, 19)
    assert (k["kaeufer"].name, k["kaeufer"].strasse, k["kaeufer"].plz, k["kaeufer"].ort) == \
        ("Muster Kunde GmbH", "Am Markt 3", "19348", "Perleberg")
    assert (k["summe_netto"], k["summe_brutto"], k["steuern"]) == (D("240.00"), D("285.60"), {D("19"): D("45.60")})
def test_summen_wandern_mit_positionen(tmp_path):
    mehr = MUSTER1 + [("3", "Filter", "1 Stk", "10,00", "10,00"), ("4", "Kleinteile", "1 Stk", "5,00", "5,00")]
    k = kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(mehr, ("255,00", "48,45", "303,45"))), V)
    assert (k["summe_netto"], k["summe_brutto"]) == (D("255.00"), D("303.45"))
def test_spur(tmp_path):
    spur = {}
    kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), V, spur=spur)
    assert spur["nummer"]["seite"] == 0 and len(spur["summe_netto"]["rahmen"]) == 4
def test_pflichtanker_fehlt(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["felder"]["summe_brutto"]["anker"]["text"] = "Gesamtsumme"
    with pytest.raises(BereichsFehler, match="Anker „Gesamtsumme“ nicht gefunden"):
        kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
def test_nummer_unzulaessig(tmp_path):
    with pytest.raises(BereichsFehler, match="Rechnungsnummer"):
        kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1, nummer="BW#17")), V)
def test_nummer_kontrolle(tmp_path):
    v = yaml.safe_load(yaml.safe_dump(V))
    v["felder"]["nummer_kontrolle"] = {"seite": "erste", "rahmen": [0.68, 0.168, 0.95, 0.186],
                                       "anker": {"text": "Belegdatum", "rahmen": [0.50, 0.170, 0.59, 0.182]}}
    with pytest.raises(BereichsFehler, match="uneinheitlich"):
        kopf_aus_bereichen(seiten(tmp_path, werkstatt_pdf(MUSTER1, SUMMEN1)), v)
```
```

- [ ] **Step 2: FAIL prüfen** – `/root/.venvs/erechnung/bin/python -m pytest tests/test_bereiche_felder.py -q`

- [ ] **Step 3: Implementieren** – in `erechnung/bereiche.py` ergänzen (Importe `date`, `timedelta`, `Decimal`, `Partei`, `betrag` oben ergänzen, falls Task 02 sie nicht schon hat)

Werte lesen (`_betrag`, `_datum`, `_tage`, `_nummer`, `_kaeufer`) und `kopf_aus_bereichen`:

```python
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
def _betrag(t):
    m = BETRAG.findall(t)
    if not m:
        raise ValueError(f"kein Betrag in {t!r}")
    return abs(betrag(m[-1]))
def _datum(t):
    m = DATUM.search(t.replace("O", "0"))
    if not m:
        raise ValueError(f"kein Datum in {t!r}")
    j = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
    return date(j, int(m[2]), int(m[1]))
def _tage(t):
    m = re.search(r"\d{1,3}", t)
    if not m or not 1 <= int(m[0]) <= 365:
        raise ValueError(f"keine Tageszahl in {t!r}")
    return int(m[0])
def _nummer(t):
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
    _, z = feld_text(seiten, v, "kaeufer", ocr, spur)
    plz = [i for i, s in enumerate(z) if re.match(r"\d{5} ", s)]
    if not z or not plz or plz[-1] < 2:
        raise BereichsFehler(f"Käuferblock ohne Name, Straße, PLZ/Ort (Vorlage {v['name']})")
    p = plz[-1]
    k["kaeufer"] = Partei(z[0].strip(), z[p - 1].strip(), z[p][:5], z[p][6:].strip())
    k["steuern"] = _steuern(seiten, v, ocr, spur)
    return k
def _steuern(seiten, v, ocr, spur) -> dict[Decimal, Decimal]:
    s = v.get("steuern")
    if not s:
        return {}
    i = 0 if s["seite"] == "erste" else len(seiten) - 1
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
            r = s["rahmen"]
            spur[f"steuern{n + 1}"] = {"seite": i, "rahmen": [round(r[0] + dx, 4), round(r[1] + dy, 4), round(r[2] + dx, 4), round(r[3] + dy, 4)]}
    return ergebnis
```

`_steuern` sucht auf der letzten Seite; steht die Steuer nicht auf der letzten Seite, aber `seite: erste` ist gesetzt, die erste. `Decimal("19")` als Schlüssel, damit `{D("19"): …}` gleich ist (bei `"7.5"` → `Decimal("7.5")`).


- [ ] **Step 4: Tests grün** – `/root/.venvs/erechnung/bin/python -m pytest -q`

- [ ] **Step 5: Commit**

```bash
git -C /root/ek-wt-lern add erechnung/bereiche.py tests/test_bereiche_felder.py
git -C /root/ek-wt-lern commit -m "Lernmodus: Kopf-, Summen- und Steuerfelder per Rahmen" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/ek-wt-lern push origin lernmodus
```
