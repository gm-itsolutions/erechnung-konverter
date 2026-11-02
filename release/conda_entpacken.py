"""Holt aus geprüften conda-Paketen (.conda) tesseract.exe, die DLLs, die es braucht, und alle Lizenzen.
Aufruf: python3 -I conda_entpacken.py <ziel> <paket.conda>...  (braucht Python 3.14: tarfile mit zstd)"""
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

# Importhülle von tesseract.exe (objdump -p, rekursiv) für die Pakete in tesseract-windows.txt;
# alles Übrige (api-ms-win-crt-*, kernel32 …) bringt Windows mit. Bei neuer Pinliste neu bestimmen.
BEHALTEN = {
    "tesseract.exe", "tesseract55.dll", "leptonica-1.87.0.dll", "archive.dll", "charset.dll", "deflate.dll",
    "gif-7.dll", "iconv.dll", "icudt78.dll", "icuuc78.dll", "jpeg8.dll", "lerc.dll", "libbz2.dll",
    "libcrypto-3-x64.dll", "libcurl.dll", "liblzma.dll", "libpng16.dll", "libsharpyuv.dll", "libssh2.dll",
    "libwebp.dll", "libwebpmux.dll", "libxml2.dll", "lz4.dll", "msvcp140.dll", "openjp2.dll", "psl-5.dll",
    "tiff.dll", "vcruntime140.dll", "vcruntime140_1.dll", "zlib.dll", "zstd.dll",
}
ziel = Path(sys.argv[1])
for datei in map(Path, sys.argv[2:]):
    name = datei.name.removesuffix(".conda").rsplit("-", 2)[0]
    with zipfile.ZipFile(datei) as z:
        for inhalt in (n for n in z.namelist() if n.endswith(".tar.zst")):
            with z.open(inhalt) as f, tarfile.open(fileobj=f, mode="r|zst") as t:
                for m in t:
                    p = PurePosixPath(m.name)
                    if not m.isfile():
                        continue
                    if ".." in p.parts:
                        sys.exit(f"unsicherer Pfad in {datei.name}: {m.name}")
                    if p.parent == PurePosixPath("Library/bin") and p.name.lower() in BEHALTEN:
                        aus = ziel / p.name
                    elif p.parts[:2] == ("info", "licenses"):
                        aus = ziel / "lizenzen" / name / Path(*p.parts[2:])
                    else:
                        continue
                    if aus.exists():
                        sys.exit(f"doppelt: {aus}")
                    aus.parent.mkdir(parents=True, exist_ok=True)
                    aus.write_bytes(t.extractfile(m).read())
fehlt = BEHALTEN - {p.name.lower() for p in ziel.iterdir()}
if fehlt:
    sys.exit("fehlt: " + " ".join(sorted(fehlt)))
