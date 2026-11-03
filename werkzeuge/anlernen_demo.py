"""Anlern-Oberfläche mit synthetischen Mustern starten (Entwicklung/Browserprüfung): python werkzeuge/anlernen_demo.py <ordner>"""
import json, sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "tests")]
from erechnung.anlernen.server import erstelle_server
from hilfen import VERKAEUFER
from hilfen_bereiche import MUSTER1, SUMMEN1, werkstatt_pdf
basis = Path(sys.argv[1])
for o in ("Eingang", "E-Rechnungen", "Originale", "Fehler", "prog"):
    (basis / o).mkdir(parents=True, exist_ok=True)
(basis / "Fehler" / "20261105-rechnung.pdf").write_bytes(werkstatt_pdf(MUSTER1, SUMMEN1))
(basis / "Fehler" / "20261106-rechnung.pdf").write_bytes(
    werkstatt_pdf(MUSTER1 + [("3", "Filter", "1 Stk", "10,00", "10,00")], ("250,00", "47,50", "297,50"), dx=0.01, dy=0.02))
konfig = basis / "prog" / "konfig.json"
konfig.write_text(json.dumps({"eingang": str(basis / "Eingang"), "ausgabe": str(basis / "E-Rechnungen"),
    "originale": str(basis / "Originale"), "fehler": str(basis / "Fehler"), "verkaeufer": VERKAEUFER.__dict__}), encoding="utf-8")
s, url = erstelle_server(konfig, basis / "daten")
print(url, flush=True)
s.serve_forever()
