"use strict";
// Anlern-Oberfläche: Muster hochladen, Felder per Rahmen markieren (docs/lernmodus/spezifikation.md 7.1, 7.2).
// Kein Framework, kein Inline-Code (CSP); Farben nur aus den Tokens in gm.css.
const CSRF = document.querySelector('meta[name="csrf"]').content;
async function api(methode, pfad, body, typ = "application/json", kopf = {}) {
  let r;
  try {
    r = await fetch(pfad, {method: methode, headers: methode === "GET" ? {} : {"X-CSRF": CSRF, "Content-Type": typ, ...kopf},
      body: body === undefined ? undefined : (typ === "application/json" ? JSON.stringify(body) : body)});
  } catch {   // Server beendet (Leerlauf, „Beenden“): sonst englisches „Failed to fetch“
    throw new Error("Verbindung zum Anlern-Programm unterbrochen – bitte über das Startmenü neu öffnen.");
  }
  const t = r.headers.get("Content-Type") || "";
  const daten = t.startsWith("application/json") ? await r.json() : await r.blob();
  if (!r.ok) throw new Error(daten.fehler || `Fehler ${r.status}`);
  return daten;
}
const r4 = (x) => Math.round(x * 10000) / 10000;
function relativ(ev, canvas) {   // Mausposition → Seitenkoordinaten 0..1
  const b = canvas.getBoundingClientRect();
  return {x: Math.min(1, Math.max(0, (ev.clientX - b.left) / b.width)), y: Math.min(1, Math.max(0, (ev.clientY - b.top) / b.height))};
}
const mitteY = (w) => (w[2] + w[4]) / 2;           // w = [text, x0, top, x1, bottom]
function umriss(ws) {
  return [r4(Math.min(...ws.map(w => w[1]))), r4(Math.min(...ws.map(w => w[2]))), r4(Math.max(...ws.map(w => w[3]))), r4(Math.max(...ws.map(w => w[4])))];
}
function satzWort(w, woerter) {   // „19“, „19,00“, „7%“ direkt vor „%“: wird in satzPlatzhalter zu {satz}, bleibt Anker
  if (!/^\d{1,2}(?:[.,]\d{1,2})?%?$/.test(w[0])) return false;
  return w[0].endsWith("%") || woerter.some(v => v[0].startsWith("%") && Math.abs(mitteY(v) - mitteY(w)) < (w[4] - w[2]) / 2
    && v[1] >= w[3] - 0.002 && v[1] - w[3] < 0.02);
}
// Beträge, Daten und Kennungen (BW-2026-17) ändern sich je Rechnung: nie Anker; Steuersätze ausgenommen
const veraenderlich = (w, woerter) => !satzWort(w, woerter) && (/\d[.,]\d/.test(w[0]) || (w[0].match(/\d/g) || []).length >= 3);
function ankerVorschlag(rahmen, woerter) {
  // 1. Wörter links vom Rahmen in derselben Zeile (zusammenhängend, höchstens 4, Lücke < 0,03)
  const [x0, y0, , y1] = rahmen;
  woerter = woerter.filter(w => !veraenderlich(w, woerter));
  const links = woerter.filter(w => mitteY(w) >= y0 && mitteY(w) <= y1 && w[3] <= x0 + 0.002).sort((a, b) => b[1] - a[1]);
  const kette = [];
  for (const w of links) {
    if (kette.length && kette[kette.length - 1][1] - w[3] > 0.03) break;
    if (!kette.length && x0 - w[3] > 0.3) break;     // Plan: 0,15; Summenblöcke stehen oft weiter rechts
    kette.push(w);
    if (kette.length === 4) break;
  }
  // 2. sonst die Zeile direkt darüber, waagerecht überlappend
  if (!kette.length) {
    const drueber = woerter.filter(w => w[4] <= y0 + 0.002 && y0 - w[4] < 0.03 && w[3] > rahmen[0] && w[1] < rahmen[2]);
    const yMax = Math.max(...drueber.map(mitteY));
    kette.push(...drueber.filter(w => Math.abs(mitteY(w) - yMax) < 0.004).sort((a, b) => a[1] - b[1]).slice(0, 4));
  } else {
    kette.sort((a, b) => a[1] - b[1]);
  }
  return kette.length ? {text: kette.map(w => w[0]).join(" "), rahmen: umriss(kette)} : null;
}
function satzPlatzhalter(text) {   // „MwSt. 19 %“ → „MwSt. {satz} %“
  return text.replace(/\d{1,2}(?:[.,]\d{1,2})?(?=\s*%)/, "{satz}");
}

// ---------- Feste Listen ----------
const PFLICHT = [["nummer", "Rechnungsnummer"], ["datum", "Rechnungsdatum"], ["kaeufer", "Käufer"],
  ["summe_netto", "Summe netto"], ["summe_brutto", "Gesamtbetrag"], ["positionen", "Positionen"]];
const OPTIONAL = [["nummer_kontrolle", "Zweite Fundstelle der Nummer"], ["leistungsdatum", "Leistungsdatum"], ["faellig", "Fälligkeit"],
  ["zahlungsziel_tage", "Zahlungsziel in Tagen"], ["summe_ust", "Umsatzsteuer gesamt"], ["steuern", "Steuerzeile"], ["nachlass", "Nachlass"]];
const BESCHRIFTUNG = Object.fromEntries([...PFLICHT, ...OPTIONAL]);
const FELDER = [...PFLICHT, ...OPTIONAL].map(f => f[0]).filter(n => n !== "positionen" && n !== "steuern");   // bereiche.FELDER
const AM_ENDE = new Set(["summe_netto", "summe_ust", "summe_brutto", "nachlass", "steuern"]);
const SPALTEN = [["nr", "Pos.-Nr."], ["bezeichnung", "Bezeichnung"], ["menge", "Menge"], ["einheit", "Einheit"],
  ["menge_einheit", "Menge mit Einheit"], ["einzelpreis", "Einzelpreis"], ["ust_satz", "USt-Satz"], ["netto", "Gesamt netto"], ["ignorieren", "ignorieren"]];
const SAETZE = [19, 7];
const MAX_PDF = 10 * 1024 * 1024;
const NAME = /^[a-z0-9][a-z0-9-]{1,39}$/;

// ---------- Zustand ----------
const S = {stand: null, name: null, vorlage: null, muster: [], aktiv: null, seite: 1, gen: 0,
  wp: {}, woerter: {}, werte: {}, uiSeite: {}, posOben: null, modus: null, zug: null, hover: null, timer: null,
  probe: null, probeNr: 0, probeOffen: false, spur: null, uac: null, erfolg: null};   // probe: {laeuft} | {ergebnis, haken}; uac: wartende Aktion
const uacHinweis = (folge) => `Windows fragt gleich nach einem Administrator-Konto. Ohne Freigabe ${folge}. `
  + "Unter „Details“ muss als Befehlszeile „-m erechnung vorlage …“ stehen, sonst „Nein“ wählen.";
const UAC_WARTEN = "Warte auf die Administrator-Freigabe in Windows …";
const $ = (id) => document.getElementById(id);
function el(tag, attr = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attr)) {
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, "");
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  e.append(...kinder.filter(k => k != null && k !== false));
  return e;
}
const knopf = (text, onclick, attr = {}) => el("button", {type: "button", class: "btn btn-secondary btn-sm", onclick, ...attr}, text);
function auswahl(id, optionen, wert, onchange) {
  const s = el("select", {id, onchange: () => onchange(s.value)}, ...optionen.map(([w, t]) => el("option", {value: w}, t)));
  s.value = String(wert);
  return s;
}
function meldung(text, art = "err") { const m = $("meldung"); m.className = `alert ${art}`; m.textContent = text; m.hidden = false; }
const fehler = (text) => meldung(text, "err");
function meldungWeg() { $("meldung").hidden = true; }
async function mitMeldung(f) {
  meldungWeg();
  try { await f(); } catch (e) { fehler(e.message); }
}
const aktuellesMuster = () => S.muster.find(m => m.id === S.aktiv) || null;
const aktuelleWoerter = () => (S.woerter[S.aktiv] || [])[S.seite - 1] || [];
const farbe = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---------- Vorlagen und Entwürfe ----------
async function ladeStand() {
  S.stand = await api("GET", "/api/stand");
  renderVorlagen();
  $("muster-fehler").replaceChildren(el("option", {value: ""}, S.stand.fehlerordner.length ? "Datei wählen …" : "Fehler-Ordner ist leer"),
    ...S.stand.fehlerordner.map(d => el("option", {value: d}, d)));
}
function renderVorlagen() {
  if (!S.stand) return;
  const aus = S.uac !== null;     // während einer UAC-Abfrage keine zweite Aktion
  const k = (text, f, gefahr = false) => el("button", {type: "button", class: `btn btn-sm ${gefahr ? "btn-danger" : "btn-secondary"}`,
    disabled: aus, onclick: () => mitMeldung(f)}, text);
  const zeile = (n, art, pill, ...aktionen) => el("tr", {}, el("td", {class: "mono"}, n), el("td", {}, art), el("td", {}, pill),
    el("td", {}, el("div", {class: "zeilen-aktionen"}, ...aktionen)));
  const st = S.stand;
  $("vorlagen-liste").replaceChildren(
    ...st.mitgeliefert.map(n => zeile(n, "mitgeliefert", el("span", {class: "pill info"}, "mitgeliefert"))),
    ...st.aktiv.map(n => zeile(n, "angelernt", el("span", {class: "pill ok"}, "aktiv"),
      k("Deaktivieren", () => verwalten(n, "deaktivieren")), k("Löschen", () => verwalten(n, "loeschen"), true))),
    ...st.deaktiviert.map(n => zeile(n, "angelernt", el("span", {class: "pill warn"}, "deaktiviert"),
      k("Reaktivieren", () => verwalten(n, "reaktivieren")), k("Löschen", () => verwalten(n, "loeschen"), true))),
    ...st.entwuerfe.map(n => zeile(n, "angelernt", el("span", {class: "pill"}, "Entwurf"),
      k("Bearbeiten", () => { location.hash = `#anlernen/${n}`; }), k("Für GM IT exportieren", () => exportieren(n)),
      k("Entwurf löschen", () => entwurfLoeschen(n), true))));
  $("vorlagen-leer").hidden = st.aktiv.length + st.deaktiviert.length + st.entwuerfe.length > 0;
  const uac = $("vorlagen-uac");
  uac.hidden = !(st.aktiv.length + st.deaktiviert.length);
  uac.textContent = aus ? UAC_WARTEN : `Deaktivieren, Reaktivieren und Löschen: ${uacHinweis("bleibt alles unverändert")}`;
}
async function verwalten(name, aktion) {   // jede Verwaltungsaktion geht über UAC (F1), auch Löschen deaktivierter
  if (aktion === "loeschen" && !confirm(`Vorlage „${name}“ endgültig löschen? Rechnungen in diesem Layout landen danach wieder im Fehler-Ordner.`)) return;
  S.uac = name;
  renderVorlagen();
  let r;
  try {
    r = await api("POST", `/api/vorlage/${encodeURIComponent(name)}/${aktion}`, {});
  } finally {
    S.uac = null;
    try { await ladeStand(); } catch (e) { renderVorlagen(); }   // Ergebnis der Aktion nicht verdecken
  }
  meldung(r.meldung, r.ok ? "ok" : "err");
}
async function entwurfLoeschen(name) {
  if (!confirm(`Entwurf „${name}“ mit allen Mustern löschen?`)) return;
  await api("DELETE", `/api/entwurf/${encodeURIComponent(name)}`);
  if (S.name === name) {   // offener Entwurf: kein Speichern mehr hinterher
    clearTimeout(S.timer);
    Object.assign(S, {timer: null, name: null, vorlage: null, muster: [], aktiv: null, gen: S.gen + 1});
    probeZurueck();
  }
  await ladeStand();
}
async function exportieren(name) {   // nur vorlage.yml, keine Muster-PDFs (F2)
  const blob = await api("GET", `/api/entwurf/${encodeURIComponent(name)}/export`);
  const d = new Date(), tag = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const url = URL.createObjectURL(blob), a = el("a", {href: url, download: `erechnung-vorlage-${name}-${tag}.yml`, hidden: true});
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function speichernJetzt() {
  if (S.timer === null) return;
  clearTimeout(S.timer);
  S.timer = null;
  vorschlagErkennung();
  try { await api("PUT", `/api/entwurf/${S.name}`, S.vorlage); } catch (e) { fehler(`Speichern fehlgeschlagen: ${e.message}`); }
}
function speichern() {   // entprellt, ganze Vorlage; jede Änderung macht den Probelauf ungültig
  probeZurueck();
  clearTimeout(S.timer);
  S.timer = setTimeout(speichernJetzt, 500);
}
async function oeffneEntwurf(name) {
  await speichernJetzt();
  const d = await api("GET", `/api/entwurf/${encodeURIComponent(name)}`);
  // Muster-IDs werden nach dem Löschen neu vergeben: Zustand je Muster nie über das Öffnen hinaus behalten
  Object.assign(S, {wp: {}, woerter: {}, werte: {}, uiSeite: {}, posOben: null, modus: null, aktiv: null, gen: S.gen + 1});
  probeZurueck();
  S.name = name;
  S.vorlage = d.vorlage;
  S.vorlage.felder = S.vorlage.felder || {};
  S.muster = d.muster;
  if (!S.stand) await ladeStand();
  if (location.hash !== `#anlernen/${name}`) location.hash = `#anlernen/${name}`;
  if (!aktuellesMuster()) S.aktiv = null;
  if (S.aktiv) renderAnlernen();
  else if (S.muster.length) await waehleMuster(S.muster[0].id);
  else renderAnlernen();
}
async function ladeMuster() {   // nach Hinzufügen/Entfernen: Probelauf gilt nicht mehr
  probeZurueck();
  S.muster = (await api("GET", `/api/entwurf/${S.name}`)).muster;
}

// ---------- Muster ----------
function woerterVon(id) {   // OCR kann je Seite einige Sekunden dauern: Zustand „läuft“ sichtbar halten (W21)
  if (!S.wp[id]) {
    const gen = S.gen;
    S.wp[id] = api("GET", `/api/entwurf/${S.name}/muster/${id}/woerter`)
      .then(w => { if (gen === S.gen) S.woerter[id] = w; return w; })
      .catch(e => { if (gen === S.gen) delete S.wp[id]; throw e; })
      .finally(() => { if (gen === S.gen) { renderMuster(); renderHinweis(); renderFelder(); } });
    renderMuster();
    renderHinweis();
    renderFelder();
  }
  return S.wp[id];
}
const laedt = (id) => S.wp[id] && !S.woerter[id];
async function waehleMuster(id) {
  S.aktiv = id;
  S.seite = 1;
  S.werte = {};
  renderAnlernen();
  try { await woerterVon(id); } catch (e) { fehler(e.message); return; }
  zeichne();
  await aktualisiereWerte();
}
async function musterHochladen(datei) {
  if (datei.size > MAX_PDF) throw new Error("PDF zu groß (höchstens 10 MB).");
  const r = await api("POST", `/api/entwurf/${S.name}/muster`, datei, "application/pdf", {"X-Dateiname": encodeURIComponent(datei.name)});
  await ladeMuster();
  await waehleMuster(r.id);
}
async function musterAusFehler(datei) {
  const r = await api("POST", `/api/entwurf/${S.name}/muster-aus-fehler`, {datei});
  await ladeMuster();
  await waehleMuster(r.id);
}
async function musterLoeschen(id) {
  if (!confirm("Muster entfernen?")) return;
  await api("DELETE", `/api/entwurf/${S.name}/muster/${id}`);
  // IDs werden nach dem Löschen neu vergeben: allen Zustand zu Mustern verwerfen
  Object.assign(S, {wp: {}, woerter: {}, werte: {}, gen: S.gen + 1});
  await ladeMuster();
  if (S.aktiv === id || !aktuellesMuster()) S.aktiv = null;
  if (S.muster.length) await waehleMuster(S.aktiv || S.muster[0].id);
  else renderAnlernen();
}
async function vorschau(name) {
  const id = S.aktiv, f = S.vorlage.felder[name];
  if (!id || !f) return;
  try {
    const r = await api("POST", `/api/entwurf/${S.name}/vorschau`, {feld: name, felder: S.vorlage.felder, muster: id});
    if (id === S.aktiv) S.werte[name] = r;
  } catch (e) {
    if (id === S.aktiv) S.werte[name] = {wert: null, fehler: e.message};
  }
  renderFelder();
}
async function aktualisiereWerte() {
  for (const n of FELDER) if (S.vorlage.felder[n]) await vorschau(n);
}

// ---------- Markieren ----------
function seiteFuer(name) {   // mehrseitiges Muster: auf der letzten Seite markiert → „letzte“
  const m = aktuellesMuster();
  if (m && m.seiten > 1) return S.seite === m.seiten ? "letzte" : "erste";
  return AM_ENDE.has(name) ? "letzte" : "erste";
}
function seiteVon(schluessel, seite) {   // Seite des Musters, auf der ein Rahmen gezeichnet wird
  const m = aktuellesMuster();
  return S.uiSeite[schluessel] || (seite === "letzte" && m ? m.seiten : 1);
}
function wortBei(p) {
  return aktuelleWoerter().find(w => p.x >= w[1] - 0.002 && p.x <= w[3] + 0.002 && p.y >= w[2] - 0.002 && p.y <= w[4] + 0.002) || null;
}
function ankerAusWort(w, rahmen, woerter, max = 4) {   // das Wort und rechts angrenzende derselben Zeile bis zum Rahmen
  const zeile = woerter.filter(v => Math.abs(mitteY(v) - mitteY(w)) < (w[4] - w[2]) / 2 && v[1] >= w[1]).sort((a, b) => a[1] - b[1]);
  const kette = [];
  for (const v of zeile) {
    const xm = (v[1] + v[3]) / 2;
    if (rahmen && xm >= rahmen[0] && xm <= rahmen[2] && mitteY(v) >= rahmen[1] && mitteY(v) <= rahmen[3]) break;
    if (kette.length && v[1] - kette[kette.length - 1][3] > 0.03) break;
    kette.push(v);
    if (kette.length === max) break;
  }
  return kette.length ? {text: kette.map(v => v[0]).join(" ").slice(0, 80), rahmen: umriss(kette)} : null;
}
function steuerAnker(s, a) {
  if (!a) { delete s.anker; return; }
  s.anker = {text: satzPlatzhalter(a.text), rahmen: a.rahmen};
  if (s.anker.text.includes("{satz}")) delete s.satz;
  else s.satz = s.satz || SAETZE[0];
}
function setzeFeld(name, rahmen) {
  const ws = aktuelleWoerter(), seite = seiteFuer(name);
  S.uiSeite[name] = S.seite;
  if (name === "steuern") {
    const s = {seite, rahmen, satz: (S.vorlage.steuern || {}).satz};
    steuerAnker(s, ankerVorschlag(rahmen, ws));
    if (!s.satz) delete s.satz;
    S.vorlage.steuern = s;
  } else {
    const f = {seite, rahmen};
    const a = name === "kaeufer" ? null : ankerVorschlag(rahmen, ws);
    if (a) f.anker = {text: a.text.slice(0, 80), rahmen: a.rahmen};
    S.vorlage.felder[name] = f;
  }
  S.modus = name === "kaeufer" ? null : {art: "anker", name};
  aenderung(name);
}
function ankerKlick(name, w) {
  const f = name === "steuern" ? S.vorlage.steuern : S.vorlage.felder[name];
  const a = ankerAusWort(w, f.rahmen, aktuelleWoerter());
  if (!a) return;
  if (name === "steuern") steuerAnker(f, a);
  else f.anker = a;
  aenderung(name);
}
function ohneAnker(name) {
  delete S.vorlage.felder[name].anker;
  S.modus = null;
  aenderung(name);
}
function entfernen(name) {
  if (name === "steuern" || name === "positionen") delete S.vorlage[name];
  else delete S.vorlage.felder[name];
  delete S.werte[name];
  if (S.modus && (S.modus.name === name || (name === "positionen" && S.modus.art.startsWith("pos-")))) S.modus = null;
  aenderung(name);
  if (FELDER.includes(name)) aktualisiereWerte();   // Felder ohne Anker hängen am Anker der Nummer
}
function aenderung(name) {
  speichern();
  if (FELDER.includes(name)) {
    delete S.werte[name];
    vorschau(name);
    if (name === "nummer") for (const n of FELDER) if (n !== "nummer" && S.vorlage.felder[n] && !S.vorlage.felder[n].anker) vorschau(n);
  }
  if (name === "positionen") renderSpalten();
  renderFelder();
  renderModus();
  zeichne();
}
// Positionstabelle in Schritten
function setzeTabelle(r) {
  const alt = S.vorlage.positionen || {};
  const p = {links: r[0], unten: r[3], spalten: [{bis: r[2], art: "bezeichnung"}]};
  if (alt.kopf) p.kopf = alt.kopf;
  if (alt.ende) p.ende = alt.ende;
  if (alt.ust_satz) p.ust_satz = alt.ust_satz;
  S.vorlage.positionen = p;
  S.posOben = r[1];
  S.uiSeite.positionen = S.seite;
  S.modus = {art: "pos-kopf", name: "positionen"};
  aenderung("positionen");
}
function setzeKopf(w) {
  const p = S.vorlage.positionen, rechts = p.spalten[p.spalten.length - 1].bis;
  const zeile = aktuelleWoerter().filter(v => Math.abs(mitteY(v) - mitteY(w)) < (w[4] - w[2]) / 2
    && (v[1] + v[3]) / 2 >= p.links && (v[1] + v[3]) / 2 <= rechts).sort((a, b) => a[1] - b[1]).slice(0, 3);
  if (!zeile.length) return;
  p.kopf = {text: zeile.map(v => v[0]).join(" ").slice(0, 80), rahmen: umriss(zeile)};
  S.modus = {art: "pos-spalten", name: "positionen"};
  aenderung("positionen");
}
function schalteSpalte(x) {   // Klick auf vorhandene Linie entfernt sie, sonst neue Grenze
  const p = S.vorlage.positionen, rechts = p.spalten[p.spalten.length - 1].bis;
  const i = p.spalten.slice(0, -1).findIndex(s => Math.abs(s.bis - x) < 0.006);
  if (i >= 0) p.spalten.splice(i, 1);
  else if (x > p.links + 0.005 && x < rechts - 0.005) p.spalten.splice(p.spalten.findIndex(s => s.bis > x), 0, {bis: r4(x), art: "ignorieren"});
  else return;
  aenderung("positionen");
}
function setzeEnde(w) {
  const a = ankerAusWort(w, null, aktuelleWoerter(), 3);
  if (!a) return;
  S.vorlage.positionen.ende = a;
  S.modus = {art: "pos-spalten", name: "positionen"};
  aenderung("positionen");
}
function setzeUnten(y) {
  S.vorlage.positionen.unten = r4(y);
  S.modus = {art: "pos-spalten", name: "positionen"};
  aenderung("positionen");
}
function markieren(name) {
  meldungWeg();
  if (!aktuellesMuster()) return fehler("Zuerst ein Muster hinzufügen.");
  S.modus = name === "positionen" ? {art: "pos-tabelle", name} : {art: "feld", name};
  S.spur = null;
  renderFelder();
  renderModus();
  zeichne();
  $("hinweis").scrollIntoView({block: "nearest"});   // Feldliste ist lang: Bild in Sicht holen
}
function vorschlagErkennung() {   // beim ersten Speichern: Anker der Nummer plus längste Zeile im oberen Viertel
  const v = S.vorlage, n = v.felder.nummer, seiten = S.woerter[S.aktiv];
  if (v.schluesselwoerter !== undefined || !n || !n.anker || !seiten) return;
  const oben = zeilenVon(seiten[0].filter(w => w[2] < 0.25)).map(z => z.map(w => w[0]).join(" ").slice(0, 80));
  const laengste = oben.reduce((a, b) => (b.length > a.length ? b : a), "");
  v.schluesselwoerter = [...new Set([n.anker.text, laengste])].filter(t => t.length >= 3);
  $("erkennung").value = v.schluesselwoerter.join(", ");
}
function zeilenVon(ws) {   // wie bereiche.zeilen: Toleranz halbe mittlere Wordhöhe
  if (!ws.length) return [];
  const h = ws.map(w => w[4] - w[2]).sort((a, b) => a - b), tol = h[Math.floor(h.length / 2)] / 2;
  const z = [];
  for (const w of [...ws].sort((a, b) => mitteY(a) - mitteY(b))) {
    if (z.length && mitteY(w) - mitteY(z[z.length - 1][0]) <= tol) z[z.length - 1].push(w);
    else z.push([w]);
  }
  return z.map(r => r.sort((a, b) => a[1] - b[1]));
}

// ---------- Zeichnen ----------
function groesse() {
  const b = $("seitenbild").getBoundingClientRect(), d = window.devicePixelRatio || 1, c = $("leinwand");
  c.width = Math.round(b.width * d);
  c.height = Math.round(b.height * d);
  zeichne();
}
function zeichne() {
  const c = $("leinwand"), ctx = c.getContext("2d"), W = c.width, H = c.height, d = window.devicePixelRatio || 1;
  ctx.clearRect(0, 0, W, H);
  if (!W || !S.vorlage || !aktuellesMuster()) return;
  const wert = farbe("--amber"), anker = farbe("--info"), dumpf = farbe("--ink-muted");
  ctx.font = `${11 * d}px "IBM Plex Mono", monospace`;
  const rahmen = (r, f, text, breite = 2, strich = []) => {
    ctx.strokeStyle = f;
    ctx.lineWidth = breite * d;
    ctx.setLineDash(strich.map(x => x * d));
    ctx.strokeRect(r[0] * W, r[1] * H, (r[2] - r[0]) * W, (r[3] - r[1]) * H);
    ctx.setLineDash([]);
    if (text) { ctx.fillStyle = f; ctx.fillText(text, r[0] * W, r[1] * H - 3 * d); }
  };
  for (const [n, f] of Object.entries(S.spur && S.spur.id === S.aktiv ? {} : S.vorlage.felder)) {
    if (seiteVon(n, f.seite) !== S.seite) continue;
    rahmen(f.rahmen, wert, BESCHRIFTUNG[n] || n);
    if (f.anker) rahmen(f.anker.rahmen, anker, "");
  }
  const s = S.vorlage.steuern;
  if (s && !(S.spur && S.spur.id === S.aktiv) && seiteVon("steuern", s.seite) === S.seite) {
    rahmen(s.rahmen, wert, "Steuerzeile");
    if (s.anker) rahmen(s.anker.rahmen, anker, "");
  }
  const p = S.vorlage.positionen;
  if (S.spur && S.spur.id === S.aktiv) {   // Probelauf: gefundene Rahmen grün, angelernte ohne Fund rot
    const ok = farbe("--ok"), err = farbe("--err"), sp = Object.entries(S.spur.spur);
    const name = (k) => BESCHRIFTUNG[k] || (k.startsWith("steuern") ? "Steuerzeile" : k.startsWith("positionen") ? "Positionen" : k);
    for (const [k, e] of sp) if (e.seite + 1 === S.seite) rahmen(e.rahmen, ok, name(k));
    const fehlt = (k) => !sp.some(([n]) => n === k || (n.startsWith(k) && /^\d+$/.test(n.slice(k.length))));
    for (const [n, f] of Object.entries(S.vorlage.felder)) if (fehlt(n) && seiteVon(n, f.seite) === S.seite) rahmen(f.rahmen, err, name(n));
    if (s && fehlt("steuern") && seiteVon("steuern", s.seite) === S.seite) rahmen(s.rahmen, err, "Steuerzeile");
    if (p && p.spalten && fehlt("positionen") && seiteVon("positionen", "erste") === S.seite) {
      rahmen([p.links, p.kopf ? p.kopf.rahmen[3] : (S.posOben ?? 0), p.spalten[p.spalten.length - 1].bis, p.unten], err, "Positionen");
    }
    return;
  }
  if (p && p.spalten && seiteVon("positionen", "erste") === S.seite) {
    const rechts = p.spalten[p.spalten.length - 1].bis, oben = p.kopf ? p.kopf.rahmen[3] : (S.posOben ?? 0);
    rahmen([p.links, oben, rechts, p.unten], dumpf, "Positionen", 1.5);
    ctx.strokeStyle = dumpf;
    ctx.lineWidth = 1.5 * d;
    for (const sp of p.spalten.slice(0, -1)) {
      ctx.beginPath(); ctx.moveTo(sp.bis * W, oben * H); ctx.lineTo(sp.bis * W, p.unten * H); ctx.stroke();
    }
    p.spalten.forEach((sp, i) => { ctx.fillStyle = dumpf; ctx.fillText(String(i + 1), ((i ? p.spalten[i - 1].bis : p.links) + 0.004) * W, (oben + 0.014) * H); });
    if (p.kopf) rahmen(p.kopf.rahmen, anker, "Kopf");
    if (p.ende) rahmen(p.ende.rahmen, anker, "Ende");
  }
  if (S.hover) rahmen([S.hover[1], S.hover[2], S.hover[3], S.hover[4]], dumpf, "", 1);
  if (S.zug) rahmen([Math.min(S.zug.x0, S.zug.x1), Math.min(S.zug.y0, S.zug.y1), Math.max(S.zug.x0, S.zug.x1), Math.max(S.zug.y0, S.zug.y1)], wert, "", 2, [6, 4]);
}

// ---------- Darstellung ----------
function renderAnlernen() {
  const da = !!S.name;
  $("anlernen-leer").hidden = da;
  $("anlernen-inhalt").hidden = !da;
  if (!da) return;
  $("anlernen-titel").textContent = `Vorlage anlernen: ${S.name}`;
  $("erkennung").value = (S.vorlage.schluesselwoerter || []).join(", ");
  renderMuster();
  renderFelder();
  renderSeite();
  renderSpalten();
  renderModus();
  renderProbe();
}
function renderMuster() {
  if (!S.name) return;
  $("muster-leer").hidden = S.muster.length > 0;
  $("muster-liste").replaceChildren(...S.muster.map(m => el("li", {"aria-current": m.id === S.aktiv ? "true" : false},
    el("span", {class: "name"}, m.datei),
    el("span", {class: "muted"}, `${m.seiten} S.`),
    laedt(m.id) ? el("span", {class: "pill info"}, m.text ? "Wörter werden gelesen …" : "Texterkennung läuft …")
      : el("span", {class: m.text ? "pill" : "pill info"}, m.text ? "Text" : "Bild, Texterkennung"),
    m.id === S.aktiv ? null : knopf("Anzeigen", () => mitMeldung(() => waehleMuster(m.id))),
    knopf("Entfernen", () => mitMeldung(() => musterLoeschen(m.id))))));
  $("muster-wahl").replaceChildren(...S.muster.map(m => el("option", {value: m.id}, `${m.id} · ${m.datei}`)));
  $("muster-wahl").value = S.aktiv || "";
}
function feldZeile(name, label) {
  const v = S.vorlage, p = v.positionen;
  const markiert = name === "steuern" ? !!(v.steuern && v.steuern.anker)
    : name === "positionen" ? !!(p && p.kopf && p.spalten && p.spalten.length >= 2) : !!v.felder[name];
  const vorhanden = name === "steuern" ? !!v.steuern : name === "positionen" ? !!p : !!v.felder[name];
  const pflicht = PFLICHT.some(f => f[0] === name);
  const aktiv = S.modus && S.modus.name === name;
  const zeile = el("li", {"aria-current": aktiv ? "true" : false},
    el("span", {class: "name"}, label),
    el("span", {class: markiert ? "pill ok" : pflicht ? "pill warn" : "pill"}, markiert ? "markiert" : "fehlt"),
    el("button", {type: "button", class: "btn btn-secondary btn-sm", "aria-pressed": aktiv ? "true" : "false",
      disabled: !S.aktiv || laedt(S.aktiv), onclick: () => markieren(name)}, "Markieren"),
    vorhanden ? knopf("Entfernen", () => entfernen(name)) : null);
  const info = [];
  if (FELDER.includes(name) && v.felder[name]) {
    const w = S.werte[name];
    if (w && w.fehler) info.push(el("span", {class: "wert err"}, w.fehler));
    else if (w) info.push(el("span", {class: "wert"}, w.wert === null ? "–" : w.wert));
    info.push(el("span", {class: "wert"}, v.felder[name].anker ? `Anker „${v.felder[name].anker.text}“` : name === "kaeufer" ? "ohne Anker (folgt der Nummer)" : "ohne Anker"));
  } else if (name === "steuern" && v.steuern) {
    info.push(el("span", {class: v.steuern.anker ? "wert" : "wert err"}, v.steuern.anker ? `Anker „${v.steuern.anker.text}“` : "Anker fehlt: Wort vor dem Betrag anklicken"));
    if (v.steuern.anker && !v.steuern.anker.text.includes("{satz}")) {
      const s = auswahl("steuersatz", SAETZE.map(x => [x, `${x} %`]), v.steuern.satz, (x) => { v.steuern.satz = Number(x); aenderung("steuern"); });
      info.push(el("label", {for: "steuersatz", class: "unsichtbar"}, "Steuersatz"), s);
    }
  } else if (name === "positionen" && p) {
    info.push(el("span", {class: "wert"}, `${p.spalten.length} Spalten${p.kopf ? ` · Kopf „${p.kopf.text}“` : " · Kopfzeile fehlt"}${p.ende ? ` · Ende „${p.ende.text}“` : ""}`));
    if (!aktiv) info.push(knopf("Tabelle bearbeiten", () => { S.modus = {art: "pos-spalten", name}; renderFelder(); renderModus(); zeichne(); $("hinweis").scrollIntoView({block: "nearest"}); }));
  }
  zeile.append(...info);
  return zeile;
}
function renderFelder() {
  if (!S.name) return;
  $("felder-liste").replaceChildren(...PFLICHT.map(([n, l]) => feldZeile(n, l)),
    el("li", {class: "gruppe"}, "Optional"), ...OPTIONAL.map(([n, l]) => feldZeile(n, l)));
}
function renderSeite() {
  const m = aktuellesMuster(), img = $("seitenbild");
  $("bild").hidden = !m;
  $("seite-anzeige").textContent = m ? `${S.seite}/${m.seiten}` : "–";
  $("seite-zurueck").disabled = !m || S.seite <= 1;
  $("seite-vor").disabled = !m || S.seite >= m.seiten;
  if (!m) return;
  const src = `/api/entwurf/${S.name}/muster/${m.id}/seite/${S.seite}.png?g=${S.gen}`;
  if (img.getAttribute("src") !== src) img.src = src;
  img.alt = `Seite ${S.seite} von ${m.datei}`;
  zeichne();
}
function renderSpalten() {
  const p = S.vorlage && S.vorlage.positionen, box = $("spalten-wahl");
  if (!p || !p.spalten) return box.replaceChildren();
  const felder = p.spalten.map((s, i) => el("div", {class: "field"}, el("label", {for: `spalte-${i}`}, `Spalte ${i + 1}`),
    auswahl(`spalte-${i}`, SPALTEN, s.art, (x) => { s.art = x; aenderung("positionen"); })));
  if (!p.spalten.some(s => s.art === "ust_satz")) {
    felder.push(el("div", {class: "field"}, el("label", {for: "pos-satz"}, "USt-Satz"),
      auswahl("pos-satz", SAETZE.map(x => [x, `${x} %`]), p.ust_satz || SAETZE[0], (x) => { p.ust_satz = Number(x); aenderung("positionen"); })));
  }
  box.replaceChildren(...felder);
}
const HINWEIS = {
  "pos-tabelle": "Rahmen um die ganze Positionstabelle ohne Kopfzeile ziehen, bis unter die letzte Position. Nicht zu knapp ziehen, lieber etwas Rand lassen.",
  "pos-kopf": "Kopfzeile der Tabelle anklicken (z. B. „Pos. Bezeichnung Menge“).",
  "pos-spalten": "Zwischen die Spalten klicken, um Grenzen zu setzen; Klick auf eine Linie entfernt sie. Unter dem Bild je Spalte die Art wählen.",
  "pos-ende": "Wort anklicken, mit dem die Tabelle endet (z. B. „Zwischensumme“).",
  "pos-unten": "Höhe anklicken, ab der der Fußbereich beginnt.",
};
function renderHinweis() {
  const h = $("hinweis"), m = S.modus;
  let t;
  if (!aktuellesMuster()) t = "Zuerst ein Muster hinzufügen.";
  else if (laedt(S.aktiv)) t = aktuellesMuster().text ? "Wörter werden gelesen …" : "Texterkennung läuft, das dauert je Seite einige Sekunden …";
  else if (S.spur && S.spur.id === S.aktiv) t = "Probelauf: grün die gefundenen Rahmen, rot angelernte Felder ohne Fund (an der angelernten Stelle).";
  else if (!m) t = "Feld wählen und „Markieren“ drücken.";
  else if (m.art === "feld") t = m.name === "kaeufer" ? "Rahmen um die Anschrift des Käufers ziehen (Name bis PLZ und Ort). Esc bricht ab."
    : m.name === "steuern" ? "Rahmen um den Steuerbetrag einer Steuerzeile ziehen (z. B. hinter „MwSt. 19 %“). Esc bricht ab."
    : `Rahmen um den Wert „${BESCHRIFTUNG[m.name]}“ ziehen, nicht zu knapp. Esc bricht ab.`;
  else if (m.art === "anker") {
    const f = m.name === "steuern" ? S.vorlage.steuern : S.vorlage.felder[m.name];
    t = f && f.anker ? `Anker „${f.anker.text}“ (blau). Ein anderes Wort anklicken setzt einen anderen Anker.`
      : "Kein Anker gefunden. Wort links neben dem Wert anklicken" + (m.name === "steuern" ? "." : " oder „ohne Anker“ wählen.");
  } else t = HINWEIS[m.art];
  h.textContent = t;
}
function renderModus() {
  renderHinweis();
  const m = S.modus, box = $("modus-aktionen"), k = [];
  const fertig = () => { S.modus = null; renderFelder(); renderModus(); zeichne(); };
  const modus = (art, text) => knopf(text, () => { S.modus = {art, name: "positionen"}; renderModus(); zeichne(); }, {"aria-pressed": m && m.art === art ? "true" : "false"});
  if (S.spur && S.spur.id === S.aktiv) k.push(knopf("Rahmen ausblenden", () => { S.spur = null; renderModus(); zeichne(); }));
  if (m && m.art === "feld") k.push(knopf("Abbrechen", fertig));
  if (m && m.art === "anker") {
    if (m.name !== "steuern") k.push(knopf("ohne Anker", () => ohneAnker(m.name)));
    k.push(knopf("Fertig", fertig));
  }
  if (m && m.art.startsWith("pos-") && S.vorlage.positionen) {
    k.push(modus("pos-kopf", "Kopfzeile"), modus("pos-spalten", "Spaltengrenzen"), modus("pos-ende", "Ende der Tabelle"), modus("pos-unten", "Fußbereich"));
    if (S.vorlage.positionen.ende) k.push(knopf("Ende entfernen", () => { delete S.vorlage.positionen.ende; aenderung("positionen"); }));
    k.push(knopf("Fertig", fertig));
  } else if (m && m.art === "pos-tabelle") k.push(knopf("Abbrechen", fertig));
  box.replaceChildren(...k);
}

// ---------- Probelauf und Aktivieren ----------
function probeZurueck() {   // Vorlage oder Muster geändert: Ergebnis und laufender Probelauf gelten nicht mehr
  if (S.probe === null && S.spur === null) return;
  S.probe = null;
  S.spur = null;
  S.probeNr += 1;
  renderProbe();
}
async function probelauf() {
  if (S.probeOffen) return;
  S.probeOffen = true;   // Knopf gesperrt, bis der Request zurück ist – auch wenn probeZurueck() das Ergebnis schon verworfen hat
  renderKopf();
  try {
    await speichernJetzt();
    const nr = S.probeNr + 1, name = S.name;
    S.probeNr = nr;
    S.probe = {laeuft: true};
    S.spur = null;
    renderProbe();
    zeichne();
    try {
      // läuft synchron auf dem Server, bei Bild-PDFs mit Texterkennung auch Minuten: bewusst ohne Zeitgrenze
      const ergebnis = await api("POST", `/api/entwurf/${encodeURIComponent(name)}/probelauf`, {});
      if (nr === S.probeNr && name === S.name) zeigeProbelauf(ergebnis);
    } catch (e) {
      if (nr === S.probeNr && name === S.name) { S.probe = null; renderProbe(); throw e; }   // veralteter Lauf: still
    }
  } finally {
    S.probeOffen = false;
    renderKopf();
  }
}
const euro = (b) => `${b} €`;
const satz = (x) => `${String(x).replace(".", ",").replace(/,0+$/, "")} %`;
function zeigeProbelauf(ergebnis) {
  S.probe = {ergebnis, haken: new Set()};
  renderProbe();
  $("probe").scrollIntoView({block: "start"});
}
function musterKarte(m) {
  const info = S.muster.find(x => x.id === m.id), datei = info ? info.datei : m.id;
  const kopf = el("div", {class: "probe-kopf"}, el("h3", {}, el("span", {class: "mono"}, m.id), ` · ${datei}`),
    el("span", {class: m.ok ? "pill ok" : "pill err"}, m.ok ? "bestanden" : "Fehler"),
    knopf("Rahmen anzeigen", () => mitMeldung(async () => {
      S.modus = null;
      S.spur = {id: m.id, spur: m.spur};
      await waehleMuster(m.id);
      $("bild").scrollIntoView({block: "start"});
    }), {class: "btn btn-secondary btn-sm nur-gross"}));
  if (!m.ok) return el("section", {class: "card"}, kopf, el("div", {class: "alert err"}, m.fehler));
  const w = m.werte, zeilen = [["Nummer", w.nummer], ["Datum", w.datum], ["Fälligkeit", w.faellig || "–"], ["Käufer", w.kaeufer],
    ["Netto", euro(w.summe_netto)], ...Object.entries(w.steuern).map(([s, b]) => [`USt ${satz(s)}`, euro(b)]), ["Brutto", euro(w.summe_brutto)]];
  const id = `haken-${m.id}`;
  const haken = el("input", {type: "checkbox", id, checked: S.probe.haken.has(m.id), onchange: () => {
    if (haken.checked) S.probe.haken.add(m.id); else S.probe.haken.delete(m.id);
    renderKopf();
  }});
  const k = el("section", {class: "card"}, kopf,
    el("dl", {class: "werte"}, ...zeilen.flatMap(([n, x]) => [el("dt", {}, n), el("dd", {}, x)]),
      el("dt", {}, "Mustang"), el("dd", {class: "mono"}, m.mustang || "–")),
    el("h4", {}, `Positionen (${m.positionen.length})`),
    el("div", {class: "table-wrap"}, el("table", {},
      el("thead", {}, el("tr", {}, ...["Pos.", "Bezeichnung", "Menge", "Einheit", "Einzelpreis", "USt", "Netto"].map((t, i) =>
        el("th", {class: [2, 4, 5, 6].includes(i) ? "num" : null}, t)))),
      el("tbody", {}, ...m.positionen.map(p => el("tr", {},
        el("td", {class: "mono"}, p[0]), el("td", {}, p[1]), el("td", {class: "num"}, String(p[2]).replace(".", ",")), el("td", {}, p[3]),
        el("td", {class: "num"}, euro(p[4])), el("td", {class: "num"}, satz(p[5])), el("td", {class: "num"}, euro(p[6]))))))));
  if (m.ignoriert.length) {
    k.append(el("h4", {}, "Ignorierte Zeilen"), el("div", {class: "hint"}, "Übertrag/Zwischensumme – prüfen, ob keine Position darunter ist"),
      el("ul", {class: "ignoriert"}, ...m.ignoriert.map(z => el("li", {class: "mono"}, z))));
  }
  k.append(el("div", {class: "haken"}, haken, el("label", {for: id}, "Nummer, Datum und Käufer stimmen mit der Rechnung überein")));
  return k;
}
function renderKopf() {
  const p = S.probe, e = p && p.ergebnis, laeuft = !!(p && p.laeuft), wartet = S.uac !== null;
  const alle = e && e.muster.filter(m => m.ok).every(m => p.haken.has(m.id));
  $("probelauf").hidden = !!e;
  $("probelauf").disabled = laeuft || S.probeOffen || !S.name;
  $("probelauf").textContent = laeuft ? "Probelauf läuft …" : "Probelauf";
  $("probe-wiederholen").hidden = !e;
  $("probe-wiederholen").disabled = wartet || S.probeOffen;
  $("aktivieren").hidden = !e;
  $("aktivieren").disabled = !(e && e.bereit && alle) || wartet;
  $("aktivieren").textContent = wartet ? "Warte auf Freigabe …" : "Vorlage aktivieren";
}
function renderProbe() {
  renderKopf();
  const p = S.probe, box = $("probe-inhalt");
  $("probe").hidden = !S.name || !p;
  if (!p) return box.replaceChildren();
  if (p.laeuft) {
    $("probe-titel").textContent = "Probelauf";
    return box.replaceChildren(el("div", {class: "alert info"}, "Probelauf läuft. Texterkennung und Mustang-Prüfung dauern je Muster einige Sekunden, bei Bild-PDFs auch länger."));
  }
  const e = p.ergebnis;
  if (e.vorlage_fehler) {
    $("probe-titel").textContent = "Probelauf: Vorlage unvollständig";
    return box.replaceChildren(el("div", {class: "alert err"}, e.vorlage_fehler));
  }
  const ok = e.muster.filter(m => m.ok).length, n = e.muster.length;
  $("probe-titel").textContent = `Probelauf: ${ok} von ${n} ${n === 1 ? "Muster" : "Mustern"} bestanden` + (n < 2 ? " · mindestens 2 Muster nötig" : "");
  box.replaceChildren(
    e.bereit ? el("div", {class: "alert info"}, S.uac !== null ? UAC_WARTEN : uacHinweis("bleibt die Vorlage inaktiv")) : null,
    ...e.muster.map(musterKarte));
}
async function aktivieren() {
  const p = S.probe, name = S.name;
  S.uac = name;
  renderProbe();
  let r;
  try {
    r = await api("POST", `/api/entwurf/${encodeURIComponent(name)}/aktivieren`, {bestaetigt: [...p.haken]});
  } finally {
    S.uac = null;
    renderProbe();
  }
  if (!r.ok) return fehler(r.meldung);
  S.erfolg = "Vorlage aktiv. Rechnungen in diesem Layout werden ab sofort umgewandelt.";
  location.hash = "#vorlagen";
}

// ---------- Ansichten ----------
function zeigeAnsicht() {
  const h = location.hash || "#vorlagen", lern = h.startsWith("#anlernen");
  $("ansicht-vorlagen").hidden = lern;
  $("ansicht-anlernen").hidden = !lern;
  for (const [id, an] of [["nav-vorlagen", !lern], ["nav-anlernen", lern]]) {
    if (an) $(id).setAttribute("aria-current", "page"); else $(id).removeAttribute("aria-current");
  }
  const name = decodeURIComponent(h.slice("#anlernen/".length));
  if (lern && name && name !== S.name) mitMeldung(() => oeffneEntwurf(name));
  else if (lern) renderAnlernen();
  else mitMeldung(ladeStand).then(() => { if (S.erfolg) { meldung(S.erfolg, "ok"); S.erfolg = null; } });
}
async function neueVorlage() {
  const feld = $("neu-name"), name = feld.value.trim();
  if (!NAME.test(name)) { feld.setAttribute("aria-invalid", "true"); throw new Error("Name ungültig: 2–40 Zeichen a–z, 0–9, Bindestrich"); }
  feld.removeAttribute("aria-invalid");
  await api("POST", "/api/entwurf", {name});
  $("neu-dialog").hidden = true;
  $("neu-oeffnen").hidden = false;
  feld.value = "";
  S.stand = null;
  await oeffneEntwurf(name);
}
async function beenden() {
  await speichernJetzt();
  await api("POST", "/api/beenden", {});
  $("app").hidden = true;
  $("beendet").hidden = false;
}

// ---------- Ereignisse ----------
function verbinde() {
  const c = $("leinwand"), img = $("seitenbild");
  c.addEventListener("pointerdown", (ev) => {
    if (!S.modus) return;
    ev.preventDefault();            // kein Markieren/Ziehen des Bildes durch den Browser
    const p = relativ(ev, c);
    S.zug = {x0: p.x, y0: p.y, x1: p.x, y1: p.y};
    c.setPointerCapture(ev.pointerId);
  });
  c.addEventListener("pointermove", (ev) => {
    const p = relativ(ev, c);
    S.hover = wortBei(p);
    if (S.zug) { S.zug.x1 = p.x; S.zug.y1 = p.y; }
    zeichne();
  });
  c.addEventListener("pointerleave", () => { S.hover = null; zeichne(); });
  c.addEventListener("pointercancel", () => { S.zug = null; zeichne(); });
  c.addEventListener("pointerup", () => {
    const z = S.zug, m = S.modus;
    if (!z || !m) return;
    S.zug = null;
    const r = [r4(Math.min(z.x0, z.x1)), r4(Math.min(z.y0, z.y1)), r4(Math.max(z.x0, z.x1)), r4(Math.max(z.y0, z.y1))];
    const gezogen = r[2] - r[0] > 0.005 && r[3] - r[1] > 0.003, p = {x: z.x1, y: z.y1}, w = wortBei(p);
    meldungWeg();
    if (gezogen && (m.art === "feld" || m.art === "anker")) setzeFeld(m.name, r);
    else if (gezogen && m.art === "pos-tabelle") setzeTabelle(r);
    else if (!gezogen && m.art === "anker" && w) ankerKlick(m.name, w);
    else if (!gezogen && m.art === "pos-kopf" && w) setzeKopf(w);
    else if (!gezogen && m.art === "pos-spalten") schalteSpalte(p.x);
    else if (!gezogen && m.art === "pos-ende" && w) setzeEnde(w);
    else if (!gezogen && m.art === "pos-unten") setzeUnten(p.y);
    zeichne();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape" || !S.modus) return;
    S.modus = null;
    S.zug = null;
    renderFelder();
    renderModus();
    zeichne();
  });
  img.addEventListener("load", groesse);
  new ResizeObserver(groesse).observe(img);
  $("seite-zurueck").addEventListener("click", () => { S.seite -= 1; S.hover = null; renderSeite(); });
  $("seite-vor").addEventListener("click", () => { S.seite += 1; S.hover = null; renderSeite(); });
  $("muster-wahl").addEventListener("change", (ev) => mitMeldung(() => waehleMuster(ev.target.value)));
  $("muster-datei").addEventListener("change", (ev) => {
    const datei = ev.target.files[0];
    ev.target.value = "";
    if (datei) mitMeldung(() => musterHochladen(datei));
  });
  $("muster-fehler").addEventListener("change", (ev) => {
    const datei = ev.target.value;
    ev.target.value = "";
    if (datei) mitMeldung(() => musterAusFehler(datei));
  });
  $("erkennung").addEventListener("change", (ev) => {
    S.vorlage.schluesselwoerter = ev.target.value.split(",").map(t => t.trim()).filter(Boolean).slice(0, 5);
    speichern();
  });
  $("neu-oeffnen").addEventListener("click", () => { $("neu-dialog").hidden = false; $("neu-oeffnen").hidden = true; $("neu-name").focus(); });
  $("neu-abbrechen").addEventListener("click", () => { $("neu-dialog").hidden = true; $("neu-oeffnen").hidden = false; });
  $("neu-anlegen").addEventListener("click", () => mitMeldung(neueVorlage));
  $("neu-name").addEventListener("keydown", (ev) => { if (ev.key === "Enter") mitMeldung(neueVorlage); });
  $("beenden").addEventListener("click", () => mitMeldung(beenden));
  $("probelauf").addEventListener("click", () => mitMeldung(probelauf));
  $("probe-wiederholen").addEventListener("click", () => mitMeldung(probelauf));
  $("aktivieren").addEventListener("click", () => mitMeldung(aktivieren));
  window.addEventListener("hashchange", zeigeAnsicht);
  window.addEventListener("beforeunload", () => {   // keepalive: das PUT überlebt das Schließen des Fensters
    if (S.timer === null) return;
    clearTimeout(S.timer);
    S.timer = null;
    vorschlagErkennung();
    fetch(`/api/entwurf/${S.name}`, {method: "PUT", keepalive: true, headers: {"X-CSRF": CSRF, "Content-Type": "application/json"},
      body: JSON.stringify(S.vorlage)});
  });
}
verbinde();
zeigeAnsicht();
