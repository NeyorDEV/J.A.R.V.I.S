import { wsRef } from "../ws_link";
import { keyboardHudEl, keyboardInputEl, keyboardToggleButtonEl } from "./dom_refs";
import { hudState } from "./state";
import { makePanelDraggable } from "../ui/draggable";

// (Écouteur de #mute-button retiré ici : un second, plus complet, existe plus bas
//  dans le fichier. Les deux étant actifs, un clic envoyait « stop_audio » DEUX
//  fois et forçait l'orbe en « idle » sans attendre la confirmation du backend.)

// NOTE : l'écouteur "click" direct de #subtitle-toggle a été supprimé. Ce bouton
// vit dans le carrousel, dont le gestionnaire délégué exécute déjà son action via
// _carouselActions. Garder les deux faisait basculer l'état DEUX fois par clic →
// le bouton semblait ne rien faire.
// Voir bindCarouselAction("subtitle-toggle") plus bas.
export function initKeyboard(): void {
  keyboardToggleButtonEl.addEventListener("click", () => {
    hudState.keyboardEnabled = !hudState.keyboardEnabled;
    keyboardToggleButtonEl.setAttribute("aria-pressed", hudState.keyboardEnabled.toString());
    keyboardHudEl.style.display = hudState.keyboardEnabled ? "block" : "none";

    if (hudState.keyboardEnabled) {
      // Réinitialiser la position pour le centrer au cas où il a été glissé précédemment
      keyboardHudEl.style.left = "";
      keyboardHudEl.style.top = "";
      keyboardHudEl.style.right = "";
      keyboardHudEl.style.bottom = "";
      keyboardHudEl.style.transform = "";
      setTimeout(() => keyboardInputEl.focus(), 100);
    }
  });

  // Rendre le clavier HUD déplaçable par son en-tête
  const keyboardHeaderEl = keyboardHudEl?.querySelector(".keyboard-hud-header") as HTMLElement | null;
  if (keyboardHudEl && keyboardHeaderEl) {
    makePanelDraggable(keyboardHudEl, keyboardHeaderEl);
  }

  let keyboardDecryptTimeout: any = null;
  keyboardInputEl.addEventListener("input", () => {
    const statusLabel = document.getElementById("keyboard-status-label");
    if (!statusLabel) return;

    // Effet de décryptage dynamique
    const chars = "0123456789ABCDEFXYZ//_#◈";
    let randomStr = "";
    for (let i = 0; i < 6; i++) {
      randomStr += chars[Math.floor(Math.random() * chars.length)];
    }
      statusLabel.textContent = `DECRYPTING: [ ${randomStr} ]`;
    statusLabel.style.color = "#ff8a1a"; // Orange pendant le décryptage
    statusLabel.style.textShadow = "0 0 8px rgba(255, 138, 26, 0.5)";

    if (keyboardDecryptTimeout) clearTimeout(keyboardDecryptTimeout);
    keyboardDecryptTimeout = setTimeout(() => {
      statusLabel.textContent = "AWAITING_COMMAND...";
      statusLabel.style.color = "#00e5ff"; // Retour au cyan JARVIS
      statusLabel.style.textShadow = "0 0 8px rgba(0, 229, 255, 0.4)";
    }, 400);
  });

  keyboardInputEl.addEventListener("keydown", (e) => {
    const statusLabel = document.getElementById("keyboard-status-label");
    if (e.key === "Enter") {
      const val = keyboardInputEl.value.trim();
      if (val && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
        const targetDir = folderInput?.value.trim() || undefined;
        wsRef.current.send(JSON.stringify({ type: "user_input", text: val, target_dir: targetDir }));
        keyboardInputEl.value = "";
      
        // Flash de statut d'envoi réussi
        if (statusLabel) {
          statusLabel.textContent = "COMMAND_TRANSMITTED";
          statusLabel.style.color = "#00ff88"; // Vert de validation
          statusLabel.style.textShadow = "0 0 10px rgba(0, 255, 136, 0.6)";
          if (keyboardDecryptTimeout) clearTimeout(keyboardDecryptTimeout);
          keyboardDecryptTimeout = setTimeout(() => {
            statusLabel.textContent = "AWAITING_COMMAND...";
            statusLabel.style.color = "#00e5ff";
            statusLabel.style.textShadow = "0 0 8px rgba(0, 229, 255, 0.4)";
          }, 1200);
        }
      }
    }
  });
}
