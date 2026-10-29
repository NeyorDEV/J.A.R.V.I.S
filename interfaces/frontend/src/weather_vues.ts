/**
 * Vues du widget météo : aujourd'hui, demain, semaine, pluie, température. Les prévisions arrivent du backend
 * (`weather_forecast` toutes les 10 min, `weather_view` quand une question météo précise la vue : « la météo de demain »).
 * Les onglets permettent aussi de changer de vue au clic.
 */

import { esc } from "./panels/pm_utils";

interface Jour { date: string; jour: string; code: number; desc: string; tmax: number; tmin: number; pluie_pct: number | null; pluie_mm: number | null; vent: number | null }
interface Heure { h: number; t: number; pluie_pct: number | null }
export interface Previsions { city: string; jours: Jour[]; heures: Heure[]; actuel: { temp: number; ressenti: number; code: number; desc: string } }

const VUES: [id: string, titre: string][] = [["aujourdhui", "AUJOURD'HUI"], ["demain", "DEMAIN"], ["semaine", "SEMAINE"], ["pluie", "PLUIE"], ["temperature", "TEMPÉRATURE"]];
let previsions: Previsions | null = null;
let vueCourante = "aujourdhui";

const SVG = (corps: string): string => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${corps}"/></svg>`;
const SOLEIL = "M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4";
const NUAGE = "M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 1 1 0 9z";

/** Pictogramme au trait d'après le code météo WMO (Open-Meteo). */
export function iconeMeteo(code: number): string {
  if (code <= 1) return SVG(SOLEIL);
  if (code === 2) return SVG("M12 2v2M4.9 4.9l1.4 1.4M2 12h2M19.1 4.9l-1.4 1.4M16 12a4 4 0 0 0-7.4-2M17.5 20H10a5 5 0 1 1 4.8-6.4h2.7a3.2 3.2 0 1 1 0 6.4z");
  if (code === 3 || code === 45 || code === 48) return SVG(NUAGE);
  if (code >= 95) return SVG(`${NUAGE.replace("19H9", "15H9").replace("9z", "5z")}M13 15l-3 5h4l-3 4`);
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return SVG(`${NUAGE.replace("19H9", "15H9")}M8 18h.01M12 20h.01M16 18h.01M10 22h.01M14 22h.01`);
  return SVG(`${NUAGE.replace("19H9", "15H9")}M8 18l-1 3M12 18l-1 3M16 18l-1 3`);
}

const r = (n: number | null | undefined): number => Math.round(n ?? 0);

function carteJour(j: Jour, titre: string): string {
  return `<div class="wv-carte">
    <div class="wv-titre">${esc(titre)} · ${esc(j.jour)} ${esc(j.date.slice(8))}</div>
    <div class="wv-ligne"><span class="wv-icone">${iconeMeteo(j.code)}</span><span class="wv-desc">${esc(j.desc)}</span></div>
    <div class="wv-grand"><span>${r(j.tmax)}°</span><span class="wv-min">/ ${r(j.tmin)}°</span></div>
    <div class="wv-details">
      <div><span>Pluie</span><b>${r(j.pluie_pct)} % · ${(j.pluie_mm ?? 0).toFixed(1)} mm</b></div>
      <div><span>Vent</span><b>${r(j.vent)} km/h</b></div>
    </div></div>`;
}

function vueSemaine(p: Previsions): string {
  const mini = Math.min(...p.jours.map((j) => j.tmin)), maxi = Math.max(...p.jours.map((j) => j.tmax)), etendue = Math.max(1, maxi - mini);
  const lignes = p.jours.map((j) => {
    const g = ((j.tmin - mini) / etendue) * 100, l = Math.max(6, ((j.tmax - j.tmin) / etendue) * 100);
    return `<div class="wv-jour"><span class="wv-nom">${esc(j.jour)}</span><span class="wv-icone">${iconeMeteo(j.code)}</span>
      <span class="wv-t">${r(j.tmin)}°</span><span class="wv-plage"><i style="left:${g}%;width:${l}%"></i></span><span class="wv-t">${r(j.tmax)}°</span>
      <span class="wv-pluie">${r(j.pluie_pct)} %</span></div>`;
  }).join("");
  return `<div class="wv-carte"><div class="wv-titre">7 PROCHAINS JOURS</div>${lignes}</div>`;
}

function vuePluie(p: Previsions): string {
  const L = 288, H = 64, n = p.heures.length || 1, w = L / n;
  const barres = p.heures.map((h, i) => `<rect x="${(i * w + 1).toFixed(1)}" y="${(H - (h.pluie_pct ?? 0) * 0.6).toFixed(1)}" width="${(w - 2).toFixed(1)}" height="${((h.pluie_pct ?? 0) * 0.6).toFixed(1)}" />`).join("");
  const reperes = p.heures.map((h, i) => (i % 3 === 0 ? `<text x="${(i * w).toFixed(1)}" y="${H + 12}">${h.h}h</text>` : "")).join("");
  const [a, b] = [p.jours[0], p.jours[1]];
  return `<div class="wv-carte"><div class="wv-titre">RISQUE DE PLUIE · 24 H</div>
    <svg class="wv-graph" viewBox="0 0 ${L} ${H + 16}" role="img" aria-label="Risque de pluie heure par heure">${barres}${reperes}</svg>
    <div class="wv-details"><div><span>Aujourd'hui</span><b>${r(a?.pluie_pct)} % · ${(a?.pluie_mm ?? 0).toFixed(1)} mm</b></div>
    <div><span>Demain</span><b>${r(b?.pluie_pct)} % · ${(b?.pluie_mm ?? 0).toFixed(1)} mm</b></div></div></div>`;
}

function vueTemperature(p: Previsions): string {
  const L = 288, H = 56, ts = p.heures.map((h) => h.t), mini = Math.min(...ts), maxi = Math.max(...ts), etendue = Math.max(1, maxi - mini), n = Math.max(1, ts.length - 1);
  const pts = ts.map((t, i) => `${((i / n) * L).toFixed(1)},${(H - ((t - mini) / etendue) * H + 4).toFixed(1)}`).join(" ");
  const reperes = p.heures.map((h, i) => (i % 3 === 0 ? `<text x="${((i / n) * L).toFixed(1)}" y="${H + 20}">${h.h}h</text>` : "")).join("");
  return `<div class="wv-carte"><div class="wv-titre">TEMPÉRATURE · 24 H</div>
    <div class="wv-grand"><span>${r(p.actuel.temp)}°</span><span class="wv-min">ressenti ${r(p.actuel.ressenti)}°</span></div>
    <svg class="wv-graph wv-courbe" viewBox="0 0 ${L} ${H + 26}" role="img" aria-label="Température heure par heure"><polyline points="${pts}" />${reperes}</svg>
    <div class="wv-details"><div><span>Maximum</span><b>${r(p.jours[0].tmax)}°</b></div><div><span>Minimum</span><b>${r(p.jours[0].tmin)}°</b></div></div></div>`;
}

function dessinerVue(id: string): void {
  const zone = document.getElementById(`weather-vue-${id}`);
  if (!zone || id === "aujourdhui") return;
  if (!previsions) { zone.innerHTML = `<div class="wv-carte"><div class="wv-titre">PRÉVISIONS INDISPONIBLES</div></div>`; return; }
  if (id === "demain") zone.innerHTML = previsions.jours[1] ? carteJour(previsions.jours[1], "DEMAIN") : "";
  else if (id === "semaine") zone.innerHTML = vueSemaine(previsions);
  else if (id === "pluie") zone.innerHTML = vuePluie(previsions);
  else if (id === "temperature") zone.innerHTML = vueTemperature(previsions);
}

export function afficherVueMeteo(id: string): void {
  if (!VUES.some(([v]) => v === id)) id = "aujourdhui";
  vueCourante = id;
  dessinerVue(id);
  document.querySelectorAll(".weather-onglet").forEach((b) => b.classList.toggle("actif", (b as HTMLElement).dataset.vue === id));
  document.querySelectorAll(".weather-vue").forEach((z) => z.classList.toggle("actif", z.id === `weather-vue-${id}`));
}

export function majPrevisions(p: Previsions, vue?: string): void {
  previsions = p;
  afficherVueMeteo(vue ?? vueCourante);
}

/** Construit les onglets et les vues (une fois) ; renvoie la zone « aujourd'hui », qui reçoit les blocs météo du moment. */
export function construireVuesMeteo(container: HTMLElement): HTMLElement {
  const existante = document.getElementById("weather-vue-aujourdhui");
  if (existante) return existante;
  const onglets = document.createElement("div");
  onglets.className = "weather-onglets";
  onglets.innerHTML = VUES.map(([id, titre]) => `<button type="button" class="weather-onglet" data-vue="${id}">${titre}</button>`).join("");
  onglets.addEventListener("click", (e) => {
    const b = (e.target as HTMLElement).closest(".weather-onglet") as HTMLElement | null;
    if (b?.dataset.vue) afficherVueMeteo(b.dataset.vue);
  });
  const vues = document.createElement("div");
  vues.className = "weather-vues";
  vues.innerHTML = VUES.map(([id]) => `<div class="weather-vue" id="weather-vue-${id}"></div>`).join("");
  container.appendChild(onglets);
  container.appendChild(vues);
  afficherVueMeteo("aujourdhui");
  return document.getElementById("weather-vue-aujourdhui") as HTMLElement;
}
