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
# Mustang-CLI und Java-Laufzeit (Temurin JRE) für die Prüfung jeder Rechnung: Versionen und SHA-256
. release/mustang.env
# Python-Embed, deu.traineddata, Temurin-JRE und Mustang-CLI kommen aus dem eigenen Spiegel (Forgejo-Paketablage, Paket-Token in PAKET_TOKEN).
# Neue Version spiegeln: Original laden, SHA-256 prüfen, per PUT nach .../generic/<paket>/<version>/<datei> hochladen.
SPIEGEL="${GITHUB_SERVER_URL:-https://git.gm-itsolutions.de}/api/packages/gm-itsolutions/generic"
hole() { curl -fsSL -H "Authorization: token $PAKET_TOKEN" -o "$2" "$SPIEGEL/$1"; }
B=build/windows-amd64
rm -rf build
mkdir -p "$B/python" "$B/app" dist
# Original: https://www.python.org/ftp/python/$PY/python-$PY-embed-amd64.zip
hole "python-embed/$PY/python-$PY-embed-amd64.zip" build/python-embed.zip
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
# Original: https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/$TESSDATA_COMMIT/deu.traineddata
hole "tessdata-best/$TESSDATA_COMMIT/deu.traineddata" "$B/tesseract/tessdata/deu.traineddata"
echo "$DEU_SHA256  $B/tesseract/tessdata/deu.traineddata" | sha256sum -c -
# Java-Laufzeit: Temurin-JRE-ZIP unverändert (kein jlink, Begründung Spezifikation 4.1), oberster Ordner entfällt
hole "temurin-jre/$JRE/OpenJDK21U-jre_x64_windows_hotspot_$JRE.zip" build/jre.zip
echo "$JRE_WIN_SHA256  build/jre.zip" | sha256sum -c -
python3 -m zipfile -e build/jre.zip build/jre
mv "build/jre/$JRE_ORDNER" "$B/java"
mkdir -p "$B/mustang"
hole "mustang-cli/$MUSTANG/Mustang-CLI-$MUSTANG.jar" "$B/mustang/Mustang-CLI-$MUSTANG.jar"
echo "$MUSTANG_SHA256  $B/mustang/Mustang-CLI-$MUSTANG.jar" | sha256sum -c -
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
         app/erechnung/bereiche.py app/erechnung/anlernen/server.py app/erechnung/anlernen/statisch/index.html \
         app/erechnung/anlernen/statisch/gm.css app/erechnung/anlernen/statisch/anlernen.js \
         app/erechnung/anlernen/statisch/fonts/OFL.txt \
         einrichten/einrichten.ps1 einrichten/gm-update.json tesseract/tesseract.exe tesseract/tesseract55.dll \
         tesseract/tessdata/deu.traineddata tesseract/lizenzen/tesseract THIRD-PARTY.txt \
         java/bin/java.exe java/legal java/NOTICE "mustang/Mustang-CLI-$MUSTANG.jar"; do
  test -e "$B/$f" || { echo "fehlt: $f" >&2; exit 1; }
done
grep -qx "__version__ = \"$V\"" "$B/app/erechnung/__init__.py"
# python314._pth ohne "import site": der erhöhte Lauf (Lernmodus) soll keine Benutzer-Pfade (site, usercustomize) laden
if grep -q "import site" "$B/python/python314._pth"; then echo "python314._pth enthält import site" >&2; exit 1; fi
# zip/unzip werden nicht gebraucht: Python-Standardbibliothek (komprimiert mit Deflate)
python3 -c 'import shutil, sys; shutil.make_archive(sys.argv[1], "zip", sys.argv[2])' "dist/$PRODUKT-$V-windows-amd64" "$B"
ls -l "dist/$PRODUKT-$V-windows-amd64.zip"
