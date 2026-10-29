import { initHoloClock } from "../holo_clock";
import { createOrb, type Orb, type OrbState } from "../orb_cylindre";
import { badgeEl, badgeLabelEl, canvas, errorEl, micBtnEl, statusEl, visualizerHudEl } from "./dom_refs";

// ── Orb ───────────────────────────────────────────────────────────────────────
export let orb!: Orb;

export function initOrb(): void {
  orb = createOrb(canvas);
  initHoloClock();

  // Load and apply the saved color theme / orb style
  const savedOrbStyle = localStorage.getItem("jarvis-orb-style") || "cyan";
  orb.setTheme(savedOrbStyle);

  // Initialize select element value
  const orbStyleSelect = document.getElementById("settings-orb-style") as HTMLSelectElement;
  if (orbStyleSelect) {
    orbStyleSelect.value = savedOrbStyle;
    // Aperçu immédiat : l'orbe, l'horloge et les paroles changent de couleur dès le choix
    orbStyleSelect.addEventListener("change", () => {
      localStorage.setItem("jarvis-orb-style", orbStyleSelect.value);
      orb.setTheme(orbStyleSelect.value);
    });
  }
}

// ── State labels (French) ────────────────────────────────────────────────────
const STATE_LABELS: Record<OrbState, string> = {
  idle: "",
  listening: "ecoute...",
  thinking: "reflexion...",
  speaking: "",
  searching: "recherche..."
};

export function applyState(state: OrbState): void {
  orb.setState(state);
  statusEl.textContent = STATE_LABELS[state];

  // Logic for the Visualizer Bar (guarded — element removed in V5)
  if (state === "listening" || state === "thinking") {
    visualizerHudEl?.classList.add("visible");
    visualizerHudEl?.classList.toggle("listening", state === "listening");
        visualizerHudEl?.classList.toggle("thinking", state === "thinking");
  } else {
    visualizerHudEl?.classList.remove("visible", "listening", "thinking");
  }
}

export function setMuted(muted: boolean): void {
  // mic-btn reflects mic mute state (red = muted)
  if (micBtnEl) {
    micBtnEl.classList.toggle("is-muted", muted);
    micBtnEl.setAttribute("aria-pressed", String(muted));
    micBtnEl.title = muted ? "Micro coupé — Cliquez pour réactiver" : "Cliquez pour couper le micro";
  }
}

// ── Error toast ───────────────────────────────────────────────────────────────
let errorTimer: ReturnType<typeof setTimeout> | null = null;

export function showError(msg: string): void {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  if (errorTimer) clearTimeout(errorTimer);
  errorTimer = setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 4_000);
}

// ── Connection badge ──────────────────────────────────────────────────────────
export function setConnected(ok: boolean): void {
  badgeEl.classList.toggle("connected", ok);
  badgeEl.classList.toggle("disconnected", !ok);
  badgeLabelEl.textContent = ok ? "connecte" : "reconnexion";
  if (micBtnEl) micBtnEl.disabled = !ok;
}
