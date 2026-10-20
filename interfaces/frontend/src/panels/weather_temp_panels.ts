// ── Panneaux météo et température (HUD) ──
import { icone } from "./pm_utils";

// ── Temp Panel (left side — Home Assistant interior) ────────────────────────

const TEMP_DURATION_MS = 3 * 60 * 1000; // 3 minutes

// Comfort scale: 10°C → 30°C maps to 0% → 100%
function tempToPercent(t: number): number {
  return Math.min(100, Math.max(0, ((t - 10) / 20) * 100));
}

let _tpTimer: ReturnType<typeof setInterval> | null = null;
let _tpHideTimer: ReturnType<typeof setTimeout> | null = null;
let _tpEndTime = 0;

export function showTempPanel(d: {
  piece: string; temperature: string; humidite?: string | null;
}) {
  const panel = document.getElementById("temp-panel");
  if (!panel) return;

  const temp = parseFloat(d.temperature) || 0;

  (document.getElementById("tp-piece") as HTMLElement).textContent = d.piece.toUpperCase();
  (document.getElementById("tp-temp") as HTMLElement).textContent = String(Math.round(temp));

  const humRow = document.getElementById("tp-hum-row") as HTMLElement;
  if (d.humidite) {
    (document.getElementById("tp-hum") as HTMLElement).textContent = d.humidite;
    humRow.style.display = "flex";
  } else {
    humRow.style.display = "none";
  }

  const pct = tempToPercent(temp);
  const marker = document.getElementById("tp-marker") as HTMLElement;
  marker.style.left = `${pct}%`;
    if (_tpTimer) clearInterval(_tpTimer);
  if (_tpHideTimer) clearTimeout(_tpHideTimer);

  panel.classList.add("tp-visible");
  _tpEndTime = Date.now() + TEMP_DURATION_MS;

  // #tp-progress et #tp-timer n'existent pas (ou plus) dans index.html : le cast
  // « as HTMLElement » masquait le null et l'intervalle levait un TypeError à
  // CHAQUE seconde dès qu'on demandait une température. On les rend optionnels.
  const progress = document.getElementById("tp-progress");
  const timerEl  = document.getElementById("tp-timer");

  _tpTimer = setInterval(() => {
    const remaining = Math.max(0, _tpEndTime - Date.now());
    const fraction  = remaining / TEMP_DURATION_MS;
    if (progress) progress.style.transform = `scaleX(${fraction})`;
    const secs = Math.ceil(remaining / 1000);
    if (timerEl) timerEl.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
    if (remaining <= 0) hideTempPanel();
  }, 1000);

  _tpHideTimer = setTimeout(hideTempPanel, TEMP_DURATION_MS);
}

function hideTempPanel() {
  const panel = document.getElementById("temp-panel");
  if (!panel) return;
  panel.classList.remove("tp-visible");
  if (_tpTimer) { clearInterval(_tpTimer); _tpTimer = null; }
  if (_tpHideTimer) { clearTimeout(_tpHideTimer); _tpHideTimer = null; }
}


// ── Weather Panel ────────────────────────────────────────────────────────────

const WEATHER_DURATION_MS = 2 * 60 * 1000; // 2 minutes
const WEATHER_ICONS: Record<number, string> = {
  0: "soleil", 1: "soleil_nuage", 2: "soleil_nuage", 3: "nuage",
  45: "brouillard", 48: "brouillard",
  51: "pluie", 53: "pluie", 55: "pluie",
  61: "pluie", 63: "pluie", 65: "pluie",
  71: "neige", 73: "neige", 75: "neige", 77: "neige",
  80: "pluie", 81: "pluie", 82: "orage",
  85: "neige", 86: "neige",
  95: "orage", 96: "orage", 99: "orage",
};

let _wpTimer: ReturnType<typeof setInterval> | null = null;
let _wpHideTimer: ReturnType<typeof setTimeout> | null = null;
let _wpEndTime = 0;

export function showWeatherPanel(d: {
  ville: string; temperature: number; ressenti: number;
  humidite: number; vent: number; code: number; description: string;
}) {
  const panel = document.getElementById("weather-panel");
  if (!panel) return;

  (document.getElementById("wp-city") as HTMLElement).textContent = d.ville.toUpperCase();
  (document.getElementById("wp-temp") as HTMLElement).textContent = String(d.temperature);
  (document.getElementById("wp-desc") as HTMLElement).textContent = d.description.toUpperCase();
  (document.getElementById("wp-feels") as HTMLElement).textContent = String(d.ressenti);
  (document.getElementById("wp-humidity") as HTMLElement).textContent = String(d.humidite);
  (document.getElementById("wp-wind") as HTMLElement).textContent = String(d.vent);
  (document.getElementById("wp-icon") as HTMLElement).innerHTML = icone(WEATHER_ICONS[d.code] ?? "inconnu");

  // reset any existing timers
  if (_wpTimer) clearInterval(_wpTimer);
  if (_wpHideTimer) clearTimeout(_wpHideTimer);

  panel.classList.add("wp-visible");
  _wpEndTime = Date.now() + WEATHER_DURATION_MS;
  // Mêmes éléments absents du HTML que pour le panneau température (voir plus haut) :
  // sans ces gardes, demander la météo provoquait un TypeError chaque seconde.
  const progress = document.getElementById("wp-progress");
  const timerEl  = document.getElementById("wp-timer");

  _wpTimer = setInterval(() => {
    const remaining = Math.max(0, _wpEndTime - Date.now());
    const fraction  = remaining / WEATHER_DURATION_MS;
    if (progress) progress.style.transform = `scaleX(${fraction})`;
    const secs = Math.ceil(remaining / 1000);
    if (timerEl) timerEl.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
    if (remaining <= 0) hideWeatherPanel();
  }, 1000);

  _wpHideTimer = setTimeout(hideWeatherPanel, WEATHER_DURATION_MS);
}

function hideWeatherPanel() {
  const panel = document.getElementById("weather-panel");
  if (!panel) return;
  panel.classList.remove("wp-visible");
  if (_wpTimer) { clearInterval(_wpTimer); _wpTimer = null; }
  if (_wpHideTimer) { clearTimeout(_wpHideTimer); _wpHideTimer = null; }
}


export function initWeatherTempPanels(): void {
  document.getElementById("tp-close-btn")?.addEventListener("click", hideTempPanel);
  document.getElementById("wp-close-btn")?.addEventListener("click", hideWeatherPanel);
}
