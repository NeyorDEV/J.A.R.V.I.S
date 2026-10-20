import { icone } from "../panels/pm_utils";
import { wsRef } from "../ws_link";
import { appAddBtn, appAddNameEl, appAddPathEl, appDetectBtn, appDetectSelect, keyboardHudEl, keyboardToggleButtonEl, settingsAgeEl, settingsAppsListEl, settingsCameraSelect, settingsCloseBtn, settingsMicSelect, settingsModalEl, settingsMusiqueLien, settingsNameEl, settingsSaveBtn, swarmLoungeClose, swarmLoungeHud } from "./dom_refs";
import { orb } from "./orb_state";
import { hudState } from "./state";
import { type JarvisMessage } from "../ws/message_types";

// Page paramètres : onglets, ouverture/fermeture, applications personnalisées,
// sauvegarde, et messages settings_data / detected_apps (extraits de main.ts).

let currentCustomApps: { id: string, label: string, exe_path: string }[] = [];

export function handleSettingsMessage(data: JarvisMessage): boolean {
  if (data.type === "detected_apps" && (data as any).apps) {
    if (appDetectSelect && appDetectBtn) {
      appDetectSelect.innerHTML = '<option value="">-- Sélectionner une application détectée --</option>';
      const appsList = (data as any).apps as {nom: string, chemin: string}[];
      appsList.forEach(app => {
        const opt = document.createElement("option");
        opt.value = app.chemin;
        opt.textContent = app.nom;
        appDetectSelect.appendChild(opt);
      });
      appDetectBtn.textContent = `APPS (${appsList.length})`;
    }
            return true;
  }

  if (data.type === "settings_data" && data.data) {
    const settings = data.data as any;
    if (settings.user_name) settingsNameEl.value = settings.user_name;
    if (settings.user_age) settingsAgeEl.value = settings.user_age;
    
    // Microphone dropdown select
    if (settingsMicSelect) {
      settingsMicSelect.innerHTML = '<option value="">-- Détection automatique --</option>';
      if (settings.mic_list) {
        settings.mic_list.forEach((mic: { index: number, name: string }) => {
          const opt = document.createElement("option");
          opt.value = String(mic.index);
          opt.textContent = `[INDEX ${mic.index}] ${mic.name}`;
          if (settings.mic_device_index !== undefined && settings.mic_device_index !== null && Number(settings.mic_device_index) === mic.index) {
            opt.selected = true;
          }
          settingsMicSelect.appendChild(opt);
        });
      }
    }
    
    // Music link
    if (settingsMusiqueLien) {
      settingsMusiqueLien.value = settings.musique_lien || "";
    }

    // Custom Apps
    if (settings.custom_apps) {
      currentCustomApps = settings.custom_apps;
      renderCustomApps();
    }

    // Orb Style & Antivirus Live
            const settingsOrbStyleEl = document.getElementById("settings-orb-style") as HTMLSelectElement;
    if (settingsOrbStyleEl) {
      settingsOrbStyleEl.value = settings.orb_style || "default";
      orb.setTheme(settingsOrbStyleEl.value);
      localStorage.setItem("jarvis-orb-style", settingsOrbStyleEl.value);
    }
    const settingsAvLiveEl = document.getElementById("settings-av-live") as HTMLInputElement;
    if (settingsAvLiveEl) {
      settingsAvLiveEl.checked = settings.av_live_protection === true;
    }

    // Remplissage des clés API
    if (settings.api_keys) {
      const geminiKeyEl = document.getElementById("settings-api-gemini-key") as HTMLInputElement;
      const openaiKeyEl = document.getElementById("settings-api-openai-key") as HTMLInputElement;
      const groqKeyEl = document.getElementById("settings-api-groq-key") as HTMLInputElement;
      const youtubeKeyEl = document.getElementById("settings-api-youtube-key") as HTMLInputElement;
      const grokKeyEl = document.getElementById("settings-api-grok-key") as HTMLInputElement;
      const serpapiKeyEl = document.getElementById("settings-api-serpapi-key") as HTMLInputElement;
      const anthropicKeyEl = document.getElementById("settings-api-anthropic-key") as HTMLInputElement;
      const mistralKeyEl = document.getElementById("settings-api-mistral-key") as HTMLInputElement;

      if (geminiKeyEl) geminiKeyEl.value = settings.api_keys.GEMINI_API_KEY || "";
      if (openaiKeyEl) openaiKeyEl.value = settings.api_keys.OPENAI_API_KEY || "";
      if (groqKeyEl) groqKeyEl.value = settings.api_keys.GROQ_API_KEY || "";
      if (youtubeKeyEl) youtubeKeyEl.value = settings.api_keys.YOUTUBE_API_KEY || "";
      if (grokKeyEl) grokKeyEl.value = settings.api_keys.XAI_API_KEY || "";
      if (serpapiKeyEl) serpapiKeyEl.value = settings.api_keys.SERPAPI_API_KEY || "";
      if (anthropicKeyEl) anthropicKeyEl.value = settings.api_keys.ANTHROPIC_API_KEY || "";
      if (mistralKeyEl) mistralKeyEl.value = settings.api_keys.MISTRAL_API_KEY || "";
    }
            // Remplissage des checkboxes d'activation API
    const geminiEnabledEl = document.getElementById("settings-api-gemini-enabled") as HTMLInputElement;
    const groqEnabledEl = document.getElementById("settings-api-groq-enabled") as HTMLInputElement;
    const youtubeEnabledEl = document.getElementById("settings-api-youtube-enabled") as HTMLInputElement;
    const grokEnabledEl = document.getElementById("settings-api-grok-enabled") as HTMLInputElement;
    const serpapiEnabledEl = document.getElementById("settings-api-serpapi-enabled") as HTMLInputElement;
    const anthropicEnabledEl = document.getElementById("settings-api-anthropic-enabled") as HTMLInputElement;
    const mistralEnabledEl = document.getElementById("settings-api-mistral-enabled") as HTMLInputElement;
    
    if (geminiEnabledEl) geminiEnabledEl.checked = settings.api_gemini_enabled !== false;
    if (groqEnabledEl) groqEnabledEl.checked = settings.api_groq_enabled !== false;
    if (youtubeEnabledEl) youtubeEnabledEl.checked = settings.api_youtube_enabled !== false;
    if (grokEnabledEl) grokEnabledEl.checked = settings.api_grok_enabled !== false;
    if (serpapiEnabledEl) serpapiEnabledEl.checked = settings.api_serpapi_enabled !== false;
    if (anthropicEnabledEl) anthropicEnabledEl.checked = settings.api_anthropic_enabled !== false;
    if (mistralEnabledEl) mistralEnabledEl.checked = settings.api_mistral_enabled !== false;

    // Mise à jour visuelle du bouton de protection live dans le menu unifié
    const menuAvLiveBtn = document.getElementById("menu-av-live-btn");
    if (menuAvLiveBtn) {
      const enabled = settings.av_live_protection === true;
      menuAvLiveBtn.setAttribute("aria-pressed", String(enabled));
      menuAvLiveBtn.innerHTML = enabled
        ? `<span class="btn-icon">${icone("bouclier")}</span> PROT. TEMPS RÉEL : ON`
        : `<span class="btn-icon">${icone("bouclier")}</span> PROT. TEMPS RÉEL : OFF`;
      if (enabled) {
        menuAvLiveBtn.classList.add("active");
        menuAvLiveBtn.style.color = "#00ffcc";
        menuAvLiveBtn.style.borderColor = "#00ffcc";
      } else {
                    menuAvLiveBtn.classList.remove("active");
        menuAvLiveBtn.style.color = "";
        menuAvLiveBtn.style.borderColor = "";
      }
    }
    
    return true;
  }
  return false;
}

// ── Settings UI Logic ────────────────────────────────────────────────────────
// ── Modale Paramètres : ouverture/fermeture centralisées ──────────────────────
// #settings-modal a « display:none » par défaut dans le CSS : on pilote donc
// uniquement la classe .visible. Toute pose de style inline (display:flex) doit
// être évitée, sinon les boutons FERMER / SAUVEGARDER n'arrivent plus à refermer
// la modale (le style inline gagne sur le CSS).
// ── Navigation par onglets de la page paramètres (bandeau vertical) ──────────
function switchSettingsTab(tab: string): void {
  document.querySelectorAll<HTMLButtonElement>(".settings-nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.panel === tab);
  });
  document.querySelectorAll<HTMLElement>(".settings-panel").forEach(panel => {
    panel.classList.toggle("active", panel.dataset.panel === tab);
  });
}

export function initSettingsNav(): void {
  document.querySelectorAll<HTMLButtonElement>(".settings-nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      if (btn.dataset.panel) switchSettingsTab(btn.dataset.panel);
    });
  });

  settingsCloseBtn?.addEventListener("click", closeSettingsModal);
  swarmLoungeClose?.addEventListener("click", () => {
    swarmLoungeHud?.classList.add("hidden");
    if (swarmLoungeHud) swarmLoungeHud.style.display = "none";
  });
}

export function openSettingsModal(tab?: string) {
  if (!settingsModalEl) return;

  // Fermer le clavier visuel pour éviter la superposition
  if (hudState.keyboardEnabled) {
    hudState.keyboardEnabled = false;
    keyboardToggleButtonEl?.setAttribute("aria-pressed", "false");
    if (keyboardHudEl) keyboardHudEl.style.display = "none";
  }

  ["display", "opacity", "visibility"].forEach(p => settingsModalEl.style.removeProperty(p));
  settingsModalEl.classList.remove("hidden");
  settingsModalEl.classList.add("visible");
  switchSettingsTab(tab || "profil");

  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "get_settings" }));
  }

  // Énumération des caméras détectées
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
}

export function closeSettingsModal() {
  if (!settingsModalEl) return;
  settingsModalEl.classList.remove("visible");
  // On purge tout style inline hérité : sans cela un display:flex résiduel
  // maintiendrait la modale affichée malgré le retrait de .visible.
  ["display", "opacity", "visibility"].forEach(p => settingsModalEl.style.removeProperty(p));
}

// (Pas d'écouteur direct sur #settings-button : il est dans le carrousel, dont le
//  dispatcher appelle l'action — en avoir deux annulait le clic.)

function renderCustomApps() {
  settingsAppsListEl.innerHTML = "";
  currentCustomApps.forEach((app, index) => {
    const div = document.createElement("div");
    div.className = "settings-app-item";
    div.innerHTML = `
      <div><strong>${app.label}</strong> <br> <span style="font-size:10px;color:rgba(0,229,255,0.5)">${app.exe_path.replace(/\\/g, '\\\\')}</span></div>
      <div class="settings-app-remove" data-index="${index}">[ X ]</div>
    `;
    settingsAppsListEl.appendChild(div);
  });

  document.querySelectorAll(".settings-app-remove").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt((e.target as HTMLElement).getAttribute("data-index") || "0", 10);
      currentCustomApps.splice(idx, 1);
      renderCustomApps();
    });
  });
}

export function initSettingsForm(): void {
  appAddBtn.addEventListener("click", () => {
    const name = appAddNameEl.value.trim();
    const path = appAddPathEl.value.trim();
    if (name && path) {
      const id = name.toLowerCase().replace(/[^a-z0-9]/g, "_");
      currentCustomApps.push({ id, label: name, exe_path: path });
      appAddNameEl.value = "";
      appAddPathEl.value = "";
      renderCustomApps();
    }
  });

  if (appDetectBtn) {
    appDetectBtn.addEventListener("click", () => {
      appDetectBtn.textContent = "SCAN...";
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "detect_apps" }));
      }
    });
  }
  if (appDetectSelect) {
    appDetectSelect.addEventListener("change", () => {
      const selectedPath = appDetectSelect.value;
      const selectedText = appDetectSelect.options[appDetectSelect.selectedIndex].text;
      if (selectedPath && selectedText) {
        const alreadyExists = currentCustomApps.some(app => app.exe_path === selectedPath);
        if (!alreadyExists) {
          const id = selectedText.toLowerCase().replace(/[^a-z0-9]/g, "_");
          currentCustomApps.push({ id, label: selectedText, exe_path: selectedPath });
          renderCustomApps();
        }
        appDetectSelect.value = "";
      }
    });
  }

  settingsSaveBtn.addEventListener("click", () => {
    const selectedMic = settingsMicSelect.value;

    // Sauvegarde du style de l'orbe dans le localStorage et application instantanée
    const orbStyleSelect = document.getElementById("settings-orb-style") as HTMLSelectElement;
    if (orbStyleSelect) {
      const selectedStyle = orbStyleSelect.value;
      localStorage.setItem("jarvis-orb-style", selectedStyle);
      orb.setTheme(selectedStyle);
    }
  
    // Sauvegarde de la caméra sélectionnée dans le localStorage
    if (settingsCameraSelect) {
      localStorage.setItem("jarvis-camera-id", settingsCameraSelect.value);
    }

    const settingsAvLiveEl = document.getElementById("settings-av-live") as HTMLInputElement;
      const settings = {
      user_name: settingsNameEl.value.trim(),
      user_age: settingsAgeEl.value.trim(),
      mic_device_index: selectedMic === "" ? null : parseInt(selectedMic, 10),
      musique_lien: settingsMusiqueLien.value.trim(),
      custom_apps: currentCustomApps,
      orb_style: orbStyleSelect ? orbStyleSelect.value : "default",
      av_live_protection: settingsAvLiveEl ? settingsAvLiveEl.checked : false
    };
  
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "update_settings", settings }));
    }
  
    settingsModalEl.classList.remove("visible");
  });

  // Toggle visibilité des mots de passe (oeil)
  document.querySelectorAll(".toggle-password-eye").forEach(eye => {
    eye.addEventListener("click", () => {
      const targetId = eye.getAttribute("data-target");
      if (targetId) {
        const input = document.getElementById(targetId) as HTMLInputElement;
        if (input) {
          if (input.type === "password") {
            input.type = "text";
            eye.innerHTML = icone("oeil_barre");
          } else {
            input.type = "password";
            eye.innerHTML = icone("oeil");
          }
        }
      }
    });
  });
}
