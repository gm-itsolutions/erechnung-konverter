#!/bin/sh
# Baut dist/erechnung-konverter-<v>-windows-amd64.zip auf Linux. Aufruf: release/bauen.sh <version>
set -eu
V="$1"
PRODUKT=erechnung-konverter
PY=3.14.10
# Gegengeprüft 02.11.2026 mit dem Sigstore-Bundle von python.org (Signatur hugo@python.org)
PY_SHA256=90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159
# Texterkennung: deu.traineddata aus tesseract-ocr/tessdata_best (Commit fest), SHA-256 am 02.11.2026 bestimmt
TESSDATA_COMMIT=e12c65a915945e4c28e237a9b52bc4a8f39a0cec
DEU_SHA256=8407331d6aa0229dc927685c01a7938fc5a641d1a9524f74838cdac599f0d06e
PIP="${PIP:-python3 -m pip}"
B=build/windows-amd64
rm -rf build
mkdir -p "$B/python" "$B/app" dist
curl -fsSL -o build/python-embed.zip "https://www.python.org/ftp/python/$PY/python-$PY-embed-amd64.zip"
echo "$PY_SHA256  build/python-embed.zip" | sha256sum -c -
python3 -m zipfile -e build/python-embed.zip "$B/python"
$PIP install --quiet --no-deps --require-hashes --only-binary=:all: \
  --platform win_amd64 --python-version 3.14 --implementation cp \
  --target "$B/python/Lib/site-packages" -r release/requirements-windows.txt
# Tesseract für Windows aus conda-forge, jede Datei mit fester SHA-256 (release/tesseract-windows.txt)
mkdir -p build/conda "$B/tesseract/tessdata"
grep -v '^#' release/tesseract-windows.txt | while read -r url sha; do
  f="build/conda/${url##*/}"
  curl -fsSL -o "$f" "$url"
  echo "$sha  $f" | sha256sum -c --quiet -
done
python3 -I release/conda_entpacken.py "$B/tesseract" build/conda/*.conda
curl -fsSL -o "$B/tesseract/tessdata/deu.traineddata" \
  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/$TESSDATA_COMMIT/deu.traineddata"
echo "$DEU_SHA256  $B/tesseract/tessdata/deu.traineddata" | sha256sum -c -
cp release/THIRD-PARTY.txt "$B/"
printf 'python314.zip\n.\nLib\\site-packages\n..\\app\n' > "$B/python/python314._pth"
cp -r erechnung "$B/app/"
find "$B/app" -name __pycache__ -prune -exec rm -rf {} +
sed -i "s/^__version__ = .*/__version__ = \"$V\"/" "$B/app/erechnung/__init__.py"
cp -r einrichten "$B/einrichten"
# Selbstprüfung: alles da, was die Probe auf Windows braucht
for f in python/pythonw.exe python/python.exe python/Lib/site-packages/lxml/etree.cp314-win_amd64.pyd \
         python/Lib/site-packages/facturx/__init__.py python/Lib/site-packages/pdfplumber/__init__.py \
         python/Lib/site-packages/yaml/__init__.py app/erechnung/__main__.py app/erechnung/vorlagen/lexware-gm-it.yml \
         einrichten/einrichten.ps1 einrichten/gm-update.json tesseract/tesseract.exe tesseract/tesseract55.dll \
         tesseract/tessdata/deu.traineddata tesseract/lizenzen/tesseract THIRD-PARTY.txt; do
  test -e "$B/$f" || { echo "fehlt: $f" >&2; exit 1; }
done
grep -qx "__version__ = \"$V\"" "$B/app/erechnung/__init__.py"
# zip/unzip werden nicht gebraucht: Python-Standardbibliothek (komprimiert mit Deflate)
python3 -c 'import shutil, sys; shutil.make_archive(sys.argv[1], "zip", sys.argv[2])' "dist/$PRODUKT-$V-windows-amd64" "$B"
ls -l "dist/$PRODUKT-$V-windows-amd64.zip"
