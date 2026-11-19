// Pièces éclatées de la météo, de l'agenda et de la musique (voir eclate.ts), au style fin (css/17_fin.css, fin_graph.ts).
// Chacune lit les dernières données reçues (donnees_widgets.ts, prévisions de weather_vues.ts) ; rien n'est inventé :
// sans donnée, la pièce l'écrit. Quatre pièces par widget (deux de chaque côté), comme sur les maquettes validées.
import { locale, nomJour, nomMois } from "../i18n/i18n";
import { rafraichirPieces, type PieceDef } from "./eclate";
import type { ContenuCylindre } from "../orb_cylindre";
import { donnees, positionMusique } from "./donnees_widgets";
import { lirePrevisions } from "../weather_vues";
import { esc } from "../panels/pm_utils";
import { hideCalendarWidget, hideMusicWidget, hideWeatherHudWidget } from "../widgets";
import { AX, AX2, bornes, jauge, ticks } from "./fin_graph";

const mmss = (s: number): string => { const n = Math.max(0, Math.floor(s || 0)); return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`; };
const arrondi = (n: number | null | undefined): number => Math.round(n ?? 0);
const attente = (texte: string): string => `<div class="fn-txt" style="margin-top:40px;text-align:center">${texte}</div>`;
const actuelle = () => donnees.meteo.local ?? donnees.meteo.monistrol ?? null;
const fin = "ec-fin";

// ───────────────────────────────────────── MÉTÉO ─────────────────────────────────────────
function pointsHeures(): { pts: { x: number; y: number; h: number; t: number }[]; mini: number; maxi: number } | null {
  const p = lirePrevisions();
  if (!p || !p.heures.length) return null;
  const ts = p.heures.map((h) => h.t), mini = Math.floor(Math.min(...ts)), maxi = Math.ceil(Math.max(...ts)), e = Math.max(1, maxi - mini), n = Math.max(1, ts.length - 1);
  return { mini, maxi, pts: p.heures.map((h, i) => ({ x: (i / n) * 214, y: 62 - ((h.t - mini) / e) * 54, h: h.h, t: h.t })) };
}

function rendreTemperature(c: HTMLElement): void {
  const m = actuelle(), p = lirePrevisions(), k = pointsHeures();
  if (!m && !p) { c.innerHTML = attente("En attente des données météo…"); return; }
  const temp = m ? m.temp : p!.actuel.temp, ress = m ? m.apparent : p!.actuel.ressenti;
  const mx = m ? m.max : p?.jours[0]?.tmax ?? temp, mn = m ? m.min : p?.jours[0]?.tmin ?? temp;
  const desc = esc((m?.desc ?? p?.actuel.desc ?? "").slice(0, 26));
  const courbeSvg = k ? `<svg width="214" height="78" viewBox="0 0 214 78" style="display:block;background:rgba(2,12,50,.55);border:1px solid rgba(127,220,255,.25)"><g ${AX}><path d="M0 14H214M0 30H214M0 46H214M36 0V62M72 0V62M108 0V62M144 0V62M180 0V62"/></g><g ${AX2}><path d="M0 62H214"/></g>
      <text x="3" y="11" font-size="6.5" fill="#9fdcff">${k.maxi}°</text><text x="3" y="59" font-size="6.5" fill="#9fdcff">${k.mini}°</text>
      <path d="${k.pts.map((q, i) => `${i ? "L" : "M"}${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(" ")} L214,62 L0,62Z" fill="rgba(47,216,255,.12)"/><path d="${k.pts.map((q, i) => `${i ? "L" : "M"}${q.x.toFixed(1)},${q.y.toFixed(1)}`).join(" ")}" fill="none" stroke="#2fd8ff" stroke-width="1" style="filter:drop-shadow(0 0 2px #2fd8ff)"/>
      <line class="cur" x1="0" x2="0" y1="0" y2="62" stroke="#d8f8ff" stroke-opacity=".7" stroke-width=".6" stroke-dasharray="2 3"/><circle class="pt" r="2" fill="#fff"/>
      <g fill="#9fdcff" font-size="6.5"><text x="3" y="74">${k.pts[0].h} h</text><text x="108" y="74" text-anchor="middle">${k.pts[Math.floor(k.pts.length / 2)].h} h</text><text x="211" y="74" text-anchor="end">${k.pts[k.pts.length - 1].h} h</text></g></svg><div class="fn-txt cv" style="margin:3px 0 0;min-height:13px"></div>`
    : `<div class="fn-txt" style="margin:6px 0">Prévisions horaires indisponibles.</div>`;
  c.innerHTML = `<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">${jauge(70, bornes((temp + 10) / 50, 0.03, 1), "#2fd8ff", `${arrondi(temp)}°`, "dehors")}<div class="fn-txt"><b>${desc || "—"}</b><br>Ressenti <b>${arrondi(ress)}°</b><br>Max <b>${arrondi(mx)}°</b> · Min <b>${arrondi(mn)}°</b></div></div>
    <div class="fn-cap">Température, heure par heure</div>${courbeSvg}`;
}
function tickTemperature(c: HTMLElement, t: number): void {
  const k = pointsHeures();
  if (!k) return;
  const u = (t * 0.1) % 1, n = k.pts.length, i = Math.min(n - 2, Math.floor(u * (n - 1))), q = k.pts[i], r = k.pts[i + 1], f = u * (n - 1) - i;
  const x = q.x + (r.x - q.x) * f, y = q.y + (r.y - q.y) * f;
  const cur = c.querySelector(".cur"), pt = c.querySelector(".pt"), cv = c.querySelector(".cv");
  cur?.setAttribute("x1", String(x)); cur?.setAttribute("x2", String(x)); pt?.setAttribute("cx", String(x)); pt?.setAttribute("cy", String(y));
  if (cv) cv.textContent = `${f < 0.5 ? q.h : r.h} h : ${arrondi(q.t + (r.t - q.t) * f)}°`;
}

function rendreHumiditePluie(c: HTMLElement): void {
  const m = actuelle(), hs = lirePrevisions()?.heures ?? [];
  const hum = m ? bornes(m.humidity, 0, 100) : null, pic = Math.max(0, ...hs.map((h) => h.pluie_pct ?? 0));
  const barres = hs.map((h, i) => { const v = ((h.pluie_pct ?? 0) / 100) * 68, x = 23 + (i / Math.max(1, hs.length)) * 107; return `<rect x="${x.toFixed(1)}" y="${(74 - v).toFixed(1)}" width="${Math.max(1.5, 107 / hs.length - 1).toFixed(1)}" height="${v.toFixed(1)}" fill="#2fd8ff" fill-opacity=".8"/>`; }).join("");
  const reperes = hs.length ? [0, 6, 12, 18].map((q) => `<text x="${(22 + (q / 24) * 108).toFixed(0)}" y="88" font-size="6.5" fill="#9fdcff">${hs[Math.min(hs.length - 1, Math.round((q / 24) * hs.length))]?.h ?? ""} h</text>`).join("") : "";
  c.innerHTML = `<div style="display:flex;gap:10px"><div><div class="fn-cap" style="margin:0 0 3px">Humidité de l'air</div>
    <svg width="64" height="92" viewBox="0 0 64 92"><rect x="4" y="4" width="14" height="80" fill="rgba(2,12,50,.6)" stroke="rgba(127,220,255,.45)"/>${hum === null ? "" : `<rect x="5" y="${84 - hum * 0.8}" width="12" height="${hum * 0.8}" fill="#4dff9b" style="filter:drop-shadow(0 0 3px #4dff9b)"/>`}
    <g stroke="rgba(127,220,255,.7)"><path d="M18 4H23M18 44H23M18 84H23"/></g><g fill="#9fdcff" font-size="7"><text x="26" y="7">100 %</text><text x="26" y="47">50 %</text><text x="26" y="87">0 %</text></g><text x="46" y="26" text-anchor="middle" font-size="11" fill="#fff">${hum === null ? "—" : `${arrondi(hum)} %`}</text></svg></div>
    <div style="flex:1"><div class="fn-cap" style="margin:0 0 3px">Pluie, heure par heure${hs.length ? ` : pic <b>${arrondi(pic)} %</b>` : ""}</div>
    ${hs.length ? `<svg width="100%" viewBox="0 0 132 92" style="display:block"><g ${AX}><path d="M22 6H132M22 40H132"/></g><g ${AX2}><path d="M22 6V74H132"/></g><g fill="#9fdcff" font-size="7" text-anchor="end"><text x="19" y="9">100 %</text><text x="19" y="43">50 %</text><text x="19" y="77">0 %</text></g>${barres}${reperes}</svg>` : `<div class="fn-txt" style="margin-top:12px">Prévisions de pluie indisponibles.</div>`}</div></div>
    <div class="fn-sep fn-txt">${m ? `Vent : <b>${arrondi(m.wind)} km/h</b>` : "Vent : en attente"}</div>`;
}

function rendreEnsemble(c: HTMLElement): void {
  const m = actuelle(), p = lirePrevisions();
  if (!m && !p) { c.innerHTML = attente("En attente des données météo…"); return; }
  const temp = m ? m.temp : p!.actuel.temp, hs = p?.heures ?? [], pic = Math.max(0, ...hs.map((h) => h.pluie_pct ?? 0));
  const lignes: { n: string; f: number; c: string; v: string }[] = [
    { n: "Température", f: bornes((temp + 10) / 50, 0.02, 1), c: "#ffd23a", v: `${arrondi(temp)} °C` },
    ...(m ? [{ n: "Humidité", f: bornes(m.humidity / 100, 0.02, 1), c: "#4dff9b", v: `${arrondi(m.humidity)} %` }, { n: "Vent", f: bornes(m.wind / 60, 0.02, 1), c: "#2fd8ff", v: `${arrondi(m.wind)} km/h` }] : []),
    ...(hs.length ? [{ n: "Pluie maximale", f: bornes(pic / 100, 0.02, 1), c: "#b79bff", v: `${arrondi(pic)} %` }] : []),
  ];
  const arcs = lignes.map((l, i) => { const r = 38 - i * 8, C = 2 * Math.PI * r * 0.75; return `<circle cx="45" cy="45" r="${r}" fill="none" stroke="rgba(127,220,255,.14)" stroke-width="3.4" stroke-dasharray="${C} 999" transform="rotate(135 45 45)"/><circle cx="45" cy="45" r="${r}" fill="none" stroke="${l.c}" stroke-width="3.4" stroke-dasharray="${(C * l.f).toFixed(1)} 999" transform="rotate(135 45 45)" style="filter:drop-shadow(0 0 2px ${l.c})"/>`; }).join("");
  c.innerHTML = `<div style="display:flex;gap:10px;align-items:center"><svg width="92" height="92" viewBox="0 0 90 90">${ticks(45, 45, 42, 40)}${arcs}<line class="ne" x1="45" y1="45" x2="45" y2="10" stroke="#e8fbff" stroke-width=".8" style="transform-origin:45px 45px;filter:drop-shadow(0 0 2px #2fd8ff)"/><circle cx="45" cy="45" r="1.6" fill="#fff"/></svg>
    <div style="flex:1">${lignes.map((l) => `<div class="fn-lgd"><i style="background:${l.c};box-shadow:0 0 3px ${l.c}"></i><span>${l.n}</span><em>${l.v}</em></div>`).join("")}</div></div>
    <div class="fn-petit" style="margin:6px 0 8px">Chaque arc se remplit selon la valeur, de 0 à son maximum.</div>
    <div class="fn-sep fn-txt">${m ? `Ressenti <b>${arrondi(m.apparent)}°</b> · ${esc((m.desc ?? "").slice(0, 24))}` : esc(p!.actuel.desc ?? "")}</div>`;
}
function tickEnsemble(c: HTMLElement, t: number): void { const n = c.querySelector<SVGElement>(".ne"); if (n) n.style.transform = `rotate(${Math.sin(t * 0.7) * 100}deg)`; }

function rendreSemaine(c: HTMLElement): void {
  const js = lirePrevisions()?.jours ?? [];
  if (!js.length) { c.innerHTML = attente("Prévisions indisponibles."); return; }
  const mini = Math.floor(Math.min(...js.map((j) => j.tmin))), maxi = Math.ceil(Math.max(...js.map((j) => j.tmax))), e = Math.max(1, maxi - mini), W = 226, pas = W / js.length;
  let s = `<g ${AX}><path d="M0 14H${W}M0 52H${W}"/></g><g ${AX2}><path d="M0 90H${W}"/></g><text x="2" y="11" font-size="6.5" fill="#9fdcff">${maxi}°</text><text x="2" y="98" font-size="6.5" fill="#9fdcff">${mini}°</text>`;
  js.forEach((j, i) => {
    const x = i * pas + pas / 2, y0 = 90 - ((j.tmin - mini) / e) * 76, y1 = 90 - ((j.tmax - mini) / e) * 76;
    s += `<rect x="${x - 3}" y="${y1}" width="6" height="${Math.max(2, y0 - y1)}" fill="${i ? "#2fd8ff" : "#fff"}" fill-opacity="${i ? 0.7 : 0.95}" style="filter:drop-shadow(0 0 2px #2fd8ff)"/>
      <text x="${x}" y="${y1 - 4}" text-anchor="middle" font-size="7.5" fill="#fff">${arrondi(j.tmax)}°</text><text x="${x}" y="${y0 + 9}" text-anchor="middle" font-size="7" fill="#9fdcff">${arrondi(j.tmin)}°</text>
      <text x="${x}" y="112" text-anchor="middle" font-size="7.5" fill="${i ? "#9fdcff" : "#fff"}">${esc(j.jour.slice(0, 3).toUpperCase())}</text>`;
  });
  c.innerHTML = `<div class="fn-cap">Du plus bas au plus haut de chaque jour</div><svg width="226" height="120" viewBox="0 0 226 120" style="display:block">${s}</svg><div class="fn-petit" style="margin-top:2px">Barre blanche : aujourd'hui.</div>`;
}

export const piecesMeteo = (): PieceDef[] => [
  { id: "temp", cote: "g", rang: 0, w: 238, h: 246, classe: fin, titre: "TEMPÉRATURE · 24 HEURES", croix: hideWeatherHudWidget, rendre: rendreTemperature, tick: tickTemperature },
  { id: "pluie", cote: "g", rang: 1, w: 238, h: 190, classe: fin, titre: "HUMIDITÉ ET PLUIE", rendre: rendreHumiditePluie },
  { id: "ensemble", cote: "d", rang: 0, w: 248, h: 212, classe: fin, titre: "VUE D'ENSEMBLE", rendre: rendreEnsemble, tick: tickEnsemble },
  { id: "semaine", cote: "d", rang: 1, w: 248, h: 204, classe: fin, titre: "SEMAINE · MIN ET MAX", rendre: rendreSemaine },
];

// ───────────────────────────────────────── AGENDA ─────────────────────────────────────────
const iso = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const dateCourte = (j: string): string => { const d = new Date(`${j}T12:00:00`); return `${nomJour(d.getDay(), true)} ${d.getDate()} ${nomMois(d.getMonth(), true)}`; };
let jourChoisi: string | null = null;   // jour du calendrier sélectionné au clic (aujourd'hui par défaut)
const jourActif = (): string => jourChoisi ?? iso(new Date());
const evenementsDu = (j: string) => (donnees.agenda ?? []).filter((e) => e.jour === j);

function ecouterJours(c: HTMLElement): void {
  if (c.dataset.ecoute) return;
  c.dataset.ecoute = "1";
  c.addEventListener("click", (e) => {
    const b = (e.target as Element).closest("[data-jour]") as HTMLElement | null;
    if (b?.dataset.jour) { jourChoisi = b.dataset.jour; rafraichirPieces("widget-calendrier"); }
  });
}

function rendreMois(c: HTMLElement): void {
  const now = new Date(), prem = new Date(now.getFullYear(), now.getMonth(), 1), nb = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  const dec = (prem.getDay() + 6) % 7, auj = iso(now), choisi = jourActif();
  let g = ["L", "M", "M", "J", "V", "S", "D"].map((d) => `<span class="fn-petit" style="text-align:center">${d}</span>`).join("") + "<span></span>".repeat(dec);
  for (let d = 1; d <= nb; d++) {
    const j = iso(new Date(now.getFullYear(), now.getMonth(), d));
    g += `<div class="ec-jour ec-btn${j === auj ? " auj" : ""}${evenementsDu(j).length ? " ev" : ""}${j === choisi ? " sel" : ""}" data-jour="${j}" style="animation:none;opacity:1;font-size:9px">${d}</div>`;
  }
  c.innerHTML = `<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px">${g}</div><div class="fn-petit" style="margin-top:8px"><span style="color:#ffd23a">●</span> jour avec un rendez-vous · clique un jour</div>`;
  ecouterJours(c);
}

function rendreJourChoisi(c: HTMLElement): void {
  const j = jourActif(), auj = iso(new Date()), d = new Date(`${j}T12:00:00`), du = evenementsDu(j).length;
  const ecart = Math.round((d.getTime() - new Date(`${auj}T12:00:00`).getTime()) / 86400000);
  const rel = ecart === 0 ? "aujourd'hui" : ecart > 0 ? `dans ${ecart} jour${ecart > 1 ? "s" : ""}` : `il y a ${-ecart} jour${ecart < -1 ? "s" : ""}`;
  c.innerHTML = `<div style="display:flex;align-items:center;gap:10px"><div class="jr-anneau">${jauge(78, 0, "#2fd8ff", String(d.getDate()), nomMois(d.getMonth(), true))}</div><div class="fn-txt"><b>${dateCourte(j)}</b><br><span class="fn-petit">${rel}</span><br><span class="fn-petit">${du ? `${du} rendez-vous` : "journée libre"}</span></div></div>
    ${j === auj ? `<div class="fn-cap" style="margin-top:10px">L'anneau montre la part de la journée écoulée</div><div class="fn-sep fn-txt"><span class="hr" style="font:300 18px Consolas,monospace;color:#2fd8ff"></span></div>` : `<div class="fn-cap" style="margin-top:10px">Clique un autre jour du calendrier pour changer</div>`}`;
}
function tickJourChoisi(c: HTMLElement): void {
  if (jourActif() !== iso(new Date())) return;
  const n = new Date(), f = (n.getHours() * 3600 + n.getMinutes() * 60 + n.getSeconds()) / 86400;
  const cercle = c.querySelectorAll("circle")[1], hr = c.querySelector(".hr");
  if (cercle) { const r = 78 / 2 - 11, C = 2 * Math.PI * r; cercle.setAttribute("stroke-dasharray", `${(C * f).toFixed(1)} ${C.toFixed(1)}`); }
  if (hr) hr.textContent = n.toLocaleTimeString(locale());
}

function ligneRdv(x: { t: string; d?: string | null; jour?: string | null }, i: number): string {
  const couleur = ["#39ff88", "#ffd23a", "#2fd8ff"][i % 3];
  return `<div style="position:relative;padding:2px 0 6px 12px;border-left:1px solid rgba(127,220,255,.35);margin-left:3px"><i style="position:absolute;left:-3px;top:6px;width:5px;height:5px;border-radius:50%;background:${couleur};box-shadow:0 0 4px ${couleur}"></i><div style="font-size:10px;color:#eaf9ff">${esc(x.t)}</div><div class="fn-petit">${x.jour ? `${dateCourte(x.jour)}${x.d ? " · " : ""}` : ""}${esc(x.d ?? "")}</div></div>`;
}
function rendreRendezVous(c: HTMLElement): void {
  const l = donnees.agenda;
  if (!l) {
    c.innerHTML = `<div class="fn-txt" style="margin-top:12px;line-height:1.6">${esc(donnees.agendaMessage ?? "Aucun rendez-vous n'est chargé pour le moment.")}<br><span class="fn-petit">${donnees.agendaMessage ? "Connecte ton compte dans les paramètres." : "Demande : « Quels sont mes prochains rendez-vous ? »"}</span></div>`;
    return;
  }
  const j = jourActif(), du = evenementsDu(j), auj = iso(new Date()), suivants = l.filter((e) => (e.jour ?? "") > j);
  let h = `<div class="fn-cap" style="margin:0 0 5px;color:#eaf9ff;font-size:8.5px">${j === auj ? "AUJOURD'HUI" : dateCourte(j)}</div>`;
  h += du.length ? du.slice(0, 3).map(ligneRdv).join("") : `<div class="fn-txt" style="margin:2px 0 6px">Rien de prévu ce jour-là.</div>`;
  if (suivants.length) h += `<div class="fn-cap" style="margin:6px 0 4px">ENSUITE</div>${suivants.slice(0, du.length ? Math.max(1, 3 - du.length) : 3).map(ligneRdv).join("")}`;
  c.innerHTML = h;
}

function rendreSemaineMois(c: HTMLElement): void {
  const now = new Date(), lundi = new Date(now); lundi.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  const choisi = jourActif(), nb = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
  let sem = "";
  for (let i = 0; i < 7; i++) {
    const d = new Date(lundi); d.setDate(lundi.getDate() + i);
    const j = iso(d), n = evenementsDu(j).length;
    sem += `<div class="ec-jour ec-btn${d.toDateString() === now.toDateString() ? " auj" : ""}${n ? " ev" : ""}${j === choisi ? " sel" : ""}" data-jour="${j}" style="flex:1;padding:5px 0;animation:none;opacity:1"><div class="fn-petit">${"LMMJVSD"[i]}</div>${d.getDate()}</div>`;
  }
  const barres = Array.from({ length: nb }, (_, i) => { const j = iso(new Date(now.getFullYear(), now.getMonth(), i + 1)), n = evenementsDu(j).length; return `<rect x="${(2 + i * (210 / nb)).toFixed(1)}" y="${28 - Math.max(1, n * 13)}" width="2" height="${Math.max(1, n * 13)}" fill="${j === choisi ? "#fff" : n ? "#ffd23a" : "#2fd8ff"}" fill-opacity="${n || j === choisi ? 1 : 0.35}"/>`; }).join("");
  const total = (donnees.agenda ?? []).length;
  c.innerHTML = `<div class="fn-cap">Cette semaine</div><div style="display:flex;gap:3px">${sem}</div>
    <div class="fn-cap" style="margin:10px 0 3px">Rendez-vous par jour du mois</div><svg width="226" height="44" viewBox="0 0 214 44" preserveAspectRatio="none"><g ${AX2}><path d="M0 29H214"/></g>${barres}<g fill="#9fdcff" font-size="6.5"><text x="2" y="40">1</text><text x="62" y="40">10</text><text x="128" y="40">20</text><text x="196" y="40">${nb}</text></g></svg>
    <div class="fn-petit" style="margin-top:4px"><b style="color:#fff;font-weight:400">${donnees.agenda ? `${total} rendez-vous` : "Pas de données"}</b>${donnees.agenda ? " à venir" : ""}</div>`;
  ecouterJours(c);
}

export const piecesAgenda = (): PieceDef[] => {
  jourChoisi = null;
  return [
    { id: "mois", cote: "g", rang: 0, w: 238, h: 226, classe: fin, croix: hideCalendarWidget, titre: `${nomMois(new Date().getMonth())} ${new Date().getFullYear()}`, rendre: rendreMois },
    { id: "jour", cote: "g", rang: 1, w: 238, h: 190, classe: fin, titre: "JOUR CHOISI", rendre: rendreJourChoisi, tick: tickJourChoisi },
    { id: "rdv", cote: "d", rang: 0, w: 248, h: 204, classe: fin, titre: "RENDEZ-VOUS", rendre: rendreRendezVous },
    { id: "sem", cote: "d", rang: 1, w: 248, h: 190, classe: fin, titre: "SEMAINE ET MOIS", rendre: rendreSemaineMois },
  ];
};

// ───────────────────────────────────────── MUSIQUE ─────────────────────────────────────────
const envoyer = (detail: string | { action: string; value?: number }): void => { window.dispatchEvent(new CustomEvent("music-cmd", { detail })); };
const graine = (s: string): number => { let h = 7; for (const ch of s) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return h; };
const surClic = (c: HTMLElement, f: (e: MouseEvent) => void): void => { if (c.dataset.ecoute) return; c.dataset.ecoute = "1"; c.addEventListener("click", f); };

function rendreEnLecture(c: HTMLElement): void {
  const m = donnees.musique, f = m.dur ? positionMusique() / m.dur : 0;
  c.innerHTML = `<div style="display:flex;gap:10px"><div style="width:84px;height:84px;border:1px solid rgba(127,220,255,.6);background:linear-gradient(135deg,rgba(10,60,220,.7),rgba(0,229,255,.5) 70%,rgba(232,251,255,.7));position:relative;overflow:hidden;flex:none">${m.pochette ? `<img src="${esc(m.pochette)}" alt="" style="width:100%;height:100%;object-fit:cover;display:block">` : ""}<i style="position:absolute;left:0;right:0;height:16px;background:linear-gradient(180deg,rgba(255,255,255,0),rgba(255,255,255,.3),rgba(255,255,255,0));animation:ec-sc 2.6s linear infinite"></i></div>
    <div style="min-width:0"><div class="fn-cap" style="margin:0">${m.hors ? "DEEZER · FERMÉ" : m.joue ? "EN LECTURE" : "EN PAUSE"}</div><div style="font-size:12px;color:#fff;margin:4px 0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.hors ? "Deezer est fermé" : m.titre)}</div><div class="fn-txt" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(m.hors ? "Dis « lance Deezer »" : m.artiste)}</div></div></div>
    <div class="fn-cap" style="margin-top:12px">Position dans le morceau</div><div class="bp" style="height:2px;background:rgba(127,220,255,.18);position:relative;margin:7px 0 3px;cursor:pointer"><i class="pr" style="position:absolute;left:0;top:0;bottom:0;width:${(f * 100).toFixed(1)}%;background:#2fd8ff;box-shadow:0 0 4px #2fd8ff"></i></div>
    <div style="display:flex;justify-content:space-between;font-size:8px;color:#9fdcff"><span class="tp">${mmss(positionMusique())}</span><span>${m.dur ? mmss(m.dur) : "—"}</span></div>`;
  surClic(c, (e) => { const b = (e.target as HTMLElement).closest(".bp") as HTMLElement | null; if (b && donnees.musique.dur) { const r = b.getBoundingClientRect(); envoyer({ action: "seek", value: bornes((e.clientX - r.left) / r.width, 0, 1) }); } });
}
function tickEnLecture(c: HTMLElement): void {
  const m = donnees.musique, f = m.dur ? positionMusique() / m.dur : 0, pr = c.querySelector<HTMLElement>(".pr"), tp = c.querySelector(".tp");
  if (pr) pr.style.width = `${(f * 100).toFixed(1)}%`;
  if (tp) tp.textContent = mmss(positionMusique());
}

function rendreSpectre(c: HTMLElement): void {
  c.innerHTML = `<div class="fn-cap">Niveau de chaque fréquence, animé pendant la lecture</div><div style="display:flex;gap:1.4px;align-items:flex-end;height:78px">${"<i class='sp' style='flex:1;background:#2fd8ff;height:6%;opacity:.8'></i>".repeat(46)}</div><div style="display:flex;justify-content:space-between;font-size:7px;color:#9fdcff;margin-top:3px"><span>graves</span><span>médiums</span><span>aigus</span></div>`;
}
function tickSpectre(c: HTMLElement, t: number): void {
  const j = donnees.musique.joue;
  c.querySelectorAll<HTMLElement>(".sp").forEach((b, i) => { b.style.height = `${j ? 8 + 88 * Math.abs(Math.sin(t * 3 + i * 0.5) * Math.sin(t * 1.3 + i * 0.21)) * (1 - i / 80) : 5}%`; });
}

function rendreForme(c: HTMLElement): void {
  const m = donnees.musique, N = 60, g = graine(m.titre || "x") % 11;
  let wf = "";
  for (let i = 0; i < N; i++) { const v = 0.25 + 0.75 * Math.abs(Math.sin(i * 0.37 + g) * Math.sin(i * 0.113 + g / 2)); wf += `<rect class="wb" data-i="${i}" x="${(i * 3.55 + 1).toFixed(1)}" y="${(24 - v * 22).toFixed(1)}" width="1.6" height="${(v * 44).toFixed(1)}" fill="rgba(127,220,255,.35)"/>`; }
  const ic = (act: string, d: string, w: number, fort = false): string => `<svg class="ec-btn" data-act="${act}" width="${w}" height="${w}" viewBox="0 0 ${w} ${w}"><rect x=".5" y=".5" width="${w - 1}" height="${w - 1}" fill="${fort ? "rgba(0,229,255,.1)" : "none"}" stroke="#2fd8ff" stroke-opacity="${fort ? 0.9 : 0.5}" stroke-width=".8"/>${d}</svg>`;
  c.innerHTML = `<div class="fn-cap">Clique pour avancer ou reculer dans le morceau</div><svg class="wf" width="226" height="48" viewBox="0 0 214 48" preserveAspectRatio="none" style="display:block;cursor:pointer;background:rgba(2,12,50,.45);border:1px solid rgba(127,220,255,.2)">${wf}</svg>
    <div style="display:flex;justify-content:center;gap:16px;align-items:center;margin-top:12px">${ic("prev", '<path d="M8 7V19M18 7L10 13L18 19Z" stroke="#bff3ff" stroke-width=".8" fill="#bff3ff"/>', 26)}${ic("toggle", m.joue ? '<path d="M12 9V25M20 9V25" stroke="#fff" stroke-width="2"/>' : '<path d="M12 8L25 17L12 26Z" fill="#fff"/>', 34, true)}${ic("next", '<path d="M18 7V19M8 7L16 13L8 19Z" stroke="#bff3ff" stroke-width=".8" fill="#bff3ff"/>', 26)}</div>
    <div class="fn-petit" style="text-align:center;margin-top:8px">Précédent · lecture ou pause · suivant</div>`;
  surClic(c, (e) => {
    const b = (e.target as HTMLElement).closest("[data-act]") as HTMLElement | null;
    if (b?.dataset.act) { envoyer(b.dataset.act); return; }
    const wf = (e.target as HTMLElement).closest(".wf") as SVGElement | null;
    if (wf && donnees.musique.dur) { const r = wf.getBoundingClientRect(); envoyer({ action: "seek", value: bornes((e.clientX - r.left) / r.width, 0, 1) }); }
  });
}
function tickForme(c: HTMLElement): void {
  const m = donnees.musique, f = m.dur ? positionMusique() / m.dur : 0;
  c.querySelectorAll<SVGElement>(".wb").forEach((b) => b.setAttribute("fill", Number(b.dataset.i) / 60 < f ? "#2fd8ff" : "rgba(127,220,255,.35)"));
}

function rendreVolume(c: HTMLElement): void {
  const v = donnees.musique.volume, m = donnees.musique, f = m.dur ? Math.round((positionMusique() / m.dur) * 100) : 0;
  c.innerHTML = `<div class="fn-cap">Volume de Deezer : <b>${v === null ? "inconnu" : `${v} %`}</b></div><div class="vb" style="height:14px;position:relative;cursor:pointer"><svg width="226" height="14" viewBox="0 0 214 14" preserveAspectRatio="none" style="position:absolute;left:0;top:0"><path d="M0 7H214" stroke="rgba(127,220,255,.2)" stroke-width="1.5"/><path d="M0 7H${(v ?? 0) * 2.14}" stroke="#2fd8ff" stroke-width="1.5" style="filter:drop-shadow(0 0 2px #2fd8ff)"/><g stroke="rgba(127,220,255,.5)" stroke-width=".6">${Array.from({ length: 11 }, (_, i) => `<path d="M${i * 21.4} ${i % 5 ? 9 : 11}V14M${i * 21.4} 0V${i % 5 ? 3 : 5}"/>`).join("")}</g></svg></div>
    <div style="display:flex;justify-content:space-between;font-size:6.5px;color:#9fdcff;margin:1px 0 10px"><span>0</span><span>50</span><span>100</span></div>
    <div class="fn-sep fn-lgd"><i style="background:${m.hors ? "#7a86b8" : "#4dff9b"}"></i><span>Source : Deezer</span><em>${m.hors ? "fermé" : m.joue ? `${f} % lu` : "en pause"}</em></div>`;
  surClic(c, (e) => { const b = (e.target as HTMLElement).closest(".vb") as HTMLElement | null; if (b) { const r = b.getBoundingClientRect(); envoyer({ action: "volume", value: Math.round(bornes((e.clientX - r.left) / r.width, 0, 1) * 100) }); } });
}

export const piecesMusique = (): PieceDef[] => [
  { id: "lecture", cote: "g", rang: 0, w: 238, h: 190, classe: fin, croix: hideMusicWidget, titre: "EN LECTURE", rendre: rendreEnLecture, tick: tickEnLecture },
  { id: "spectre", cote: "g", rang: 1, w: 238, h: 156, classe: fin, titre: "SPECTRE SONORE", rendre: rendreSpectre, tick: tickSpectre },
  { id: "forme", cote: "d", rang: 0, w: 248, h: 160, classe: fin, titre: "FORME DU MORCEAU", rendre: rendreForme, tick: tickForme },
  { id: "volume", cote: "d", rang: 1, w: 248, h: 120, classe: fin, titre: "VOLUME ET SOURCE", rendre: rendreVolume },
];

// ───────────────────────────────────────── CONTENU AU MILIEU DU CYLINDRE ─────────────────────────────────────────
// Le cylindre n'est pas vide quand des pièces l'entourent : il porte le titre, une grande valeur et un sous-titre (rappelés à chaque image).
export const centreMeteo = (): ContenuCylindre => {
  const m = actuelle(), p = lirePrevisions();
  if (!m && !p) return { titre: "MÉTÉO", valeur: "…", sous: "EN ATTENTE DES DONNÉES" };
  return { titre: "MÉTÉO", valeur: `${arrondi(m ? m.temp : p!.actuel.temp)}°`, sous: (m?.desc ?? p?.actuel.desc ?? "").toUpperCase() };
};
export const centreAgenda = (): ContenuCylindre => {
  const j = jourActif(), d = new Date(`${j}T12:00:00`), premier = evenementsDu(j)[0]?.t ?? donnees.agenda?.find((e) => (e.jour ?? "") > j)?.t;
  return { titre: "AGENDA", valeur: `${d.getDate()} ${nomMois(d.getMonth(), true)}`, sous: (premier ?? nomJour(d.getDay(), true).replace(".", "")).toUpperCase() };
};
export const centreMusique = (): ContenuCylindre => {
  const m = donnees.musique;
  return { titre: "MUSIQUE", valeur: m.hors ? "—" : mmss(positionMusique()), sous: m.hors ? "DEEZER FERMÉ" : m.titre.toUpperCase() };
};
