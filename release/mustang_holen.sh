#!/bin/sh
# CI: Mustang-CLI und, falls das Job-Image kein Java hat, die Linux-JRE aus dem eigenen Spiegel holen (PAKET_TOKEN)
# und für die folgenden Schritte bekannt machen (MUSTANG_JAR in GITHUB_ENV, java in GITHUB_PATH).
set -eu
. release/mustang.env
S="${GITHUB_SERVER_URL:-https://git.gm-itsolutions.de}/api/packages/gm-itsolutions/generic"
M="${RUNNER_TEMP:-/tmp}/mustang"
hole() { curl -fsSL -H "Authorization: token $PAKET_TOKEN" -o "$2" "$S/$1"; }
mkdir -p "$M"
hole "mustang-cli/$MUSTANG/Mustang-CLI-$MUSTANG.jar" "$M/Mustang-CLI-$MUSTANG.jar"
echo "$MUSTANG_SHA256  $M/Mustang-CLI-$MUSTANG.jar" | sha256sum -c -
echo "MUSTANG_JAR=$M/Mustang-CLI-$MUSTANG.jar" >> "$GITHUB_ENV"
if command -v java; then
  java -version
  exit 0
fi
hole "temurin-jre/$JRE/OpenJDK21U-jre_x64_linux_hotspot_$JRE.tar.gz" "$M/jre.tar.gz"
echo "$JRE_LINUX_SHA256  $M/jre.tar.gz" | sha256sum -c -
tar -xzf "$M/jre.tar.gz" -C "$M"
"$M/$JRE_ORDNER/bin/java" -version
echo "$M/$JRE_ORDNER/bin" >> "$GITHUB_PATH"
