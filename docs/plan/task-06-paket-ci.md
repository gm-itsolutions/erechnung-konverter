# Task 06: Windows-ZIP bauen, Release-CI

Spezifikation: Abschnitt 4.1, 9. gm-update: `/root/gm-update/vorlagen/` (release.yml, bauen-beispiel.sh), Runbook ai-os `40-wissen/runbooks/release-und-update.md` Abschnitt B. Global Constraints in `index.md`.

**Files:**
- Create: `release/bauen.sh` (ausführbar), `release/requirements-windows.txt`, `.forgejo/workflows/release.yml`
- Create: `.forgejo/workflows/ci.yml` (Jobs `test` und `paket`)

**Interfaces:**
- Consumes: Paket `erechnung/` (Task 01, mit `__version__`), Ordner `einrichten/` (Task 07; fehlt er beim Bauen, bricht `bauen.sh` ab – im CI-Lauf vor Task 07 also rot, das ist erwartet).
- Produces: `dist/erechnung-konverter-<v>-windows-amd64.zip` mit `python\` (Embed 3.14.10 + `Lib\site-packages`), `app\erechnung\` (`__version__` = `<v>`), `einrichten\`. Release über `gm-update release` in die Forgejo-Paketablage (`generic/erechnung-konverter/<v>/`).

- [ ] **Step 0: CI-Workflow anlegen** `.forgejo/workflows/ci.yml` (Job `test`; Step 5 hängt Job `paket` an)

```yaml
# Forgejo CI (Runner gm-hosting). Tests bei jedem Push und Pull Request.
name: ci
on:
  push:
    branches: [main, dev]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: https://github.com/actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
      - uses: https://github.com/actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: '3.14'
      - run: python -m pip install -r requirements-dev.txt
      - run: python -m pytest -q
```

Prüfen, ob Actions im Repo aktiv sind: nach dem Push `https://git.gm-itsolutions.de/gm-itsolutions/erechnung-konverter/actions`. Ist der Reiter „Actions“ aus, per API einschalten (`PATCH /api/v1/repos/gm-itsolutions/erechnung-konverter` mit `{"has_actions": true}`, Token aus `/root/ai-os/.env` `FORGEJO_TOKEN` o. ä., nicht ausgeben). Geht das nicht: in der Rückmeldung als Blocker für Marvin nennen.

- [ ] **Step 1: `release/requirements-windows.txt`** (geprüft 02.11.2026 mit `pip download --platform win_amd64 --python-version 3.14 --implementation cp --only-binary=:all: pdfplumber factur-x pyyaml`; Hashes = SHA-256 der Wheels)

```
certifi==2026.10.23 --hash=sha256:e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1
cffi==2.1.1 --hash=sha256:3222ba5d678f80a030e6afbcc33dc1ae5cb45facabb61cee2c7016b8432fde48
charset-normalizer==3.5.2 --hash=sha256:e4e81e09c1578b8df602e3db08b0b3ea0a6947ad612f52bf8dc5ea8d47691f0c
cryptography==50.0.2 --hash=sha256:7afa5a6602a9f29af1f3a2965f831bae7c9d5d597b7cbb716d41ab3b7d89879c
factur-x==7.9 --hash=sha256:a91b66e48b51de0b2075d52091e794ed254585553daa5bfbd37041a166e296ae
idna==3.20 --hash=sha256:ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c
iso4217==1.16.20260101 --hash=sha256:69c591b93c7d783ec8c309ebee8df1aa28f8403d44bcce518ae8db050462084b
lxml==6.1.3 --hash=sha256:66299564c046bc7e0cc5de5106601eae907e9fa5904cd68a323380a8502f7861
pdfminer.six==20260107 --hash=sha256:366585ba97e80dffa8f00cebe303d2f381884d8637af4ce422f1df3ef38111a9
pdfplumber==0.11.10 --hash=sha256:7741ea81bf165b474b153e6789d10d18e06b6ddcf3ec84289c3ef2fed6802580
pillow==13.0.0 --hash=sha256:f7cbb7a64e7ec664775195e4f81923bc8a93d9451b963f844e59118f63147a7a
pycparser==3.12 --hash=sha256:a076f3f489b39b43ed13563a1dafe42447445bec2e294154ec5c57fcdda4c85e
pypdf==6.21.4 --hash=sha256:33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c
pypdfium2==5.14.0 --hash=sha256:149fd5c6397b8df8bf7911a93506eff0be874f877afe7ac936cf5d37d21a6a06
python-stdnum==2.2 --hash=sha256:bdf98fd117a0ca152e4047aa8ad254bae63853d4e915ddd4e0effb33ba0e9260
pyyaml==6.0.3 --hash=sha256:4a2e8cebe2ff6ab7d1050ecd59c25d4c8bd7e6f400f5f82b96557ac0abafd0ac
requests==2.34.2 --hash=sha256:2a0d60c172f83ac6ab31e4554906c0f3b3588d37b5cb939b1c061f4907e278e0
urllib3==2.8.0 --hash=sha256:0cf3cae568d36aa9576b28dfb35f11328f1cb974ca7647d9475ebb86c75ac6e3
```

`requirements-dev.txt` (Task 01) muss dieselben Versionen für pdfplumber, factur-x, lxml, pyyaml haben; abgleichen.

- [ ] **Step 2: Prüfsumme Python-Embed gegenprüfen**

Lokal gemessen (02.11.2026): `python-3.14.10-embed-amd64.zip` SHA-256 `90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159`. Gegen eine zweite Quelle prüfen: Release-Seite `https://www.python.org/downloads/release/python-31410/` (Tabelle „Files“, SHA-256 bzw. Sigstore-Bundle `…embed-amd64.zip.sigstore`). Stimmt sie nicht: **abbrechen und melden**, nichts pinnen.

- [ ] **Step 3: `release/bauen.sh`**

```sh
#!/bin/sh
# Baut dist/erechnung-konverter-<v>-windows-amd64.zip auf Linux. Aufruf: release/bauen.sh <version>
set -eu
V="$1"
PRODUKT=erechnung-konverter
PY=3.14.10
PY_SHA256=90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159
B=build/windows-amd64
rm -rf build
mkdir -p "$B/python" "$B/app" dist
curl -fsSL -o build/python-embed.zip "https://www.python.org/ftp/python/$PY/python-$PY-embed-amd64.zip"
echo "$PY_SHA256  build/python-embed.zip" | sha256sum -c -
unzip -q build/python-embed.zip -d "$B/python"
python3 -m pip install --quiet --no-deps --require-hashes --only-binary=:all: \
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
(cd "$B" && zip -qr "../../dist/$PRODUKT-$V-windows-amd64.zip" .)
ls -l "dist/$PRODUKT-$V-windows-amd64.zip"
```

`chmod +x release/bauen.sh`, außerdem `git update-index --chmod=+x release/bauen.sh` nach dem `git add`. Der Dateiname der lxml-`.pyd` kann abweichen: nach dem ersten Lauf mit `ls build/windows-amd64/python/Lib/site-packages/lxml/` prüfen und die Zeile anpassen.

- [ ] **Step 4: Lokal bauen**

Run (cwd `/root/erechnung-konverter`): `sh release/bauen.sh 0.0.1`. Fehlt `einrichten/` noch (Task 07 parallel), vorübergehend mit `mkdir -p einrichten` und leeren Dateien `einrichten.ps1`/`gm-update.json` testen, diese **nicht** committen.
Expected: `sha256sum: OK`, ZIP ca. 40–60 MB. `unzip -l dist/erechnung-konverter-0.0.1-windows-amd64.zip | grep -c site-packages` > 0. pip auf gm-claude: `/root/.venvs/erechnung/bin/python -m pip` statt `python3 -m pip` verwenden, falls `python3` kein pip hat (`PIP="${PIP:-python3 -m pip}"` als Variable im Skript ist erlaubt).

- [ ] **Step 5: CI-Job `paket` in `.forgejo/workflows/ci.yml`** (nach Job `test` anhängen)

```yaml
  paket:
    runs-on: ubuntu-latest
    steps:
      - uses: https://github.com/actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
      - uses: https://github.com/actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: '3.14'
      - run: sh release/bauen.sh 0.0.0
```

Fehlt `zip`/`unzip` im Runner: Schritt `- run: command -v zip unzip || (apt-get update && apt-get install -y zip unzip)` davor (eigener Schritt; YAML-`run` ist kein Freigabe-Aufruf, `||` ist dort erlaubt).

- [ ] **Step 6: `.forgejo/workflows/release.yml`** aus `/root/gm-update/vorlagen/release.yml` kopieren und anpassen:
  - `PRODUKT: erechnung-konverter`, `GM_UPDATE_VERSION: '0.1.3'`
  - `GM_UPDATE_SHA256`: SHA-256 von `gm-update-0.1.3-linux-amd64` aus der freigegebenen `release.json`: `curl -fsS -H "Authorization: token $(cat /root/.config/gm-it-os/update-test.token)" https://git.gm-itsolutions.de/api/packages/gm-itsolutions/generic/gm-update/0.1.3/release.json` (Token nicht ausgeben; Befehl so absetzen, dass er nicht im Log steht, z. B. Ausgabe in Datei unter `/tmp` und dann mit `python3 -c` das Feld lesen).
  - Schritt „Bauen (Docker)“ entfernen. Vor „Bauen (Datei)“ einfügen:

```yaml
      - uses: https://github.com/actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6.3.0
        with:
          python-version: '3.14'
      - name: Tests
        run: |
          set -euo pipefail
          python -m pip install -r requirements-dev.txt
          python -m pytest -q
```

- [ ] **Step 7: Commit, Push, CI grün**

```bash
git -C /root/erechnung-konverter add release/bauen.sh release/requirements-windows.txt .forgejo/workflows/release.yml .forgejo/workflows/ci.yml
git -C /root/erechnung-konverter update-index --chmod=+x release/bauen.sh
git -C /root/erechnung-konverter commit -m "Windows-Paket mit Embeddable-Python und Release-CI über gm-update" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter push origin main
```
CI-Ergebnis in Forgejo ansehen. Job `paket` darf rot sein, solange Task 07 (`einrichten/`) fehlt; dann in der Rückmeldung so vermerken.
