import { wsRef } from "../ws_link";
import { apiKeysButtonEl, apiKeysCloseBtn, apiKeysSaveBtn, haPanel, holoButtonEl, jarvisMenuBtn, jarvisMenuDropdown, keyboardHudEl, keyboardToggleButtonEl, settingsCameraSelect, settingsModalEl, subtitleToggleButtonEl } from "./dom_refs";
import { showHelpHUD } from "./help_hud";
import { closeSettingsModal, openSettingsModal } from "./settings";
import { hudState } from "./state";
import { closeUninstallerPanel, openUninstallerPanel } from "../panels/uninstaller_panel";

// ── Events ──────────────────────────────────────────────────────────────────
// ── Unified Menu Event Listeners ─────────────────────────────────────────────
// ⚠ Ce bloc était intégralement enveloppé dans « if (jarvisMenuBtn && jarvisMenuDropdown) ».
// Or #jarvis-menu-btn / #jarvis-menu-dropdown n'existent PLUS dans index.html :
// la condition était donc toujours fausse et TOUT ce qui suit (≈260 lignes) était
// du code mort — dont le bouton SAUVEGARDER de la modale des clés API, qui n'avait
// aucun écouteur et ne faisait donc jamais rien.
// Le câblage propre au menu reste conditionné ; le reste s'exécute maintenant.
export function initMenu(): void {
  if (jarvisMenuBtn && jarvisMenuDropdown) {
    jarvisMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = !jarvisMenuDropdown.classList.contains("hidden");
      if (isOpen) {
        jarvisMenuDropdown.classList.add("hidden");
        jarvisMenuBtn.classList.remove("active");
      } else {
        jarvisMenuDropdown.classList.remove("hidden");
        jarvisMenuBtn.classList.add("active");
      }
    });

    // Close menu when clicking outside of it
    document.addEventListener("click", (e) => {
      const target = e.target as HTMLElement;
      if (!jarvisMenuDropdown.classList.contains("hidden")) {
        if (!jarvisMenuDropdown.contains(target) && target !== jarvisMenuBtn) {
          jarvisMenuDropdown.classList.add("hidden");
          jarvisMenuBtn.classList.remove("active");
        }
      }
    });

    // Close menu when panel-opening buttons are clicked
    jarvisMenuDropdown.querySelectorAll(".menu-action-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.id;
        if (id === "menu-settings-btn" || id === "shopping-toggle-btn" || id === "menu-uninstaller-toggle-btn" || id === "winget-toggle-btn" || id === "menu-holo-btn" || id === "menu-ha-toggle-btn" || id === "menu-keyboard-toggle" || id === "clear-cache-btn" || id === "api-keys-button" || id === "menu-av-scan-btn" || id === "menu-av-live-btn") {
          jarvisMenuDropdown.classList.add("hidden");
          jarvisMenuBtn.classList.remove("active");
        }
      });
    });
  }
    // Liaison des clics du menu unifié vers les boutons jumeaux originaux (évite les doublons d'IDs)
  const menuSubtitleToggle = document.getElementById("menu-subtitle-toggle");
  if (menuSubtitleToggle && subtitleToggleButtonEl) {
    menuSubtitleToggle.addEventListener("click", () => subtitleToggleButtonEl.click());
  }

  const menuHoloBtn = document.getElementById("menu-holo-btn");
  if (menuHoloBtn && holoButtonEl) {
    menuHoloBtn.addEventListener("click", () => holoButtonEl.click());
  }

  const menuUninstallerToggleBtn = document.getElementById("menu-uninstaller-toggle-btn");
  if (menuUninstallerToggleBtn) {
        menuUninstallerToggleBtn.addEventListener("click", () => {
      const uninstallerPanel = document.getElementById("uninstaller-panel");
      if (!uninstallerPanel) return;
      const isHidden = uninstallerPanel.classList.contains("hidden");
      if (isHidden) {
        openUninstallerPanel();
        menuUninstallerToggleBtn.setAttribute("aria-pressed", "true");
        menuUninstallerToggleBtn.classList.add("active");
      } else {
        closeUninstallerPanel();
        menuUninstallerToggleBtn.setAttribute("aria-pressed", "false");
        menuUninstallerToggleBtn.classList.remove("active");
      }
    });
  }

  const menuHaToggleBtn = document.getElementById("menu-ha-toggle-btn");
  if (menuHaToggleBtn) {
    menuHaToggleBtn.addEventListener("click", () => {
      if (!haPanel) return;
      const isHidden = haPanel.classList.contains("hidden");
      if (isHidden) {
        haPanel.classList.remove("hidden");
        menuHaToggleBtn.setAttribute("aria-pressed", "true");
        menuHaToggleBtn.classList.add("active");
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "ha_get_states" }));
        }
      } else {
        haPanel.classList.add("hidden");
        menuHaToggleBtn.setAttribute("aria-pressed", "false");
        menuHaToggleBtn.classList.remove("active");
      }
    });
  }

    const menuSettingsBtn = document.getElementById("menu-settings-btn");
  if (menuSettingsBtn) {
    menuSettingsBtn.addEventListener("click", () => {
      // Masquer le menu déroulant
      if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
      if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");
      
      // Désactiver le clavier visuel s'il est ouvert pour éviter la superposition
      if (hudState.keyboardEnabled && keyboardToggleButtonEl && keyboardHudEl) {
        hudState.keyboardEnabled = false;
        keyboardToggleButtonEl.setAttribute("aria-pressed", "false");
        keyboardHudEl.style.display = "none";
      }

      // Ouvrir directement le modal paramètres
      if (settingsModalEl) {
        settingsModalEl.classList.add("visible");
      }
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "get_settings" }));
      }

      // Énumération autonome des caméras
      if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        navigator.mediaDevices.enumerateDevices()
          .then(devices => {
            const cameras = devices.filter(d => d.kind === "videoinput");
            if (settingsCameraSelect) {
              settingsCameraSelect.innerHTML = '<option value="">-- Détection automatique --</option>';
              cameras.forEach((cam, index) => {
                const opt = document.createElement("option");
                opt.value = cam.deviceId;
                opt.textContent = cam.label || `Caméra ${index + 1} (${cam.deviceId.substring(0, 5)}...)`;
                settingsCameraSelect.appendChild(opt);
              });
                            const savedCam = localStorage.getItem("jarvis-camera-id") || "";
              settingsCameraSelect.value = savedCam;
            }
          })
          .catch(err => {
            console.error("Erreur lors de l'énumération des caméras:", err);
          });
      }
    });
  }

  const menuKeyboardToggle = document.getElementById("menu-keyboard-toggle");
  const keyboardToggle = document.getElementById("keyboard-toggle");
  if (menuKeyboardToggle && keyboardToggle) {
    menuKeyboardToggle.addEventListener("click", () => keyboardToggle.click());
  }

  // ── Antivirus Scan / Live Protection dans le menu unifié ──
  // (L'écouteur de #menu-av-scan-btn a été retiré d'ici : un second existe plus
  //  bas dans le fichier. Les deux étant désormais actifs, un seul clic aurait
  //  lancé DEUX scans antivirus concurrents et réinitialisé l'affichage en
  //  pleine progression. Voir « menuAvScanBtn » plus bas.)

  const menuAvLiveBtn = document.getElementById("menu-av-live-btn");
  const settingsAvLive = document.getElementById("settings-av-live") as HTMLInputElement;
  if (menuAvLiveBtn && settingsAvLive) {
    menuAvLiveBtn.addEventListener("click", () => {
      if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
      if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");
      settingsAvLive.click();
    });
  }
    // ── Bouton Vider Cache / Recharger ──
  const clearCacheBtn = document.getElementById("clear-cache-btn") as HTMLButtonElement;
  if (clearCacheBtn) {
    // Écouteur direct supprimé (doublon du dispatcher du carrousel) : la logique
    // complète — dont la bannière de progression — vit désormais dans
    // bindCarouselAction("clear-cache-btn").
  }

  // ── Bouton Liste des Commandes ──
  const commandsBtn = document.getElementById("commands-btn");
  if (commandsBtn) {
    commandsBtn.addEventListener("click", () => {
      if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
      if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");
      showHelpHUD();
    });
  }
  // ── Bouton de configuration des clés API — ouvre la page paramètres sur l'onglet Clés API ──
  if (apiKeysButtonEl) {
    apiKeysButtonEl.addEventListener("click", () => {
      if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
      if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");
      openSettingsModal("api");
    });
  }

  if (apiKeysCloseBtn) {
    apiKeysCloseBtn.addEventListener("click", () => {
      closeSettingsModal();
    });
  }

  if (apiKeysSaveBtn) {
    apiKeysSaveBtn.addEventListener("click", () => {
      const geminiEnabledEl = document.getElementById("settings-api-gemini-enabled") as HTMLInputElement;
      const groqEnabledEl = document.getElementById("settings-api-groq-enabled") as HTMLInputElement;
      const youtubeEnabledEl = document.getElementById("settings-api-youtube-enabled") as HTMLInputElement;
      const grokEnabledEl = document.getElementById("settings-api-grok-enabled") as HTMLInputElement;
      const serpapiEnabledEl = document.getElementById("settings-api-serpapi-enabled") as HTMLInputElement;
      const anthropicEnabledEl = document.getElementById("settings-api-anthropic-enabled") as HTMLInputElement;
      const mistralEnabledEl = document.getElementById("settings-api-mistral-enabled") as HTMLInputElement;
            const geminiKeyEl = document.getElementById("settings-api-gemini-key") as HTMLInputElement;
      const groqKeyEl = document.getElementById("settings-api-groq-key") as HTMLInputElement;
      const youtubeKeyEl = document.getElementById("settings-api-youtube-key") as HTMLInputElement;
      const grokKeyEl = document.getElementById("settings-api-grok-key") as HTMLInputElement;
      const serpapiKeyEl = document.getElementById("settings-api-serpapi-key") as HTMLInputElement;
      const anthropicKeyEl = document.getElementById("settings-api-anthropic-key") as HTMLInputElement;
      const mistralKeyEl = document.getElementById("settings-api-mistral-key") as HTMLInputElement;

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "update_settings",
          settings: {
            api_gemini_enabled: geminiEnabledEl ? geminiEnabledEl.checked : true,
            api_groq_enabled: groqEnabledEl ? groqEnabledEl.checked : true,
            api_youtube_enabled: youtubeEnabledEl ? youtubeEnabledEl.checked : true,
            api_grok_enabled: grokEnabledEl ? grokEnabledEl.checked : true,
            api_serpapi_enabled: serpapiEnabledEl ? serpapiEnabledEl.checked : true,
            api_anthropic_enabled: anthropicEnabledEl ? anthropicEnabledEl.checked : true,
            api_mistral_enabled: mistralEnabledEl ? mistralEnabledEl.checked : true,
            api_keys: {
              GEMINI_API_KEY: geminiKeyEl ? geminiKeyEl.value.trim() : "",
              GROQ_API_KEY: groqKeyEl ? groqKeyEl.value.trim() : "",
              YOUTUBE_API_KEY: youtubeKeyEl ? youtubeKeyEl.value.trim() : "",
              XAI_API_KEY: grokKeyEl ? grokKeyEl.value.trim() : "",
              SERPAPI_API_KEY: serpapiKeyEl ? serpapiKeyEl.value.trim() : "",
              ANTHROPIC_API_KEY: anthropicKeyEl ? anthropicKeyEl.value.trim() : "",
              MISTRAL_API_KEY: mistralKeyEl ? mistralKeyEl.value.trim() : ""
                          }
          }
        }));
      }
      closeSettingsModal();
    });
  }
}
