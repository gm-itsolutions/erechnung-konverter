"""Texterkennung (Tesseract) für PDFs ohne Text, z. B. aus Edge gerastert gedruckt (Spezifikation Abschnitt 3.2)."""
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image
from .bereiche import Seite, Wort

PAKET = Path(__file__).resolve().parents[2] / "tesseract"   # im ZIP: app\erechnung → ..\..\tesseract
DPI = 300
MAX_PIXEL = 6000      # längste Bildkante; schützt vor riesigen Seitenformaten
MAX_SEITEN = 20
FRIST = 120           # Sekunden je Seite und Lesart
GESAMTFRIST = 600     # Sekunden je Rechnung; danach keine weitere Lesart
# Lesarten in dieser Reihenfolge, bis Vorlage, Nummern-Gegenprobe und Summenabgleich passen (Spezifikation 3.2)
LESARTEN = (("psm 6", 6, False), ("psm 6 ohne Linien", 6, True), ("psm 4", 4, False), ("psm 4 ohne Linien", 4, True))


def tesseract() -> list[str] | None:
    """Aufruf ohne Bild: mitgeliefertes tesseract.exe mit eigenem tessdata, sonst tesseract aus PATH (Entwicklung)."""
    exe = PAKET / "tesseract.exe"
    if exe.is_file():
        return [str(exe), "--tessdata-dir", str(PAKET / "tessdata")]
    w = shutil.which("tesseract")
    return [w] if w else None


def bereinige(text: str) -> str:
    """Tabellenrahmen (|), doppelte Leerzeichen und Leerzeilen entfernen. Ziffern bleiben unangetastet."""
    return "\n".join(z for z in (" ".join(z.replace("|", " ").split()) for z in text.splitlines()) if z)


def ohne_linien(quelle: Path, ziel: Path) -> None:
    """Tabellenrahmen weiß machen: Bildzeilen, die zu mehr als der Hälfte dunkel sind. Sonst stören die Linien
    die Zeilenerkennung von Tesseract, einzeilige Positionen zwischen zwei Linien fallen dann weg."""
    im = Image.open(quelle).convert("L")
    w, h = im.size
    dunkel = im.point(lambda v: 255 if v < 128 else 0).resize((1, h), Image.BOX)   # Anteil dunkler Pixel je Zeile
    for y in range(h):
        if dunkel.getpixel((0, y)) > 128:
            im.paste(255, (0, y, w, y + 1))
    im.save(ziel)


def tsv_woerter(tsv: str, breite: int, hoehe: int) -> Seite:
    """Tesseract-TSV: Ebene 5 = Wort; conf < 0 und leere Wörter verwerfen; Lage relativ zum Bild."""
    woerter = []
    for z in tsv.splitlines()[1:]:
        f = z.split("\t")
        if len(f) < 12 or f[0] != "5" or float(f[10]) < 0 or not f[11].strip():
            continue
        l, t, w, h = (int(x) for x in f[6:10])
        woerter.append(Wort(f[11].strip(), l / breite, t / hoehe, (l + w) / breite, (t + h) / hoehe))
    return woerter


def erkenne(pdf: Path, arbeit: Path, aufruf: list[str]) -> Iterator[tuple[str, str]]:
    """Lesarten (Name, Text) nacheinander, erst bei Bedarf gelesen: jede Seite einmal mit pypdfium2 als Graustufenbild
    gerendert, dann je Lesart mit `aufruf` (tesseract) -l deu gelesen. Nach GESAMTFRIST keine weitere Lesart."""
    lesarten = _lesarten(pdf, arbeit, aufruf, tsv=False)
    try:
        for name, text, _ in lesarten:
            yield name, text
    finally:
        lesarten.close()


def erkenne_seiten(pdf: Path, arbeit: Path, aufruf: list[str]) -> Iterator[tuple[str, str, list[Seite]]]:
    """Wie `erkenne`, je Lesart zusätzlich die Wörter mit Lage je Seite (Tesseract `txt tsv` in einem Lauf)."""
    yield from _lesarten(pdf, arbeit, aufruf, tsv=True)


def _lesarten(pdf: Path, arbeit: Path, aufruf: list[str], tsv: bool) -> Iterator[tuple[str, str, list[Seite] | None]]:
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ocr-", dir=arbeit) as tmp:
        d = pdfium.PdfDocument(pdf)
        try:
            if len(d) > MAX_SEITEN:
                raise ValueError(f"zu viele Seiten für die Texterkennung ({len(d)}, höchstens {MAX_SEITEN})")
            bilder = []
            for i, s in enumerate(d):
                skala = min(DPI / 72, MAX_PIXEL / max(s.get_size()))
                pil = s.render(scale=skala, grayscale=True).to_pil()
                bilder.append((Path(tmp) / f"{i}.png", round(skala * 72), pil.size))
                pil.save(bilder[-1][0])
        finally:
            d.close()   # vor der Erkennung schließen: Windows sperrt sonst das PDF
        for n, (name, psm, linien_weg) in enumerate(LESARTEN):
            if n and time.monotonic() - start > GESAMTFRIST:
                return
            seiten, woerter = [], []
            for i, (bild, dpi, groesse) in enumerate(bilder):
                if linien_weg:
                    if not (ohne := bild.with_name(f"{i}-ohne-linien.png")).exists():
                        ohne_linien(bild, ohne)
                    bild = ohne
                basis = Path(tmp) / f"{i}-{n}"
                try:
                    subprocess.run([*aufruf, str(bild), str(basis), "-l", "deu", "--psm", str(psm), "--dpi", str(dpi),
                                    *(("txt", "tsv") if tsv else ())],
                                   check=True, capture_output=True, timeout=FRIST,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except subprocess.CalledProcessError as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}, Code {e.returncode}): "
                                     f"{e.stderr.decode(errors='replace').strip()[-300:]}") from None
                except (subprocess.TimeoutExpired, OSError) as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}): {e}") from None
                seiten.append(basis.with_suffix(".txt").read_text(encoding="utf-8"))
                if tsv:
                    woerter.append(tsv_woerter(basis.with_suffix(".tsv").read_text(encoding="utf-8"), *groesse))
            yield name, bereinige("\n".join(s.rstrip("\n\f") for s in seiten)), woerter if tsv else None
