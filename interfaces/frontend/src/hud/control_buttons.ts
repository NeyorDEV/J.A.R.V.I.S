import { toggleArMirror } from "../hand_tracking";
import { wsRef } from "../ws_link";
import { haPanel, haToggleBtn, micBtnEl, settingsModalEl } from "./dom_refs";
import { setMuted } from "./orb_state";
import { openAntivirusPanel } from "../panels/antivirus_panel";

export function initControlButtons(): void {
  // ── Control Buttons Events ───────────────────────────────────────────────────
  document.getElementById("fullscreen-btn")?.addEventListener("click", () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "toggle_fullscreen" }));
    }
  });

  const gesturesToggleBtn = document.getElementById("gestures-toggle") as HTMLButtonElement;
  if (gesturesToggleBtn) {
    // Écouteur direct supprimé : doublon du dispatcher du carrousel. Les deux
    // s'exécutaient à chaque clic, d'où « quand on reclique ça le réouvre ».
    // L'action vit dans bindCarouselAction("gestures-toggle").
  }

  const gesturesMirrorBtn = document.getElementById("gestures-mirror") as HTMLButtonElement;
  if (gesturesMirrorBtn) {
    gesturesMirrorBtn.addEventListener("click", () => {
      const isMirrored = toggleArMirror();
      gesturesMirrorBtn.classList.toggle("active", isMirrored);
      gesturesMirrorBtn.textContent = isMirrored ? "AR MIROIR" : "AR DIRECT";
    });
  }

  // (Bouton « Stopper JARVIS » retiré : JARVIS comprend « stop » / « tais-toi » à la voix,
  //  ou « stop » tapé dans la barre du HUD.)

  // mic-btn = Couper/réactiver le microphone
  micBtnEl?.addEventListener("click", () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "toggle_mic" }));
    }
    // Feedback visuel optimiste (l'état réel sera confirmé par mic_state)
    const isMuted = micBtnEl.classList.contains("is-muted");
    setMuted(!isMuted);
  });
}

// Appelé après initCarouselDock(), comme dans l'ordre d'origine de main.ts.
export function initPanelShortcuts(): void {
  // Lancement manuel du scan antivirus depuis le menu des paramètres
  const settingsAvScanBtn = document.getElementById("settings-av-scan-btn") as HTMLButtonElement;
  if (settingsAvScanBtn) {
    settingsAvScanBtn.addEventListener("click", () => {
      // Fermer le modal des paramètres
      if (settingsModalEl) {
        settingsModalEl.classList.remove("visible");
      }
      // Ouvrir le panneau antivirus et démarrer le scan
      openAntivirusPanel();
    });
  }

  // Raccourci ANTIVIRUS dans le menu principal
  const menuAvScanBtn = document.getElementById("menu-av-scan-btn") as HTMLButtonElement;
  if (menuAvScanBtn) {
    menuAvScanBtn.addEventListener("click", () => {
      // Fermer le menu déroulant (requête dynamique d'éléments)
      const dropdown = document.getElementById("jarvis-menu-dropdown");
      if (dropdown) dropdown.classList.add("hidden");
      const menuBtn = document.getElementById("jarvis-menu-btn");
      if (menuBtn) menuBtn.classList.remove("active");
      // Ouvrir le panneau antivirus
      openAntivirusPanel();
    });
  }

  // ── LOGIQUE DU DASHBOARD DOMOTIQUE HOME ASSISTANT ────────────────────────────
  haToggleBtn?.addEventListener("click", () => {
    if (!haPanel) return;
    const isHidden = haPanel.classList.contains("hidden");
    if (isHidden) {
      haPanel.classList.remove("hidden");
      haToggleBtn.setAttribute("aria-pressed", "true");
      haToggleBtn.classList.add("active");
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ha_get_states" }));
      }
    } else {
      haPanel.classList.add("hidden");
      haToggleBtn.setAttribute("aria-pressed", "false");
      haToggleBtn.classList.remove("active");
    }
  });
}
