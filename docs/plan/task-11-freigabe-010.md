# Task 11: Freigabe `v0.1.0` (Marvin, YubiKey)

Runbook ai-os `40-wissen/runbooks/release-und-update.md` Abschnitt A. **Nur Marvin** – Claude kann und darf nicht freigeben.

**Voraussetzung:** Task 09 erledigt (Release in der Paketablage, CI grün, Mustang gültig). Cockpit-Punkt „Freigabe erechnung-konverter 0.1.0“ liegt vor.

## Schritte (Fedora mit USB-YubiKey oder Handy mit NFC)

1. `https://freigabe.gm-itsolutions.de` öffnen, Passwort „GM Freigabe (Caddy)“ aus dem Passwortmanager.
2. In der Übersicht **erechnung-konverter 0.1.0** (Kanal stabil) anklicken. Erstes Produkt auf gm-update außer den Testprodukten: es gibt noch keine Vorversion, der Zeiger wird neu angelegt.
3. Detailseite prüfen:
   - Commit verlinkt auf `gm-itsolutions/erechnung-konverter`, Commit-Liste passt zu den Tasks 01–08.
   - Artefakt `erechnung-konverter-0.1.0-windows-amd64.zip`, Größe ca. 40–60 MB, SHA-256 identisch mit der Angabe aus Task 09 (Claude nennt die ersten 12 Zeichen im Cockpit-Punkt).
4. „Freigeben mit YubiKey“ → PIN → berühren.
5. Meldung „Freigegeben: erechnung-konverter 0.1.0 (latest.json)“.
6. Im Cockpit den Punkt erledigen bzw. Claude „freigegeben“ sagen → Task 12 startet.

## Fehlerbilder

- Version fehlt in der Übersicht: Release-CI nicht durchgelaufen (Task 09 Step 5).
- 503 „keine Schlüssel“ / 502 „Zeiger unlesbar“: Runbook-Fehlerbilder.
