import { locale } from "../i18n/i18n";
import { timerDisplayEl, timerHudEl, timerProgressEl } from "./dom_refs";
import { signalerOutils } from "./donnees_outils";

// ── Minuteurs ───────────────────────────────────────────────────────────────
// Le backend peut avoir plusieurs minuteurs en même temps (chaque « mets un minuteur » en crée un) : le HUD les suit tous.
// #timer-hud porte l'état affiché / masqué (style.display) ; ses pièces éclatées (pieces_outils.ts) lisent `lireMinuteurs()`.
export interface Minuteur { id: number; nom: string; fin: number; total: number; termine: number }

const minuteurs: Minuteur[] = [];
let timerInterval: number | null = null;
let prochainId = 1;

export const lireMinuteurs = (): Minuteur[] => minuteurs;
/** Secondes restantes d'un minuteur (0 une fois fini). */
export const resteMinuteur = (m: Minuteur): number => Math.max(0, Math.ceil((m.fin - Date.now()) / 1000));

function nomDuree(s: number): string {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  if (h) return `${h} H${m ? ` ${String(m).padStart(2, "0")}` : ""}`;
  if (m) return `${m} MIN${r ? ` ${r} S` : ""}`;
  return `${r} S`;
}

function afficher(): void {
  timerHudEl.classList.remove("hidden");
  timerHudEl.style.display = "block";
}

function suivreLeTemps(): void {
  if (timerInterval !== null) return;
  timerInterval = window.setInterval(() => {
    const maintenant = Date.now();
    let change = false;
    for (const m of minuteurs) if (!m.termine && m.fin <= maintenant) { m.termine = maintenant; change = true; }
    // un minuteur fini reste affiché « FIN » trois secondes
    for (let i = minuteurs.length - 1; i >= 0; i--) if (minuteurs[i].termine && maintenant - minuteurs[i].termine > 3000) { minuteurs.splice(i, 1); change = true; }
    updateTimerDisplay();
    if (!minuteurs.length) { stopTimer(); return; }
    if (change) signalerOutils("minuteurs");
  }, 1000);
}

// ── Timer Logic ─────────────────────────────────────────────────────────────
export function startTimer(duration: number) {
  if (duration <= 0) return;
  minuteurs.push({ id: prochainId++, nom: nomDuree(duration), fin: Date.now() + duration * 1000, total: duration, termine: 0 });
  afficher();
  updateTimerDisplay();
  suivreLeTemps();
  signalerOutils("minuteurs");
}

export function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  minuteurs.length = 0;
  timerHudEl.style.display = "none";
  signalerOutils("minuteurs");
}

/** Rallonge le minuteur le plus proche (`tous` : tous les minuteurs en cours). */
export function addTimer(extraSeconds: number, tous = false) {
  const actifs = minuteurs.filter((m) => !m.termine).sort((a, b) => a.fin - b.fin);
  for (const m of tous ? actifs : actifs.slice(0, 1)) { m.fin += extraSeconds * 1000; m.total += extraSeconds; }
  updateTimerDisplay();
  signalerOutils("minuteurs");
}

export function removeTimer(lessSeconds: number) {
  const m = minuteurs.filter((x) => !x.termine).sort((a, b) => a.fin - b.fin)[0];
  if (m) m.fin = Math.max(Date.now(), m.fin - lessSeconds * 1000);
  updateTimerDisplay();
  signalerOutils("minuteurs");
}

// Ancienne boîte (masquée par les pièces éclatées) : elle continue d'afficher le minuteur le plus proche
function updateTimerDisplay() {
  const m = minuteurs.filter((x) => !x.termine).sort((a, b) => a.fin - b.fin)[0];
  if (!m) { timerDisplayEl.textContent = "FINISH"; timerProgressEl.style.width = "100%"; return; }
  const reste = resteMinuteur(m);
  timerDisplayEl.textContent = `${Math.floor(reste / 60).toString().padStart(2, "0")}:${(reste % 60).toString().padStart(2, "0")}`;
  timerProgressEl.style.width = `${((m.total - reste) / m.total) * 100}%`;
  timerDisplayEl.style.color = reste <= 10 ? (reste % 2 === 0 ? "#ff3d00" : "#00e5ff") : "#00e5ff";
}

// ── Clock Logic ─────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString(locale(), { hour12: false });

  // Globe overlay clock (existing)
  const clockEl = document.getElementById("globe-clock");
  if (clockEl) clockEl.textContent = timeStr;

  // Orb HUD clock (top of screen, always visible)
  const orbTime = document.getElementById("orb-time-display");
  if (orbTime) orbTime.textContent = timeStr;

  const orbDate = document.getElementById("orb-date-display");
  if (orbDate) {
    orbDate.textContent = now.toLocaleDateString(locale(), {
      day: '2-digit', month: '2-digit', year: 'numeric'
    });
  }
}
export function initClock(): void {
  setInterval(updateClock, 1000);
  updateClock();
}
