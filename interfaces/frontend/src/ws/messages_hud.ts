import { type OrbState } from "../orb";
import { statusEl } from "../hud/dom_refs";
import { showHelpHUD } from "../hud/help_hud";
import { applyState, orb, setMuted } from "../hud/orb_state";
import { showSubtitles } from "../hud/subtitles";
import { addTimer, removeTimer, startTimer, stopTimer } from "../hud/timer_clock";
import { updateVoiceVaultUI } from "../panels/vault_panel";
import { showTempPanel, showWeatherPanel } from "../panels/weather_temp_panels";
import { type JarvisMessage } from "./message_types";

// Messages backend : coffre-fort, actions DOM, aide, minuteur, globe, sous-titres,
// stats système, panneaux, recette, état de l'orbe (fin du gestionnaire de main.ts).
export function handleHudMessage(data: JarvisMessage, pushDomAction: (domAction: any) => void): void {
  // ── VOICE VAULT WEBSOCKET HANDLERS ──
  if (data.type === "vault_status" || data.type === "vault_unlock_result" || data.type === "vault_file_added" || data.type === "vault_file_deleted" || data.type === "vault_lock_result") {
    updateVoiceVaultUI(data);
    return;
  }

  if (data.type === "dom_action") {
    pushDomAction(data);
    return;
  }

  if (data.action === "help") {
    showHelpHUD();
    return;
  }
  if (data.action === "timer_start") {
    startTimer(data.duration || 0);
    return;
  }
  if (data.action === "timer_stop") {
    stopTimer();
    return;
  }
  if (data.action === "timer_add") {
    addTimer(data.duration || 60);
    return;
  }
  if (data.action === "timer_remove") {
    removeTimer(data.duration || 60);
    return;
  }
  if (data.action === "demo") {
    orb.triggerDemo();
    return;
  }
  // ── Globe 3D Navigation ─────────────────────────────────────────
        if (data.action === "jarvis_globe") {
    if (typeof (window as any).jarvisGlobe === "function") {
      (window as any).jarvisGlobe(data);
    }
    return;
  }
  if (data.action === "set_volume" && typeof data.volume === "number") {
    orb.setVolume(data.volume);
    return;
  }
  if (data.action === "jarvis_text" && typeof data.text === "string") {
    showSubtitles(data.text);
    return;
  }
  if (data.action === "interim_speech" && typeof data.text === "string") {
    const container = document.getElementById("subtitle-hud")!;
    const textEl = document.getElementById("subtitle-text")!;
    const metaEl = document.getElementById("subtitle-meta")!;
    if (container && textEl && metaEl) {
      container.style.display = "block";
      textEl.textContent = data.text;
      textEl.style.fontStyle = "italic";
      textEl.style.color = "rgba(0, 229, 255, 0.85)";
      metaEl.textContent = "DECRYPTING_SPEECH_STREAM...";
      metaEl.style.color = "rgba(0, 229, 255, 0.6)";
    }
    return;
  }
  if (data.action === "system_stats") {
            const cpuVal = document.getElementById("cpu-value");
    const ramVal = document.getElementById("ram-value");
    const cpuHud = document.getElementById("cpu-hud");
    const ramHud = document.getElementById("ram-hud");
    const cpuBar = document.getElementById("cpu-bar-fill") as HTMLDivElement | null;
    const ramBar = document.getElementById("ram-bar-fill") as HTMLDivElement | null;

    if (cpuVal && typeof data.cpu === "number") {
      cpuVal.textContent = `${Math.round(data.cpu)}%`;
      cpuHud?.classList.toggle("stat-critical", data.cpu > 90);
      if (cpuBar) cpuBar.style.width = `${Math.min(100, data.cpu)}%`;
    }
    if (ramVal && typeof data.ram === "number") {
      ramVal.textContent = `${Math.round(data.ram)}%`;
      ramHud?.classList.toggle("stat-critical", data.ram > 90);
      if (ramBar) ramBar.style.width = `${Math.min(100, data.ram)}%`;
    }
    return;
  }

  if (data.action === "temp_panel" && data.data) {
    showTempPanel(data.data as Parameters<typeof showTempPanel>[0]);
  }

  if (data.action === "weather_panel" && data.data) {
    showWeatherPanel(data.data as Parameters<typeof showWeatherPanel>[0]);
  }

  if (data.type === "show_recipe") {
    const modal = document.getElementById("recipe-modal");
    const titleEl = document.getElementById("recipe-title");
    const ingListEl = document.getElementById("recipe-ingredients-list");
    const instListEl = document.getElementById("recipe-instructions-list");

    if (modal && titleEl && ingListEl && instListEl) {
      titleEl.textContent = (data as any).titre || "RECETTE J.A.R.V.I.S";

      ingListEl.innerHTML = "";
                const ingredients = (data as any).ingredients || [];
      ingredients.forEach((ing: string) => {
        const li = document.createElement("li");
        li.textContent = ing;
        ingListEl.appendChild(li);
      });

      instListEl.innerHTML = "";
      const instructions = (data as any).instructions || [];
      instructions.forEach((inst: string) => {
        const li = document.createElement("li");
        li.textContent = inst;
        instListEl.appendChild(li);
      });

      modal.classList.remove("hidden");
    }
    return;
  }

  if (data.state) {
    applyState(data.state as OrbState);
    if (data.status_text && statusEl) {
      statusEl.textContent = data.status_text;
    }
  }
  if (typeof data.volume === "number") {
    orb.setVolume(data.volume);
  }
  if (typeof data.muted === "boolean") {
    setMuted(data.muted);
  }
}
