/**
 * J.A.R.V.I.S — Widgets Logic (Calendar & Weather)
 */

import { construireVuesMeteo } from "./weather_vues";

export function initWidgets(ws: WebSocket | null) {
  // 1. Calendar is self-sufficient
  updateCalendar();
  setInterval(updateCalendar, 1000 * 60 * 60);

  // 2. Initial state for Music
  updateMusicUI({ status: "Stopped" });

  // 3. Weather-hud header (close button), data filled by backend via weather_update
  initWeatherHudHeader();

  // Start logic
  initWeather(ws);
  initMusic(ws);
}

// ── Widget show/hide helpers ─────────────────────────────────────────────────
export function showCalendarWidget() {
  const el = document.getElementById("calendar-hud");
  if (el) el.classList.add("hud-revealed");
}

export function hideCalendarWidget() {
  const el = document.getElementById("calendar-hud");
  if (el) el.classList.remove("hud-revealed");
}

export function showWeatherHudWidget() {
  const el = document.getElementById("weather-hud");
  if (el) el.classList.add("hud-revealed");
}

export function hideWeatherHudWidget() {
  const el = document.getElementById("weather-hud");
  if (el) el.classList.remove("hud-revealed");
}

export function showMusicWidget() {
  const el = document.getElementById("music-hud");
  if (el) el.classList.add("hud-revealed");
}

export function hideMusicWidget() {
  const el = document.getElementById("music-hud");
  if (el) el.classList.remove("hud-revealed");
}

// ── MUSIC ─────────────────────────────────────────────────────────────────────
// Widget « en lecture » : pochette, titre, progression qui avance en continu entre deux mises à jour du backend (toutes les
// 2 s), précédent / lecture / suivant et volume. Le DOM est construit une seule fois et mis à jour en place : le reconstruire à
// chaque message détruisait les écouteurs et interrompait le glissement du volume.
interface MusiqueData {
  status?: string; title?: string; artist?: string; cover?: string | null;
  position_s?: number; duration_s?: number; position?: string; duration?: string; percent?: number;
  volume?: number | null; muet?: boolean;
}

const ICONE_LECTURE = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
const ICONE_PAUSE = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
const musique = { pos: 0, dur: 0, t0: 0, joue: false, glisse: false, scrub: false, pochette: "", iconeJoue: null as boolean | null };

const mmss = (s: number): string => { const n = Math.max(0, Math.floor(s || 0)); return `${String(Math.floor(n / 60)).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}`; };
const enSecondes = (v: string | undefined): number => { const m = /^(\d+):(\d{2})$/.exec(v || ""); return m ? Number(m[1]) * 60 + Number(m[2]) : 0; };
const envoyerMusique = (detail: string | { action: string; value?: number }): void => { window.dispatchEvent(new CustomEvent("music-cmd", { detail })); };

function construireMusique(container: HTMLElement): void {
  container.innerHTML = `
    <div class="music-content">
      <div class="music-header">
        <div class="music-source"><div class="music-source-icon"></div><span>DEEZER</span></div>
        <button class="widget-close-btn" id="music-close-btn" title="Masquer">✕</button>
      </div>
      <div class="music-corps">
        <div class="music-pochette"><img id="music-cover" alt="" hidden></div>
        <div class="music-info">
          <div class="music-title" id="music-title">DEEZER</div>
          <div class="music-artist" id="music-artist"></div>
        </div>
      </div>
      <div class="music-progress">
        <span id="music-pos">00:00</span>
        <div class="music-bar" id="music-bar"><div class="music-bar-fill" id="music-fill"></div></div>
        <span id="music-dur">00:00</span>
      </div>
      <div class="music-controls">
        <button class="music-btn" id="music-prev" title="Morceau précédent"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6L18 18V6z"/></svg></button>
        <button class="music-btn play-pause" id="music-toggle" title="Lecture / pause">${ICONE_LECTURE}</button>
        <button class="music-btn" id="music-next" title="Morceau suivant"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6zm9-12v12h2V6z"/></svg></button>
      </div>
      <div class="music-volume">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H3v6h3l5 4zM15.5 8.5a5 5 0 0 1 0 7M18.5 6a9 9 0 0 1 0 12"/></svg>
        <input type="range" id="music-vol" min="0" max="100" step="1" value="50" aria-label="Volume de Deezer">
        <span class="music-volume-val" id="music-vol-val">50</span>
      </div>
    </div>`;

  container.querySelector("#music-prev")?.addEventListener("click", () => envoyerMusique("prev"));
  container.querySelector("#music-next")?.addEventListener("click", () => envoyerMusique("next"));
  container.querySelector("#music-toggle")?.addEventListener("click", () => envoyerMusique("toggle"));
  container.querySelector("#music-close-btn")?.addEventListener("click", () => hideMusicWidget());
  // Barre de progression : se saisit et se fait glisser pour avancer ou reculer dans le morceau. Elle doit empêcher le
  // déplacement du widget lui-même (le widget se déplace à la souris : sans cela, saisir la barre le déplaçait).
  const barre = container.querySelector("#music-bar") as HTMLElement | null;
  if (barre) {
    const fraction = (e: PointerEvent): number => { const r = barre.getBoundingClientRect(); return r.width > 0 ? Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) : 0; };
    const apercu = (f: number): void => {
      const fill = document.getElementById("music-fill"), pos = document.getElementById("music-pos");
      if (fill) fill.style.width = `${f * 100}%`;
      if (pos) pos.textContent = mmss(f * musique.dur);
    };
    barre.addEventListener("mousedown", (e) => e.stopPropagation());
    barre.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || !musique.dur) return;
      e.stopPropagation();
      barre.setPointerCapture(e.pointerId);
      musique.scrub = true;
      apercu(fraction(e));
    });
    barre.addEventListener("pointermove", (e) => { if (musique.scrub) apercu(fraction(e)); });
    barre.addEventListener("pointerup", (e) => {
      if (!musique.scrub) return;
      musique.scrub = false;
      const f = fraction(e);
      musique.pos = f * musique.dur; musique.t0 = performance.now();   // l'affichage reste là où on a lâché en attendant la mise à jour du backend
      envoyerMusique({ action: "seek", value: f });
    });
    barre.addEventListener("pointercancel", () => { musique.scrub = false; });
  }
  const vol = container.querySelector("#music-vol") as HTMLInputElement | null;
  const volVal = container.querySelector("#music-vol-val") as HTMLElement | null;
  let attente: number | null = null;
  vol?.addEventListener("input", () => {
    musique.glisse = true;
    if (volVal) volVal.textContent = vol.value;
    if (attente !== null) clearTimeout(attente);
    attente = window.setTimeout(() => { envoyerMusique({ action: "volume", value: Number(vol.value) }); musique.glisse = false; }, 140);
  });
  window.setInterval(avancerProgression, 250);
}

function avancerProgression(): void {
  const fill = document.getElementById("music-fill"), pos = document.getElementById("music-pos");
  if (!fill || !pos || !musique.dur || musique.scrub) return;
  const p = Math.min(musique.dur, musique.pos + (musique.joue ? (performance.now() - musique.t0) / 1000 : 0));
  fill.style.width = `${(p / musique.dur) * 100}%`;
  pos.textContent = mmss(p);
}

export function updateMusicUI(data: MusiqueData) {
  const container = document.getElementById("music-hud");
  if (!container || !data) return;
  if (!document.getElementById("music-title")) construireMusique(container);

  const horsLigne = data.status === "Stopped";
  container.classList.toggle("hors-ligne", horsLigne);
  const titre = document.getElementById("music-title"), artiste = document.getElementById("music-artist");
  if (titre) titre.textContent = horsLigne ? "DEEZER EST FERMÉ" : (data.title || "DEEZER");
  if (artiste) artiste.textContent = horsLigne ? "Dites « lance Deezer »" : (data.artist || "");

  const img = document.getElementById("music-cover") as HTMLImageElement | null;
  const cover = horsLigne ? "" : (data.cover || "");
  if (img && cover !== musique.pochette) {
    musique.pochette = cover;
    if (cover) { img.src = cover; img.hidden = false; } else { img.hidden = true; img.removeAttribute("src"); }
  }

  const joue = data.status === "Playing";
  if (musique.iconeJoue !== joue) {
    musique.iconeJoue = joue;
    const bouton = document.getElementById("music-toggle");
    if (bouton) bouton.innerHTML = joue ? ICONE_PAUSE : ICONE_LECTURE;
  }

  musique.joue = joue;
  musique.dur = horsLigne ? 0 : (data.duration_s ?? enSecondes(data.duration));
  if (!musique.scrub) { musique.pos = data.position_s ?? enSecondes(data.position); musique.t0 = performance.now(); }
  const dur = document.getElementById("music-dur");
  if (dur) dur.textContent = mmss(musique.dur);
  if (!musique.dur) {
    const fill = document.getElementById("music-fill"), pos = document.getElementById("music-pos");
    if (fill) fill.style.width = "0%";
    if (pos) pos.textContent = "00:00";
  } else avancerProgression();

  const vol = document.getElementById("music-vol") as HTMLInputElement | null;
  if (vol && !musique.glisse && typeof data.volume === "number") {
    vol.value = String(data.volume);
    const v = document.getElementById("music-vol-val"); if (v) v.textContent = String(data.volume);
  }
}

function initMusic(ws: WebSocket | null) {
  updateMusicUI({ status: "Stopped" });

  window.addEventListener("music-cmd", (e: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const detail = e.detail;
      ws.send(JSON.stringify({ type: "music_control", ...(typeof detail === "string" ? { action: detail } : detail) }));
    }
  });
}

// ── CALENDAR ──────────────────────────────────────────────────────────────────
function updateCalendar() {
  const container = document.getElementById("calendar-hud");
  if (!container) return;

  const now = new Date();
  const month = now.toLocaleString('fr-FR', { month: 'long' });
  const year = now.getFullYear();

  let html = `<div class="cal-header"><span class="cal-header-title">${month} ${year}</span><button class="widget-close-btn" id="cal-close-btn" title="Masquer">✕</button></div>`;
  html += `<div class="cal-grid">`;

  // Days of week
  const days = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
  days.forEach(d => html += `<div class="cal-day-name">${d}</div>`);

  // Calculate days
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  
  // Starting day (0=Sun, 1=Mon...) -> map to Mon-Sun
  let startDay = firstDay.getDay(); 
  if (startDay === 0) startDay = 7; // Sunday is 7
  startDay--; // Adjust to 0-indexed (Mon=0)

  // Empty slots for prev month
  for (let i = 0; i < startDay; i++) {
    html += `<div class="cal-day other-month"></div>`;
  }

  // Days of current month
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const isToday = d === now.getDate();
    html += `<div class="cal-day ${isToday ? 'today' : ''}">${d}</div>`;
  }

  html += `</div>`;
  container.innerHTML = html;

  document.getElementById("cal-close-btn")?.addEventListener('click', () => {
    hideCalendarWidget();
  });
}

// ── WEATHER ───────────────────────────────────────────────────────────────────
interface WeatherData {
  city: string;
  temp: number;
  desc: string;
  apparent: number;
  humidity: number;
  wind: number;
  max: number;
  min: number;
}

export function updateWeatherUI(data: WeatherData, type: 'local' | 'monistrol') {
  const container = document.getElementById("weather-hud");
  if (!container) return;

  let block = document.getElementById(`weather-${type}`);
  if (!block) {
    block = document.createElement("div");
    block.id = `weather-${type}`;
    block.className = "weather-block";
    (document.getElementById("weather-vue-aujourdhui") ?? container).appendChild(block);
  }

  block.innerHTML = `
    <div class="weather-city">${data.city}</div>
    <div class="weather-main">
      <div class="weather-desc">${data.desc}</div>
      <div class="weather-temp">${Math.round(data.temp)}°</div>
    </div>
    <div class="weather-details">
      <div class="weather-detail-item">
        <span class="weather-detail-label">Ressenti</span>
        <span class="weather-detail-val">${Math.round(data.apparent)}°</span>
      </div>
      <div class="weather-detail-item">
        <span class="weather-detail-label">Humidité</span>
        <span class="weather-detail-val">${data.humidity}%</span>
      </div>
      <div class="weather-detail-item">
        <span class="weather-detail-label">Vent</span>
        <span class="weather-detail-val">${data.wind} km/h</span>
      </div>
      <div class="weather-detail-item">
        <span class="weather-detail-label">Max / Min</span>
        <span class="weather-detail-val">${Math.round(data.max)}° / ${Math.round(data.min)}°</span>
      </div>
    </div>
  `;
}

function initWeatherHudHeader() {
  const container = document.getElementById("weather-hud");
  if (!container) return;

  // Insert a header row with close button if not already there
  if (!document.getElementById("weather-hud-header")) {
    const header = document.createElement("div");
    header.id = "weather-hud-header";
    header.className = "weather-hud-header";
    header.innerHTML = `<span>ATMOSPHERIC_DATA</span><button class="widget-close-btn" id="weather-hud-close-btn" title="Masquer">✕</button>`;
    container.insertBefore(header, container.firstChild);

    header.querySelector("#weather-hud-close-btn")?.addEventListener('click', () => {
      hideWeatherHudWidget();
    });
  }
  construireVuesMeteo(container);
}

function initWeather(ws: WebSocket | null) {
  // 1. Detection de localisation
  if ("geolocation" in navigator) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        console.log("[METEO] Localisation detectee :", coords);
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "set_location", ...coords }));
        }
      },
      (err) => {
        console.warn("[METEO] Geolocation refusee ou erreur :", err.message);
        // Le backend utilisera l'IP par defaut
      }
    );
  }
}
