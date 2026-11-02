"""Texterkennung (Tesseract) für PDFs ohne Text, z. B. aus Edge gerastert gedruckt (Spezifikation Abschnitt 3.2)."""
import shutil
import subprocess
import tempfile
from pathlib import Path
import pypdfium2 as pdfium

PAKET = Path(__file__).resolve().parents[2] / "tesseract"   # im ZIP: app\erechnung → ..\..\tesseract
DPI = 300
MAX_PIXEL = 6000      # längste Bildkante; schützt vor riesigen Seitenformaten
MAX_SEITEN = 20
FRIST = 120           # Sekunden je Seite


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


def erkenne(pdf: Path, arbeit: Path, aufruf: list[str]) -> str:
    """Jede Seite mit pypdfium2 als Graustufenbild rendern und mit `aufruf` (tesseract) -l deu lesen."""
    d = pdfium.PdfDocument(pdf)
    try:
        if len(d) > MAX_SEITEN:
            raise ValueError(f"zu viele Seiten für die Texterkennung ({len(d)}, höchstens {MAX_SEITEN})")
        seiten = []
        with tempfile.TemporaryDirectory(prefix="ocr-", dir=arbeit) as tmp:
            for i, s in enumerate(d):
                skala = min(DPI / 72, MAX_PIXEL / max(s.get_size()))
                bild, basis = Path(tmp) / f"{i}.png", Path(tmp) / str(i)
                s.render(scale=skala, grayscale=True).to_pil().save(bild)
                try:
                    subprocess.run([*aufruf, str(bild), str(basis), "-l", "deu", "--psm", "6", "--dpi", str(round(skala * 72))],
                                   check=True, capture_output=True, timeout=FRIST,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                except subprocess.CalledProcessError as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}, Code {e.returncode}): "
                                     f"{e.stderr.decode(errors='replace').strip()[-300:]}") from None
                except (subprocess.TimeoutExpired, OSError) as e:
                    raise ValueError(f"Texterkennung fehlgeschlagen (Seite {i + 1}): {e}") from None
                seiten.append(basis.with_suffix(".txt").read_text(encoding="utf-8"))
    finally:
        d.close()
    return bereinige("\n".join(s.rstrip("\n\f") for s in seiten))
