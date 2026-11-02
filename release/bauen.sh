#!/bin/sh
# Baut dist/erechnung-konverter-<v>-windows-amd64.zip auf Linux. Aufruf: release/bauen.sh <version>
set -eu
V="$1"
PRODUKT=erechnung-konverter
PY=3.14.10
# Gegengeprüft 02.11.2026 mit dem Sigstore-Bundle von python.org (Signatur hugo@python.org)
PY_SHA256=90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159
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
printf 'python314.zip\n.\nLib\\site-packages\n..\\app\n' > "$B/python/python314._pth"
cp -r erechnung "$B/app/"
find "$B/app" -name __pycache__ -prune -exec rm -rf {} +
sed -i "s/^__version__ = .*/__version__ = \"$V\"/" "$B/app/erechnung/__init__.py"
cp -r einrichten "$B/einrichten"
# Selbstprüfung: alles da, was die Probe auf Windows braucht
for f in python/pythonw.exe python/python.exe python/Lib/site-packages/lxml/etree.cp314-win_amd64.pyd \
         python/Lib/site-packages/facturx/__init__.py python/Lib/site-packages/pdfplumber/__init__.py \
         python/Lib/site-packages/yaml/__init__.py app/erechnung/__main__.py app/erechnung/vorlagen/lexware-gm-it.yml \
         einrichten/einrichten.ps1 einrichten/gm-update.json; do
  test -e "$B/$f" || { echo "fehlt: $f" >&2; exit 1; }
done
grep -qx "__version__ = \"$V\"" "$B/app/erechnung/__init__.py"
# zip/unzip werden nicht gebraucht: Python-Standardbibliothek (komprimiert mit Deflate)
python3 -c 'import shutil, sys; shutil.make_archive(sys.argv[1], "zip", sys.argv[2])' "dist/$PRODUKT-$V-windows-amd64" "$B"
ls -l "dist/$PRODUKT-$V-windows-amd64.zip"
