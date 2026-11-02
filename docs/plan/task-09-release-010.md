# Task 09: Release `v0.1.0` (Hauptsitzung)

Spezifikation: Abschnitt 9, 12. Runbook ai-os `40-wissen/runbooks/release-und-update.md` Abschnitt A/B. Global Constraints in `index.md`.

**Wer:** Claude in der Hauptsitzung (kurz, braucht Überblick über Tasks 01–08).

**Voraussetzungen:** Tasks 01–08 erledigt und gepusht; CI auf `main` grün (Jobs `test` und `paket`).

- [ ] **Step 1: Stand prüfen**

```bash
git -C /root/erechnung-konverter pull --rebase origin main
git -C /root/erechnung-konverter status --short
git -C /root/erechnung-konverter log --oneline -n 15
```
Expected: sauber, alle Task-Commits da.

- [ ] **Step 2: Alle Tests inklusive echter Daten und Mustang**

Run: `ERECHNUNG_TESTDATEN=/root/erechnung-testdaten /root/.venvs/erechnung/bin/python -m pytest /root/erechnung-konverter/tests -q`
Expected: alle PASS, keine `echt`-Tests übersprungen.

- [ ] **Step 3: Secret-Prüfung vor dem Tag**

```bash
git -C /root/erechnung-konverter grep -n -I -E 'token [0-9a-f]{20,}|BEGIN (RSA|OPENSSH|PRIVATE)|LEXWARE.*=|password|passwort *[:=]'
```
Expected: keine Treffer außer Doku-Erwähnungen ohne Wert. Außerdem die Käufernamen der drei Lexware-Rechnungen (Käuferblock in `/root/erechnung-testdaten/RE01xx.txt`) einzeln mit `git -C /root/erechnung-konverter grep -n -i '<name>'` suchen → keine Treffer. Rechnungsnummern RE0146/48/49 in Doku und Tests sind unkritisch.

- [ ] **Step 4: Tag setzen**

```bash
git -C /root/erechnung-konverter tag v0.1.0
git -C /root/erechnung-konverter push origin v0.1.0
```

- [ ] **Step 5: Release-Workflow abwarten** – Forgejo → Repo → Actions, Lauf `release` für `v0.1.0` grün. Bei rot: Log lesen, Ursache beheben, **neue** Version `v0.1.1` taggen (CI-409 bei gleichem Tag, Runbook Fehlerbilder).

- [ ] **Step 6: Artefakt prüfen** (Token nie ausgeben)

```bash
curl -fsS -o /tmp/erechnung-release.json -H "Authorization: token $(cat /root/.config/gm-it-os/update-test.token)" https://git.gm-itsolutions.de/api/packages/gm-itsolutions/generic/erechnung-konverter/0.1.0/release.json
```
```bash
python3 -m json.tool /tmp/erechnung-release.json
```
Expected: `produkt` = `erechnung-konverter`, Artefakt `erechnung-konverter-0.1.0-windows-amd64.zip` mit `sha256` und `groesse`. ZIP ebenso nach `/tmp/` laden, `sha256sum` vergleichen, `unzip -p … app/erechnung/__init__.py` → `__version__ = "0.1.0"`.

- [ ] **Step 7: Cockpit-Punkt für die Freigabe** (Marvin sieht ihn beim Sitzungsstart; kein Telegram)

```bash
python3 /root/ai-os/tools/cockpit/thema.py "Freigabe erechnung-konverter 0.1.0" "Release liegt in der Paketablage, Tests + Mustang grün. Bitte unter https://freigabe.gm-itsolutions.de freigeben (Task 11). VM-Test ohne Freigabe läuft bereits (Task 10)."
```
(Einzige Änderung außerhalb des Repos, über das vorgesehene Werkzeug; keine Datei in ai-os von Hand ändern.)

- [ ] **Step 8:** Status in `docs/plan/index.md` (Tasks 01–09 → erledigt) nachziehen, committen, pushen.
