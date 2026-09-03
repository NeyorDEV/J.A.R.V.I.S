/**
 * J.A.R.V.I.S — Interface Web avec Orbe Three.js
 *
 * Se connecte au backend Python via WebSocket (ws://localhost:8765),
 * recoit les changements d'etat et pilote l'orbe en consequence.
 *
 * Etats: "idle" | "listening" | "thinking" | "speaking"
 */

import { createOrb, type OrbState } from "./orb";
import { injectVisionButton, captureFrame, toggleVision } from "./screen_capture";
import { initJarvisGlobe } from "./globe";
import { initWidgets, updateWeatherUI, updateMusicUI } from "./widgets";
import { cardManager } from "./cards";
import { initHoloClock } from "./holo_clock";
import { initHandTracking, toggleHandTracking, toggleArMirror } from "./hand_tracking";
import { activerHolo, desactiverHolo } from "./hologramme";
import { SpatialFileExplorer } from "./spatial_explorer";
import { DomoticMap } from "./domotic_map";
import { CortexMap } from "./cortex_map";
import { initHADashboard, handleHAMessage } from "./ha_dashboard";
import { ChessMap } from "./chess_map";
import { NetworkRadar } from "./network_radar";
import { wsRef } from "./ws_link";
import { makeDraggable, makePanelDraggable } from "./ui/draggable";
import { initDynamicUserTips } from "./ui/tips";
import { initDynamicAmbientGlow, initMagneticButtons } from "./ui/effects";
import { initCarouselDock, hideCarouselArrow, showCarouselArrow, refreshCarousel } from "./ui/carousel";
import { showImageHUD, showImagePanel } from "./panels/image_panels";
import { openAntivirusPanel, closeAntivirusPanel, handleAntivirusWSMessage } from "./panels/antivirus_panel";
import { setShoppingList, openShoppingPanel } from "./panels/shopping_panel";
import { openUninstallerPanel, closeUninstallerPanel, handleInstalledPrograms, updateUninstallProgress, showUninstallComplete, showCleanComplete } from "./panels/uninstaller_panel";
import { openWingetPanel, closeWingetPanel, handleWingetUpgrades, appendWingetProgress } from "./panels/winget_panel";
import { LiveAudioEngine } from "./live_audio";
import { SwarmLounge } from "./swarm_lounge";

// Expose SpatialFileExplorer class globally for hologramme.js
(window as any).SpatialFileExplorer = SpatialFileExplorer;
(window as any).DomoticMap = DomoticMap;
(window as any).CortexMap = CortexMap;
(window as any).ChessMap = ChessMap;
(window as any).NetworkRadar = NetworkRadar;

import "./css/index.css";
import "./widgets.css";

// ── Config ────────────────────────────────────────────────────────────────────
const WS_URL = `ws://${window.location.hostname}:8765`;
const RECONNECT_INTERVAL_MS = 2_000;

// ── Boot sequence state ───────────────────────────────────────────────────────
let bootConnectedCallback: (() => void) | null = null;
let wsConnectedBeforeBoot = false;
let bootOrbSphereStop: (() => void) | null = null;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const canvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
const statusEl = document.getElementById("status-text") as HTMLDivElement;
const errorEl = document.getElementById("error-text") as HTMLDivElement;
const badgeEl = document.getElementById("connection-badge") as HTMLDivElement;
const badgeLabelEl = document.getElementById(
  "connection-label"
) as HTMLSpanElement;
const muteButtonEl = document.getElementById("mute-button") as HTMLButtonElement;
const micBtnEl = document.getElementById("mic-btn") as HTMLButtonElement;
const jarvisMenuBtn = document.getElementById("jarvis-menu-btn") as HTMLButtonElement;
const jarvisMenuDropdown = document.getElementById("jarvis-menu-dropdown") as HTMLDivElement;
const apiKeysButtonEl = document.getElementById("api-keys-button") as HTMLButtonElement;
const apiKeysCloseBtn = document.getElementById("api-keys-close-btn") as HTMLSpanElement;
const apiKeysSaveBtn = document.getElementById("api-keys-save-btn") as HTMLButtonElement;
const gpuButtonEl = document.getElementById("gpu-button") as HTMLButtonElement;
const helpOverlayEl = document.getElementById("help-overlay") as HTMLDivElement;
const timerHudEl = document.getElementById("timer-hud") as HTMLDivElement;
const timerDisplayEl = document.getElementById("timer-display") as HTMLDivElement;
const timerProgressEl = document.getElementById("timer-progress") as HTMLDivElement;
const subtitleToggleButtonEl = document.getElementById("subtitle-toggle") as HTMLButtonElement;
const keyboardToggleButtonEl = document.getElementById("keyboard-toggle") as HTMLButtonElement;
const keyboardHudEl = document.getElementById("keyboard-hud") as HTMLDivElement;
const keyboardInputEl = document.getElementById("keyboard-input") as HTMLInputElement;
const visualizerHudEl = document.getElementById("visualizer-hud") as HTMLDivElement;

const settingsButtonEl = document.getElementById("settings-button") as HTMLButtonElement;
const settingsModalEl = document.getElementById("settings-modal") as HTMLDivElement;
const holoButtonEl = document.getElementById("holo-button") as HTMLButtonElement;
const haToggleBtn = document.getElementById("ha-toggle-btn") as HTMLButtonElement;
const haPanel = document.getElementById("ha-panel") as HTMLDivElement;
const settingsCloseBtn = document.getElementById("settings-close-btn") as HTMLSpanElement;
const settingsNameEl = document.getElementById("settings-name") as HTMLInputElement;
const settingsAgeEl = document.getElementById("settings-age") as HTMLInputElement;
const settingsAppsListEl = document.getElementById("settings-apps-list") as HTMLDivElement;
const appAddNameEl = document.getElementById("app-add-name") as HTMLInputElement;
const appAddPathEl = document.getElementById("app-add-path") as HTMLInputElement;
const appAddBtn = document.getElementById("app-add-btn") as HTMLButtonElement;
const settingsSaveBtn = document.getElementById("settings-save-btn") as HTMLButtonElement;

// New settings fields DOM refs
const settingsMicSelect = document.getElementById("settings-mic") as HTMLSelectElement;
const settingsCameraSelect = document.getElementById("settings-camera") as HTMLSelectElement;
const settingsMusiqueLien = document.getElementById("settings-musique-lien") as HTMLInputElement;
const appDetectBtn = document.getElementById("app-detect-btn") as HTMLButtonElement;
const appDetectSelect = document.getElementById("app-detect-select") as HTMLSelectElement;

// (Refs courses extraites dans panels/shopping_panel.ts)
// Swarm 3D Command Center Modal DOM refs
const swarmLoungeHud = document.getElementById("swarm-lounge-hud") as HTMLDivElement;
const swarmLoungeClose = document.getElementById("swarm-lounge-close") as HTMLButtonElement;
const swarmTerminalLogs = document.getElementById("swarm-terminal-logs") as HTMLDivElement;

let swarmLoungeInstance: SwarmLounge | null = null;
window.addEventListener("DOMContentLoaded", () => {
  try {
    const canvasEl = document.getElementById("swarm-lounge-canvas") as HTMLCanvasElement;
    if (canvasEl) {
      swarmLoungeInstance = new SwarmLounge("swarm-lounge-canvas");
      swarmLoungeInstance.start();
      (window as any).swarmLounge = swarmLoungeInstance;
    }
  } catch (e) {
    console.warn("Could not init SwarmLounge 3D Canvas:", e);
  }
});

swarmLoungeClose?.addEventListener("click", () => {
  swarmLoungeHud?.classList.add("hidden");
  if (swarmLoungeHud) swarmLoungeHud.style.display = "none";
});

// Website Builder Console HUD DOM refs
const wbHud = document.getElementById("website-builder-hud") as HTMLDivElement;
const wbCloseBtn = document.getElementById("wb-close-btn") as HTMLButtonElement;
const wbStepBadge = document.getElementById("wb-step-badge") as HTMLSpanElement;
const wbStatusText = document.getElementById("wb-status-text") as HTMLSpanElement;
const wbImagesCount = document.getElementById("wb-images-count") as HTMLSpanElement;
const wbProgressPct = document.getElementById("wb-progress-pct") as HTMLSpanElement;
const wbProgressFill = document.getElementById("wb-progress-fill") as HTMLDivElement;
const wbTerminalLogs = document.getElementById("wb-terminal-logs") as HTMLDivElement;

wbCloseBtn?.addEventListener("click", () => {
  wbHud?.classList.add("hidden");
  if (wbHud) wbHud.style.display = "none";
});

const wbBrowseBtn = document.getElementById("wb-browse-btn");
if (wbBrowseBtn) {
  wbBrowseBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "select_folder" }));
    }
  });
}

// (Refs winget extraites dans panels/winget_panel.ts)

// (Refs désinstallateur extraites dans panels/uninstaller_panel.ts)


let currentCustomApps: { id: string, label: string, exe_path: string }[] = [];


let subtitlesEnabled = true;
let keyboardEnabled = false;

let timerInterval: number | null = null;
let timerSeconds = 0;
let timerTotalSeconds = 0;
const HELP_COMMANDS = [
  // Heure & Date
  "Quelle heure est-il ?",
  "On est quel jour ?",
  "Quelle date sommes-nous ?",
  "C'est quel mois ?",
  "Quelle année est-ce ?",
  "J'ai quel âge ?",
  
  // Système PC
  "Niveau de la batterie",
  "Niveau de charge du PC",
  "Utilisation du CPU",
  "Charge du processeur",
  "Utilisation de la RAM",
  "Mémoire vive disponible",
  "Allumé depuis combien de temps ?",
  "PC allumé depuis quand ?",
  "Uptime système",
  "Volume monte",
  "Volume baisse",
  "Coupe le son",
  "Volume à 50%",
  "Remets le son",
  "Prends une capture d'écran",
  "Prends un screenshot",
  "Vide la corbeille",
  "Nettoie la corbeille",
  "Éteins le PC dans 5 minutes",
  "Redémarre le PC",
  "Mets le PC en veille",
  "Verrouille le PC",
  "Annule l'arrêt",

  // Gestion des Fichiers & Dossiers
  "Ouvre mon Bureau",
  "Ouvre mes Documents",
  "Ouvre mes Téléchargements",
  "Ouvre mes Images",
  "Ouvre le dossier Documents",
  "Ouvre le fichier photo.jpg",
  "Range mes dossiers",
  "Mosaïque dossiers",
  "Trie mes fichiers par type",
  "Trie mes fichiers par date",
  "Crée le dossier Projets",
    "Renomme ancien_dossier en nouveau_dossier",
  "Déplace photo.jpg vers Images",
  "Analyse le fichier de notes",

  // Applications & Jeux
  "Ouvre la calculatrice",
  "Ouvre Notepad",
  "Ouvre Paint",
  "Ouvre Chrome",
  "Ouvre le gestionnaire de tâches",
  "Ferme la calculatrice",
  "Mode Boulot !",
  "Mode Gaming",
  "On joue !",
  "On joue à Rocket League",

  // Contrôle de l'Interface Graphique (HUD)
  "Ouvre les paramètres",
  "Ferme les paramètres",
  "Boost le GPU",
  "Active l'accélération graphique",
  "Active les sous-titres",
  "Active le clavier",
  "Ferme la météo",
  "Montre le widget Calendrier",
  "Active le mode hologramme",
  "Active le mode AR",
  "Active le miroir holo",

  // Minuteurs Interactifs
  "Mets un minuteur de 10 minutes",
  "Lance un timer de 5 minutes",
  "Ajoute 2 minutes au minuteur",
  "Retire 1 minute au minuteur",
  "Annule le minuteur",
  "Combien de temps reste-t-il ?",

  // Explorateur Spatial 3D & Carte 3D
  "Ouvre l'explorateur spatial",
  "Affiche mes fichiers en 3D",
  "Affiche ma maison en 3D",
  "Affiche la carte domotique 3D",
  
  // Cortex Neuronal 3D
  "Affiche ton cortex",
  "Ouvre le cortex neuronal",
  "Cherche dans mon cortex la musique",
  "Trouve dans le cortex la météo",
  "Lis ce souvenir",
  "Raconte cette mémoire",

  // Échecs 3D
  "On joue aux échecs",
  "Lance une partie d'échecs",
  "Lance la partie avec les noirs",
  "Réinitialise la partie d'échecs",
  "Quitte les échecs",
  "Lance la partie niveau moyen",
  "Lance la partie sans chrono",

  // Globe Terrestre 3D
  "Affiche la Terre",
  "Vue depuis l'espace",
  "Zoom sur la Terre",
  "Vol vers Tokyo",
  "Affiche ma position",
  "Où suis-je ?",
  "Trajet de Paris à Lyon",
  "Ferme le globe",

  // Télévision & Multimédia
  "Allume la télé",
  "Éteins la télé",
  "Lance Netflix sur la télé",
  "Mets du rock sur YouTube (Télé)",
  "Pause la télé",
  "Reprends la télé",
  "Monte le son de la télé",

    // Musique Spotify & Deezer
  "Lance Spotify",
  "Joue Billie Jean sur Spotify",
  "Suivant sur Spotify",
  "Volume Spotify monte",
  "Ouvre Deezer",
  "Recherche Michael Jackson sur Deezer",
  "Mets de la musique sur YouTube (PC)",

  // HomePod Mini & Audio Casque
  "Passe ta voix sur le HomePod",
  "Bascule sur le casque",
  "Règle le volume du HomePod à 50%",
  "Pause le HomePod",

  // Autopilote Web & Vision IA
  "Cherche un hôtel à Annecy sur Booking",
  "Cherche une PS5 moins de 400€ à Lyon",
  "Cherche les vols Paris-Barcelone sur Kayak",
  "Ferme le navigateur",
  "Lance l'autopilote OS",

  // Domotique Home Assistant
  "Allume la lumière du Salon",
  "Éteins la lumière du Bureau",
  "Mets la lumière en Bleu",
  "Règle la luminosité à 80%",
  "Quelle est la température dans le Salon ?",
  "Quel est le taux d'humidité dans le Bureau ?",
  "Combien d'abonnés sur TikTok ?",
  "Anniversaires du jour",
  "Active la scène Cinéma",
  "Désactive l'alarme",
  "Verrouille la porte",
  "Aspire la maison",
  "Retour à la base de l'aspirateur",

    // Intelligence & Assistance IA
  "Recherche approfondie sur l'intelligence artificielle",
  "Analyse mon écran",
  "Aide-moi",
  "Lance la caméra",
  "Regarde-moi",
  "Génère une image d'un coucher de soleil",
  "Dessine-moi une voiture de sport",
  "Tape le texte dicté",
  "Souviens-toi que j'aime le café",
  "Qu'est-ce que tu sais sur moi ?",
  "Liste ma mémoire",
  "Cherche dans mes souvenirs l'anniversaire",

  // Google Workspace
  "Crée un Google Doc intitulé Réunion",
  "Lis le contenu de mon Google Doc",
  "Lis mes nouveaux emails",
  "Lis le détail du dernier email",
  "Envoie un email à mylane@example.com",
  "Montre mon agenda",
  "Quels sont mes événements ?",
  "Ouvre mon Google Drive",
  "Ajoute une tâche faire les courses",

  // Sécurité & Mises à Jour
  "Analyse mon PC",
  "Lance le scan antivirus",
  "Active la protection en temps réel",
  "Mets à jour mes logiciels",
  "Lance winget",

  // Compétences Dynamiques / Démonstrations
  "Crée la compétence recherche_web",
  "Liste toutes tes compétences",
  "Lance la démo",
  "Écris le mot JARVIS",

    // Configuration & Flux
  "Prends la voix d'homme",
  "Prends la voix de femme",
  "Active le mode Iron Man",
  "Silence !",
  "Tais-toi !"
];

// ── Orb ───────────────────────────────────────────────────────────────────────
const orb = createOrb(canvas);
initHoloClock();

// Load and apply the saved color theme / orb style
const savedOrbStyle = localStorage.getItem("jarvis-orb-style") || "cyan";
orb.setTheme(savedOrbStyle);

// Initialize select element value
const orbStyleSelect = document.getElementById("settings-orb-style") as HTMLSelectElement;
if (orbStyleSelect) {
  orbStyleSelect.value = savedOrbStyle;
}

// ── State labels (French) ────────────────────────────────────────────────────
const STATE_LABELS: Record<OrbState, string> = {
  idle: "",
  listening: "ecoute...",
  thinking: "reflexion...",
  speaking: "",
  searching: "recherche..."
};

function applyState(state: OrbState): void {
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

function setMuted(muted: boolean): void {
  // mic-btn reflects mic mute state (red = muted)
  if (micBtnEl) {
    micBtnEl.classList.toggle("is-muted", muted);
    micBtnEl.setAttribute("aria-pressed", String(muted));
    micBtnEl.title = muted ? "Micro coupé — Cliquez pour réactiver" : "Cliquez pour couper le micro";
  }
}

// ── Error toast ───────────────────────────────────────────────────────────────
let errorTimer: ReturnType<typeof setTimeout> | null = null;

function showError(msg: string): void {
  errorEl.textContent = msg;
  errorEl.style.opacity = "1";
  if (errorTimer) clearTimeout(errorTimer);
  errorTimer = setTimeout(() => {
    errorEl.style.opacity = "0";
  }, 4_000);
}

// ── Connection badge ──────────────────────────────────────────────────────────
function setConnected(ok: boolean): void {
  badgeEl.classList.toggle("connected", ok);
  badgeEl.classList.toggle("disconnected", !ok);
  badgeLabelEl.textContent = ok ? "connecte" : "reconnexion";
  muteButtonEl.disabled = !ok;
  if (micBtnEl) micBtnEl.disabled = !ok;
}



// ── Virtual Cursor for Dynamic HUD Automation ──────────────────────────────────
let virtualCursorHideTimeout: ReturnType<typeof setTimeout> | null = null;

function initVirtualCursor(): HTMLDivElement | null {
  let cursor = document.getElementById("virtual-cursor") as HTMLDivElement;
  if (!cursor) {
    cursor = document.createElement("div");
    cursor.id = "virtual-cursor";
    document.body.appendChild(cursor);
  }
  return cursor;
}

function getElementCoordinates(el: HTMLElement): Promise<{x: number, y: number}> {
  return new Promise((resolve) => {
    let attempts = 0;
    const check = () => {
      const r = el.getBoundingClientRect();
      if ((r.width > 0 && r.height > 0) || (r.left > 0 || r.top > 0) || attempts > 15) {
        resolve({
          x: r.left + r.width / 2 + window.scrollX,
          y: r.top + r.height / 2 + window.scrollY
        });
      } else {
        attempts++;
        setTimeout(check, 50);
      }
    };
    check();
  });
}

function animateVirtualCursorTo(element: HTMLElement): Promise<void> {
  return new Promise(async (resolve) => {
    const cursor = initVirtualCursor();
    if (!cursor) {
      resolve();
      return;
    }
        if (virtualCursorHideTimeout) {
      clearTimeout(virtualCursorHideTimeout);
      virtualCursorHideTimeout = null;
    }

    if (cursor.style.display !== "block") {
      cursor.style.left = `${window.innerWidth / 2}px`;
      cursor.style.top = `${window.innerHeight / 2}px`;
      cursor.style.display = "block";
      // FORCE UN REFLOW pour garantir que la position de départ (milieu) soit peinte et prise en compte
      cursor.offsetHeight;
    }

    const coords = await getElementCoordinates(element);

    setTimeout(() => {
      cursor.style.left = `${coords.x}px`;
      cursor.style.top = `${coords.y}px`;
      
      setTimeout(resolve, 800);
    }, 50);
  });
}

// ── WebSocket with auto-reconnect ─────────────────────────────────────────────
let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

function connect(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }

  ws = new WebSocket(WS_URL);
  wsRef.current = ws;
  (window as any)._jarvisWs = ws;

  const previousLiveEngine = (window as any).liveAudioEngine as LiveAudioEngine | undefined;
  if (previousLiveEngine) {
    previousLiveEngine.stopLiveSession();
  }
  const liveEngine = new LiveAudioEngine((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  });
  (window as any).liveAudioEngine = liveEngine;

  ws.addEventListener("open", () => {
    setConnected(true);
    // Demander la liste de courses courante
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "get_shopping_list" }));
    }
    // Notifie la séquence de boot que le serveur est prêt
    if (bootConnectedCallback) {
      bootConnectedCallback();
      bootConnectedCallback = null;
    } else {
      wsConnectedBeforeBoot = true;
    }
  });

  // ── DOM Automation Queue to prevent race conditions ───────────────────────────
  const domActionQueue: any[] = [];
  let domActionProcessing = false;

  async function executeSingleDomAction(domAction: any): Promise<void> {
    // Cas dom_sequence : exécuter chaque step dans l'ordre avec délai
    if (domAction.action === "dom_sequence") {
      const steps: any[] = domAction.steps || [];
      for (const step of steps) {
        const delay = (step.delay || 0.5) * 1000;
        await new Promise(r => setTimeout(r, delay));
        // Convertir step (action_type) en format domAction (action)
        await executeSingleDomAction({
          action: step.action_type,
          selector: step.selector,
          text: step.text,
          class_name: step.class_name,
        });
      }
      return;
    }

    const element = domAction.selector ? document.querySelector(domAction.selector) as HTMLElement : null;
    if (!element) return;
        // Scroll automatique : amener l'élément dans la zone visible avant toute interaction
    element.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    await new Promise(r => setTimeout(r, 300)); // Laisser le scroll se terminer

    const cursor = initVirtualCursor();

    if (domAction.action === "click") {
      await animateVirtualCursorTo(element);
      if (cursor) {
        cursor.classList.add("clicking");
        await new Promise(r => setTimeout(r, 200));
      }
      element.click();
      if (cursor) {
        cursor.classList.remove("clicking");
        await new Promise(r => setTimeout(r, 500)); // Pacing de 500ms post-clic
      }
    } else if (domAction.action === "type") {
      await animateVirtualCursorTo(element);
      element.focus();
      await new Promise(r => setTimeout(r, 200));
      
      const text = domAction.text || "";
      const input = element as HTMLInputElement;
      input.value = "";
      for (let i = 0; i < text.length; i++) {
        input.value += text[i];
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        // Vitesse clavier à 100ms
        await new Promise(r => setTimeout(r, 100));
      }
      await new Promise(r => setTimeout(r, 500)); // Pacing de 500ms post-saisie
    } else if (domAction.action === "focus") {
      await animateVirtualCursorTo(element);
      element.focus();
      await new Promise(r => setTimeout(r, 500)); // Pacing de 500ms post-focus
    } else if (domAction.action === "select") {
      await animateVirtualCursorTo(element);
      (element as HTMLSelectElement).value = domAction.text || "";
      element.dispatchEvent(new Event('change', { bubbles: true }));
      await new Promise(r => setTimeout(r, 500)); // Pacing de 500ms post-sélection
          } else if (domAction.action === "add_class") {
      element.classList.add(domAction.class_name || "");
    } else if (domAction.action === "remove_class") {
      element.classList.remove(domAction.class_name || "");
    }

    // Effacer le curseur virtuel après 2 secondes d'inactivité en retournant d'abord au centre
    if (virtualCursorHideTimeout) clearTimeout(virtualCursorHideTimeout);
    virtualCursorHideTimeout = setTimeout(() => {
      if (cursor) {
        cursor.style.left = `${window.innerWidth / 2}px`;
        cursor.style.top = `${window.innerHeight / 2}px`;
        setTimeout(() => {
          cursor.style.display = "none";
        }, 800);
      }
    }, 2000);
  }

  async function processDomActionQueue() {
    if (domActionProcessing || domActionQueue.length === 0) return;
    domActionProcessing = true;
    
    while (domActionQueue.length > 0) {
      const nextAction = domActionQueue.shift();
      try {
        await executeSingleDomAction(nextAction);
      } catch (e) {
        console.error("Erreur d'action DOM dans la queue:", e);
      }
    }
    
    domActionProcessing = false;
  }

  ws.addEventListener("message", async (event: MessageEvent) => {
    try {
            const data = JSON.parse(event.data as string) as {
        state?: string;
        action?: string;
        muted?: boolean;
        volume?: number;
        id?: string;
        duration?: number;
        text?: string;
        type?: string;
        version?: string;
        url?: string;
        cpu?: number;
        ram?: number;
        prompt?: string;
        title?: string;
        icon?: string;
        weather?: any;
        weather_type?: string;
        status_text?: string;
        data?: Record<string, any>;
        pcm_base64?: string;
        sample_rate?: number;
      };

      // ── Gemini Multimodal Live Audio Handler ──
      if (data.action === "live_audio_output" && data.pcm_base64) {
        if ((window as any).liveAudioEngine) {
          (window as any).liveAudioEngine.playIncomingPCM(data.pcm_base64, data.sample_rate || 24000);
        }
      }

      // ── OS Autopilot & Virtual Cursor ──
      if (data.action === "draw_virtual_cursor" && (data as any).x !== undefined && (data as any).y !== undefined) {
        const cursor = document.getElementById("virtual-cursor");
        if (cursor) {
          const wasHidden = cursor.style.display === "none";
          const animDuration = data.duration || 0.8;
          
          // Injecter la durée de transition dynamique
          cursor.style.transition = `left ${animDuration}s cubic-bezier(0.25, 0.8, 0.25, 1), top ${animDuration}s cubic-bezier(0.25, 0.8, 0.25, 1), transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275)`;
                    if (wasHidden) {
            // Positionner initialement au centre pour un premier déplacement fluide
            cursor.style.left = "50%";
            cursor.style.top = "50%";
            cursor.style.display = "block";
            
            // Attendre deux ticks du moteur de rendu pour appliquer le display: block
            requestAnimationFrame(() => {
              requestAnimationFrame(() => {
                cursor.style.left = `${(data as any).x}%`;
                cursor.style.top = `${(data as any).y}%`;
              });
            });
          } else {
            cursor.style.left = `${(data as any).x}%`;
            cursor.style.top = `${(data as any).y}%`;
          }
          
          const duration = animDuration * 1000;
          
          // Nettoyer les anciens timeouts de clic et de masquage
          if ((cursor as any).vcClickTimeout) clearTimeout((cursor as any).vcClickTimeout);
          if ((cursor as any).vcHideTimeout) clearTimeout((cursor as any).vcHideTimeout);
          
          (cursor as any).vcClickTimeout = setTimeout(() => {
            cursor.classList.add("clicking");
            
            const wave = document.createElement("div");
            wave.className = "vc-click-wave";
            cursor.appendChild(wave);
            
            setTimeout(() => {
              cursor.classList.remove("clicking");
              wave.remove();
            }, 600);
          }, duration);
          
          // Masquer le curseur après 3 secondes d'inactivité
          (cursor as any).vcHideTimeout = setTimeout(() => {
            cursor.style.display = "none";
          }, duration + 3000);
        }
        return;
              }

      if (data.action === "os_agent_status") {
        const banner = document.getElementById("os-autopilot-banner");
        const logEl = document.getElementById("os-autopilot-log");
        if (banner && logEl) {
          if ((data as any).active) {
            banner.style.display = "flex";
            logEl.textContent = (data as any).log || "[JARVIS OS AUTOPILOT] ACTIF";
          } else {
            banner.style.display = "none";
            // Cacher le curseur virtuel quand l'autopilote est terminé
            const cursor = document.getElementById("virtual-cursor");
            if (cursor) {
              if ((cursor as any).vcHideTimeout) clearTimeout((cursor as any).vcHideTimeout);
              cursor.style.display = "none";
            }
          }
        }
        return;
      }

      if (data.action === "request_screen_capture") {
        const frame = await captureFrame();
        if (frame && ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "screen_frame",
            id: data.id,
            data: frame,
          }));
        } else if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "screen_frame",
            id: data.id,
            error: "no_stream",
          }));
        }
        return;
      }

      // ── Spatial File Explorer 3D ──
      if (data.type === "spatial_result") {
        const explorer = (window as any)._spatialExplorer;
        if (explorer) explorer.handleServerResponse(data);
        return;
      }
            // ── Image Search ──
      if (data.type === "show_images") {
        showImagePanel((data as any).query || "IMAGE_SCAN", (data as any).images || []);
        return;
      }

      // ── Antivirus WS Messages ──
      if (data.type === "av_open") {
        openAntivirusPanel();
        return;
      }

      if (data.type === "av_start" || data.type === "av_progress" || data.type === "av_threat_detected" || data.type === "av_complete" || data.type === "av_cancel" || data.type === "av_action_result") {
        handleAntivirusWSMessage(data);
        return;
      }

      // ── Uninstaller WS Messages ──
      if (data.action === "uninstaller_open" || data.type === "uninstaller_open") {
        openUninstallerPanel();
        return;
      }

      if (data.type === "installed_programs" && (data as any).programs) {
        handleInstalledPrograms((data as any).programs);
        return;
      }

      if (data.type === "uninstall_progress") {
        updateUninstallProgress(data);
        return;
      }

      if (data.type === "uninstall_complete") {
        showUninstallComplete(data);
        return;
      }

      if (data.type === "clean_complete") {
        showCleanComplete(data);
        return;
      }
            // ── Winget WS Messages ──
      if (data.action === "winget_open" || data.type === "winget_open") {
        openWingetPanel();
        return;
      }

      if (data.type === "winget_upgrades" && (data as any).upgrades) {
        handleWingetUpgrades((data as any).upgrades);
        return;
      }

      if (data.type === "winget_upgrade_progress") {
        appendWingetProgress(data as any);
        return;
      }


      // —— NAVIGATEUR SÉCURISÉ ——
      if (data.action === "browser_state" && data.state) {
        if ((window as any).updateBrowserUIState) {
          (window as any).updateBrowserUIState(data.state);
        }
        return;
      }

      // ── WS File Inspector Read/Write Events ──
      if (data.type === "file_content" || data.action === "file_content") {
        const fileData = data as any;
        const textarea = document.getElementById("code-editor-textarea") as HTMLTextAreaElement;
        const filepathEl = document.getElementById("code-editor-filepath");
        if (textarea && fileData.filepath) {
          textarea.value = fileData.content || (fileData.error ? `// Erreur : ${fileData.error}` : "");
        }
        if (filepathEl && fileData.filepath) {
          filepathEl.textContent = `Fichier : ${fileData.filepath}`;
        }
        return;
      }
            if (data.type === "file_saved" || data.action === "file_saved") {
        const fileData = data as any;
        const saveBtn = document.getElementById("save-code-btn");
        if (saveBtn) {
          const oldText = saveBtn.textContent;
          saveBtn.textContent = fileData.success ? "✅ Sauvegardé !" : "❌ Échec !";
          setTimeout(() => { saveBtn.textContent = oldText; }, 2000);
        }
        return;
      }

      if (data.type === "folder_selected") {
        const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
        if (folderInput && (data as any).folder) {
          folderInput.value = (data as any).folder;
        }
        return;
      }

const _projectWrittenCode: Record<string, string> = {};
let _activeStreamFile: string = "";

function getFileBadgeHTML(filename: string): string {
  if (!filename || typeof filename !== "string") return '<span class="file-icon-tag default">FILE</span>';
  const clean = filename.toLowerCase();
  if (clean.endsWith(".html")) {
    return '<span class="file-icon-tag html"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> HTML</span>';
  }
  if (clean.endsWith(".css")) {
    return '<span class="file-icon-tag css"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l9 4.9v10.2L12 22l-9-4.9V6.9L12 2z"/></svg> CSS</span>';
  }
    if (clean.endsWith(".js")) {
    return '<span class="file-icon-tag js"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> JS</span>';
  }
  return '<span class="file-icon-tag default"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/></svg> FILE</span>';
}

function updateLiveCodeStream(fileName?: string, codeContent?: string) {
  const tabsContainer = document.getElementById("swarm-code-tabs");
  const codeContentEl = document.getElementById("swarm-code-content");
  const codeGutterEl = document.getElementById("swarm-code-gutter");

  if (fileName) {
    if (codeContent) {
      _projectWrittenCode[fileName] = codeContent;
    }
    _activeStreamFile = fileName;
  }

  const targetFile = fileName || _activeStreamFile;

  if (tabsContainer) {
    tabsContainer.innerHTML = "";
    const fileKeys = Object.keys(_projectWrittenCode);
    if (fileKeys.length === 0 && targetFile) fileKeys.push(targetFile);

    fileKeys.forEach((fKey) => {
      const tabBtn = document.createElement("button");
      tabBtn.className = `swarm-code-tab ${fKey === targetFile ? "active" : ""}`;
      tabBtn.innerHTML = `${getFileBadgeHTML(fKey)} ${fKey}`;
      tabBtn.style.cursor = "pointer";
      tabBtn.onclick = (e) => {
        e.stopPropagation();
        _activeStreamFile = fKey;
        updateLiveCodeStream(fKey, _projectWrittenCode[fKey]);
      };
      tabsContainer.appendChild(tabBtn);
    });
  }
    const displayCode = (targetFile && _projectWrittenCode[targetFile]) || codeContent || "";
  if (codeContentEl) {
    codeContentEl.textContent = displayCode;

    if (codeGutterEl) {
      const lines = displayCode.split('\n');
      codeGutterEl.innerHTML = lines.map((_, i) => `<span class="ln">${i + 1}</span>`).join('');
    }

    codeContentEl.scrollTop = codeContentEl.scrollHeight;
    if (codeGutterEl) codeGutterEl.scrollTop = codeContentEl.scrollTop;

    codeContentEl.onscroll = () => {
      if (codeGutterEl) codeGutterEl.scrollTop = codeContentEl.scrollTop;
    };
  }
}

      // ── Autonomous Dev Swarm Command Center HUD (Full 3D & 6-Agents) ──
      if (data.action === "dev_swarm_update") {
        const swarmData = data as any;

        // 1. Ouvrir le grand Command Center 3D Swarm Modal
        if (swarmLoungeHud) {
          swarmLoungeHud.classList.remove("hidden");
          swarmLoungeHud.style.display = "flex";
        }

        // 2. Mettre à jour l'état de la scène 3D Three.js
        if (swarmLoungeInstance) {
          swarmLoungeInstance.updateSwarmStatus(
            swarmData.agent || null,
            swarmData.status || 'in_progress',
            swarmData.message || '',
            swarmData.project || ''
          );
        }
                // 3. Mettre à jour les 6 cartes d'agents du volet latéral
        const currentRole = (swarmData.agent || '').toLowerCase();
        const rolesOrder = ['pm', 'ui', 'dev', 'sec', 'qa', 'ops'];
        const currentIndex = rolesOrder.indexOf(currentRole);

        rolesOrder.forEach((r, idx) => {
          const cardEl = document.getElementById(`card-agent-${r}`);
          const statusBadge = document.getElementById(`status-${r}`);
          const msgEl = document.getElementById(`msg-${r}`);

          if (cardEl && statusBadge && msgEl) {
            if (swarmData.status === 'success') {
              cardEl.classList.remove("active");
              statusBadge.className = "card-status-badge success";
              statusBadge.textContent = "SUCCÈS";
            } else if (r === currentRole) {
              cardEl.classList.add("active");
              statusBadge.className = "card-status-badge active";
              statusBadge.textContent = "ACTION";
              if (swarmData.message) msgEl.textContent = swarmData.message;
            } else if (idx < currentIndex) {
              cardEl.classList.remove("active");
              statusBadge.className = "card-status-badge success";
              statusBadge.textContent = "VALIDÉ";
            } else {
              cardEl.classList.remove("active");
              statusBadge.className = "card-status-badge idle";
              statusBadge.textContent = "EN ATTENTE";
            }
          }
        });

        // 4. Mettre à jour le visualiseur de code en direct (Live Stream IDE)
        if (swarmData.current_file) {
          _activeStreamFile = swarmData.current_file;
          updateLiveCodeStream(swarmData.current_file, swarmData.current_code || _projectWrittenCode[swarmData.current_file]);
        }

        // 5. Ajouter une ligne de log au terminal du Command Center
        if (swarmTerminalLogs && (swarmData.log || swarmData.message)) {
                    const logEntry = document.createElement("div");
          logEntry.className = "swarm-log-line";
          const timestamp = new Date().toLocaleTimeString();
          logEntry.textContent = `[${timestamp}] [${swarmData.agent || 'SYS'}] ${swarmData.message || swarmData.log}`;
          swarmTerminalLogs.appendChild(logEntry);
          swarmTerminalLogs.scrollTop = swarmTerminalLogs.scrollHeight;
        }

        return;
      }

      // ── Website Builder Console HUD Event ──
      if (data.action === "website_builder_update") {
        const wbData = data as any;
        if (wbHud) {
          wbHud.classList.remove("hidden");
          wbHud.style.display = "block";
        }
        if (wbStepBadge && wbData.step_label) {
          wbStepBadge.textContent = wbData.step_label;
        }
        if (wbStatusText && wbData.message) {
          wbStatusText.textContent = wbData.message;
        }
        const wbFilesCount = document.getElementById("wb-files-count");
        if (wbFilesCount && wbData.files_count) {
          wbFilesCount.textContent = `${wbData.files_count.generated} / ${wbData.files_count.total}`;
        }
                if (wbImagesCount && wbData.images_count) {
          const imgGen = wbData.images_count.generated !== undefined ? wbData.images_count.generated : 0;
          const imgTot = wbData.images_count.total !== undefined ? wbData.images_count.total : 0;
          wbImagesCount.textContent = `${imgGen} / ${imgTot}`;
        }
        if (wbProgressPct) {
          wbProgressPct.textContent = `${wbData.progress || 0}%`;
        }
        if (wbProgressFill) {
          wbProgressFill.style.width = `${wbData.progress || 0}%`;
        }
        const filesContainer = document.getElementById("wb-files-list-container");
        if (filesContainer && wbData.files_list && Array.isArray(wbData.files_list)) {
          filesContainer.innerHTML = "";
          wbData.files_list.forEach((fItem: any) => {
            const filePath = typeof fItem === "string" ? fItem : (fItem.file_path || fItem.name || String(fItem));
            const btn = document.createElement("button");
            btn.className = "wb-file-btn";
            btn.innerHTML = `${getFileBadgeHTML(filePath)}<span>${filePath}</span>`;
            btn.title = `Cliquer pour éditer / voir ${filePath}`;
            btn.onclick = (e) => {
              e.stopPropagation();
              openCodeEditorModal(filePath, wbData.project_name);
            };
            filesContainer.appendChild(btn);
          });
        }
        if (wbTerminalLogs && wbData.logs && Array.isArray(wbData.logs)) {
          wbTerminalLogs.innerHTML = "";
          wbData.logs.forEach((logStr: string) => {
            const entry = document.createElement("div");
            entry.className = "wb-log-entry";
            if (logStr.includes("IMAGE IA")) entry.classList.add("image");
            else if (logStr.includes("CODE ENGINE")) entry.classList.add("code");
            else if (logStr.includes("succès") || logStr.includes("RÉUSSI")) entry.classList.add("success");

            const fileMatch = logStr.match(/([\w\-\\./]+\.(?:html|css|js|json))/i);
            if (fileMatch) {
              const matchedFile = fileMatch[1];
              const parts = logStr.split(matchedFile);
              entry.appendChild(document.createTextNode(parts[0]));
              
              const fileLink = document.createElement("span");
              fileLink.className = "file-click-link";
              fileLink.textContent = matchedFile;
              fileLink.title = "Cliquer pour ouvrir et éditer ce fichier";
                            fileLink.onclick = (e) => {
                e.stopPropagation();
                openCodeEditorModal(matchedFile, wbData.project_name);
              };
              entry.appendChild(fileLink);
              entry.appendChild(document.createTextNode(parts.slice(1).join(matchedFile)));
            } else {
              entry.textContent = logStr;
            }
            wbTerminalLogs.appendChild(entry);
          });
          wbTerminalLogs.scrollTop = wbTerminalLogs.scrollHeight;
        }
        if (wbData.status === "success" || wbData.status === "failure") {
          setTimeout(() => {
            wbHud?.classList.add("hidden");
            if (wbHud) wbHud.style.display = "none";
          }, 14000);
        }
        return;
      }

function openCodeEditorModal(filePath: string, projectName?: string) {
  const modal = document.getElementById("code-editor-modal");
  const filenameEl = document.getElementById("code-editor-filename");
  const filepathEl = document.getElementById("code-editor-filepath");
  const textarea = document.getElementById("code-editor-textarea") as HTMLTextAreaElement;
  const closeBtn = document.getElementById("close-code-editor");
  const saveBtn = document.getElementById("save-code-btn");
  const previewBtn = document.getElementById("preview-code-btn");

  if (!modal || !textarea) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";

  const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
  const customFolder = folderInput?.value.trim() || "";
    let fullPath = filePath;
  if (!filePath.includes(":") && !filePath.startsWith("/")) {
    if (customFolder) {
      fullPath = `${customFolder}\\${filePath}`;
    } else {
      const proj = projectName || "apexmind_studio_saas";
      fullPath = `n:\\JARVIS\\backend\\sandbox\\${proj}\\${filePath}`;
    }
  }

  if (filenameEl) filenameEl.textContent = `JARVIS // ÉDITEUR (${filePath})`;
  if (filepathEl) filepathEl.textContent = `Fichier : ${fullPath}`;

  textarea.value = `// Chargement de ${filePath} depuis le disque...`;

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "read_file", action: "read_file", filepath: fullPath }));
  }

  if (closeBtn) {
    closeBtn.onclick = () => {
      modal.classList.add("hidden");
      modal.style.display = "none";
    };
  }

  if (saveBtn) {
    saveBtn.onclick = () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "write_file",
          action: "write_file",
          filepath: fullPath,
          content: textarea.value
        }));
      }
    };
  }
    if (previewBtn) {
    previewBtn.onclick = () => {
      const cleanPath = fullPath.replace(/\\/g, "/");
      window.open(`file:///${cleanPath}`, "_blank");
    };
  }
}

      // ── Chess Map 3D ──
      if (data.action === "chess_start") {
        if (!_holoActive) {
          _openHolo();
        }
        setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app) {
            if (!app.chessMap) {
              app.toggleChess();
            }
            setTimeout(() => {
              const chess = (window as any)._chessMap;
              if (chess) {
                // Si la commande provient du serveur avec des paramètres de configuration
                const anyData = data as any;
                if (anyData.difficulty) {
                  const diffSelect = document.getElementById('chess-config-difficulty') as HTMLSelectElement | null;
                  if (diffSelect) diffSelect.value = anyData.difficulty;
                }
                if (anyData.player_color) {
                  const colorSelect = document.getElementById('chess-config-color') as HTMLSelectElement | null;
                  if (colorSelect) colorSelect.value = anyData.player_color;
                }
                if (anyData.use_timer) {
                  const timerSelect = document.getElementById('chess-config-timer') as HTMLSelectElement | null;
                  if (timerSelect) timerSelect.value = anyData.use_timer;
                }

                // Démarrer la partie avec les paramètres si fournis
                if (anyData.difficulty && anyData.player_color && anyData.use_timer) {
                                    chess.startFromConfig(anyData.difficulty, anyData.player_color, anyData.use_timer === 'yes');
                }

                chess.handleGameState(data.state);
              }
            }, 100);
          }
        }, 150);
        return;
      }

      if (data.action === "chess_reset") {
        const chess = (window as any)._chessMap;
        if (chess) {
          chess.resetGame(true); // reset forcé (sans confirm prompt)
        }
        return;
      }

      if (data.action === "chess_stop") {
        const app = (window as any)._holoApp;
        if (app && app.chessMap) {
          app.toggleChess();
        }
        return;
      }

      if (data.action === "chess_game_state") {
        const chess = (window as any)._chessMap;
        if (chess) {
          chess.handleGameState(data.state, (data as any).last_move);
        }
        return;
      }

      if (data.action === "chess_thinking") {
        const chess = (window as any)._chessMap;
        if (chess) {
          chess.handleThinking((data as any).thinking);
        }
        return;
      }
            // ── Network Radar 3D ──
      if (data.action === "network_radar_show") {
        if (!_holoActive) _openHolo();
        setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app && !app.networkRadar) app.toggleNetworkRadar?.();
          const connections = (data as any).connections;
          if (connections) {
            setTimeout(() => {
              const radar = (window as any)._networkRadar;
              if (radar) radar.handleRadarUpdate(connections);
            }, 200);
          }
        }, 150);
        return;
      }
      if (data.action === "network_radar_update") {
        const radar = (window as any)._networkRadar;
        if (radar) radar.handleRadarUpdate((data as any).connections || []);
        return;
      }
      if (data.action === "network_radar_hide") {
        const app = (window as any)._holoApp;
        if (app?.networkRadar) app.toggleNetworkRadar?.();
        return;
      }
      if (data.action === "blocked_ips") {
        const radar = (window as any)._networkRadar;
        if (radar) radar.handleBlockedIps((data as any).ips || []);
        return;
      }

      // ── Domotic Map 3D ──

      if (data.action === "domotic_map_update") {
        const domMap = (window as any)._domoticMap;
        if (domMap) domMap.handleServerResponse(data);
        return;
      }
            // ── Cortex Neuronal 3D ──
      if (data.action === "cortex_list" || 
          data.action === "cortex_update" || 
          data.action === "cortex_new_memory" || 
          data.action === "cortex_link_created" ||
          data.action === "cortex_link_removed" ||
          data.action === "cortex_edit_success") {
        const cortex = (window as any)._cortexMap;
        if (cortex) cortex.handleServerResponse(data);
        return;
      }

      if (data.action === "cortex_search") {
        if (!_holoActive) {
          _openHolo();
        }
        const app = (window as any)._holoApp;
        if (app && !app.cortexMap) {
          app.toggleCortex();
        }
        
        setTimeout(() => {
          const cortex = (window as any)._cortexMap;
          if (cortex && typeof (data as any).query === "string") {
            cortex.searchCortex((data as any).query);
          }
        }, 250);
        return;
      }

      if (data.action === "cortex_vocal_speak_request") {
        const cortex = (window as any)._cortexMap;
        if (cortex) {
          cortex.handleVocalSpeakRequest();
        }
        return;
      }

      if (data.action === "open_spatial_explorer") {
        if (!_holoActive) {
          _openHolo();
        }
                setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app) {
            if (!app.spatialExplorer) {
              app.toggleExplorer();
            }
          }
        }, 150);
        return;
      }

      if (data.action === "domotic_audio_route_animation") {
        if (!_holoActive) {
          _openHolo();
        }
        setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app && !app.domoticMap) {
            app.toggleDomotic();
          }
          setTimeout(() => {
            const domMap = (window as any)._domoticMap;
            if (domMap) domMap.handleServerResponse(data);
          }, 250);
        }, 200);
        return;
      }

      if (data.action === "open_domotic_map") {
        if (!_holoActive) {
          _openHolo();
        }
        setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app) {
            if (!app.domoticMap) {
              app.toggleDomotic();
            }
          }
        }, 150);
        return;
      }
            if (data.action === "open_cortex") {
        if (!_holoActive) {
          _openHolo();
        }
        setTimeout(() => {
          const app = (window as any)._holoApp;
          if (app) {
            if (!app.cortexMap) {
              app.toggleCortex();
            }
          }
        }, 150);
        return;
      }

      if (data.action === "orb_write_word" && (data as any).word) {
        if (orb) {
          orb.writeWord((data as any).word);
        }
        return;
      }

      if (data.action === "display_image" && data.url) {
        showImageHUD(data.url, data.prompt || "--");
        return;
      }
      if (data.action === "ctx_card") {
        cardManager.showCard({
          title: data.title || "INFORMATION",
          content: data.text || "",
          type: data.type as any,
          duration: data.duration,
          icon: data.icon
        });
        return;
      }
      if (data.action === "weather_update" && data.weather) {
        updateWeatherUI(data.weather, data.weather_type as 'local' | 'monistrol');
        return;
              }
      if (data.action === "music_update" && data.data) {
        updateMusicUI(data.data);
        return;
      }

      // ── Shopping List ────────────────────────────────────────────────────
      if (data.type === "shopping_list" && (data as any).items !== undefined) {
        setShoppingList((data as any).items);
        return;
      }
      if (data.type === "shopping_open") {
        openShoppingPanel();
        return;
      }

      // ── Home Assistant WS Messages ──
      if (data.type === "ha_states" || data.type === "ha_state_changed" || data.type === "ha_service_result") {
        handleHAMessage(data);
        return;
      }

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
          appDetectBtn.textContent = `🔍 APPS (${appsList.length})`;
        }
                return;
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
            ? `<span class="btn-icon">🛡️</span> PROT. TEMPS RÉEL : ON`
            : `<span class="btn-icon">🛡️</span> PROT. TEMPS RÉEL : OFF`;
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
        
        return;
      }

      // ── VOICE VAULT WEBSOCKET HANDLERS ──
      if (data.type === "vault_status" || data.type === "vault_unlock_result" || data.type === "vault_file_added" || data.type === "vault_file_deleted" || data.type === "vault_lock_result") {
        updateVoiceVaultUI(data);
        return;
      }

      if (data.type === "dom_action") {
        domActionQueue.push(data);
        processDomActionQueue();
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
    } catch {
      // ignore malformed messages
    }
  });

  ws.addEventListener("close", () => {
    setConnected(false);
    applyState("idle");
    scheduleReconnect();
  });

  ws.addEventListener("error", () => {
    setConnected(false);
  });
}

// ── Subtitles HUD Logic ──────────────────────────────────────────────────────
let subtitleTimer: number | null = null;
let subtitleTypeInterval: number | null = null;
let hudLogs: string[] = [];

function showSubtitles(text: string) {
  const container = document.getElementById("subtitle-hud")!;
  const textEl = document.getElementById("subtitle-text")!;
  const metaEl = document.getElementById("subtitle-meta")!;

  if (textEl) {
    textEl.style.fontStyle = "normal";
    textEl.style.color = "#00e5ff";
  }

  // Si c'est un message du HUD de compilation (Iron Man Matrix)
  if (text.startsWith("[HUD]")) {
    if (subtitleTypeInterval) {
      clearInterval(subtitleTypeInterval);
      subtitleTypeInterval = null;
    }
    if (subtitleTimer) {
      clearTimeout(subtitleTimer);
      subtitleTimer = null;
    }
    container.style.display = "block";
    metaEl.textContent = "COMPILING_SKILL_MATRIX...";
    metaEl.style.color = "#ffaa00"; // Orange néon
    
    // Style type console / terminal
    if (textEl) {
      textEl.style.display = "block";
      textEl.style.textAlign = "left";
      textEl.style.whiteSpace = "pre-wrap";
      textEl.style.fontSize = "11px";
      textEl.style.lineHeight = "1.5";
      textEl.style.maxHeight = "120px";
      textEl.style.overflowY = "hidden";
      textEl.style.fontFamily = "'Courier New', monospace";
    }
    
    const cleanText = text.replace("[HUD] ", "").replace("[HUD]", "");
    
    // Réinitialiser les logs au début du processus
    if (cleanText.includes("COMPILING NEW SKILL") || cleanText.includes("SYSTEM: ALLOCATING")) {
            hudLogs = [];
    }
    
    // Filtrer les codes de couleur console ANSI éventuels
    const filteredText = cleanText.replace(/\u001b\[\d+m/g, '').replace(/\[0m/g, '').replace(/\[9\dm/g, '');
    
    if (filteredText.trim()) {
      hudLogs.push(filteredText);
      // Garder au maximum les 6 dernières lignes de logs à l'écran
      if (hudLogs.length > 6) {
        hudLogs.shift();
      }
    }
    
    if (textEl) {
      textEl.textContent = hudLogs.join("\n");
    }
    return;
  }

  // Restauration du style d'origine pour les sous-titres ordinaires de Jarvis
  if (textEl) {
    textEl.style.display = "inline";
    textEl.style.textAlign = "center";
    textEl.style.whiteSpace = "normal";
    textEl.style.fontSize = "18px";
    textEl.style.lineHeight = "1.4";
  }
  hudLogs = []; // Vider la console

  // Clear any existing animation
  if (subtitleTimer) clearTimeout(subtitleTimer);
  if (subtitleTypeInterval) clearInterval(subtitleTypeInterval);

  if (!subtitlesEnabled || text === "") {
    container.style.display = "none";
    return;
  }
  
  container.style.display = "block";
  textEl.textContent = "";
  metaEl.textContent = "DECRYPTING_RESPONSE...";
  metaEl.style.color = "rgba(0, 229, 255, 0.4)";

  let i = 0;
  // Faster for long text (news), slower for short phrases
  const speed = text.length > 100 ? 15 : 25;

  subtitleTypeInterval = window.setInterval(() => {
    if (i < text.length) {
      // Add a bit of "glitch" feel by sometimes adding random chars before the real one
      textEl.textContent += text.charAt(i);
      i++;

      // Auto-scroll if it's long? (The box is fixed width/max-width)
    } else {
      if (subtitleTypeInterval) clearInterval(subtitleTypeInterval);
      metaEl.textContent = "DECRYPTION_COMPLETE [STABLE]";
      metaEl.style.color = "#22c55e";

      // Hide after a delay proportional to text length
      const delay = Math.max(3000, text.length * 50);
      subtitleTimer = window.setTimeout(() => {
        container.style.display = "none";
      }, delay);
    }
  }, speed);
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_INTERVAL_MS);
}

// ── Events ──────────────────────────────────────────────────────────────────
// ── Unified Menu Event Listeners ─────────────────────────────────────────────
// ⚠ Ce bloc était intégralement enveloppé dans « if (jarvisMenuBtn && jarvisMenuDropdown) ».
// Or #jarvis-menu-btn / #jarvis-menu-dropdown n'existent PLUS dans index.html :
// la condition était donc toujours fausse et TOUT ce qui suit (≈260 lignes) était
// du code mort — dont le bouton SAUVEGARDER de la modale des clés API, qui n'avait
// aucun écouteur et ne faisait donc jamais rien.
// Le câblage propre au menu reste conditionné ; le reste s'exécute maintenant.
{
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
        if (id === "menu-settings-btn" || id === "shopping-toggle-btn" || id === "menu-uninstaller-toggle-btn" || id === "winget-toggle-btn" || id === "menu-holo-btn" || id === "menu-ha-toggle-btn" || id === "browser-btn" || id === "menu-keyboard-toggle" || id === "clear-cache-btn" || id === "api-keys-button" || id === "menu-av-scan-btn" || id === "menu-av-live-btn") {
          jarvisMenuDropdown.classList.add("hidden");
          jarvisMenuBtn.classList.remove("active");
        }
      });
    });
  }
    // Liaison des clics du menu unifié vers les boutons jumeaux originaux (évite les doublons d'IDs)
  const menuGpuBtn = document.getElementById("menu-gpu-btn");
  if (menuGpuBtn && gpuButtonEl) {
    menuGpuBtn.addEventListener("click", () => gpuButtonEl.click());
  }

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
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "ha_get_states" }));
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
      if (keyboardEnabled && keyboardToggleButtonEl && keyboardHudEl) {
        keyboardEnabled = false;
        keyboardToggleButtonEl.setAttribute("aria-pressed", "false");
        keyboardHudEl.style.display = "none";
      }

      // Ouvrir directement le modal paramètres
      if (settingsModalEl) {
        settingsModalEl.classList.add("visible");
      }
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "get_settings" }));
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

      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
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


// (Écouteur de #mute-button retiré ici : un second, plus complet, existe plus bas
//  dans le fichier. Les deux étant actifs, un clic envoyait « stop_audio » DEUX
//  fois et forçait l'orbe en « idle » sans attendre la confirmation du backend.)

// NOTE : les écouteurs "click" directs de #gpu-button et #subtitle-toggle ont été
// supprimés. Ces boutons vivent dans le carrousel, dont le gestionnaire délégué
// exécute déjà leur action via _carouselActions. Garder les deux faisait basculer
// l'état DEUX fois par clic → le bouton semblait ne rien faire.
// Voir bindCarouselAction("gpu-button") / ("subtitle-toggle") plus bas.

keyboardToggleButtonEl.addEventListener("click", () => {
  keyboardEnabled = !keyboardEnabled;
  keyboardToggleButtonEl.setAttribute("aria-pressed", keyboardEnabled.toString());
  keyboardHudEl.style.display = keyboardEnabled ? "block" : "none";

  if (keyboardEnabled) {
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
    if (val && ws && ws.readyState === WebSocket.OPEN) {
      const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
      const targetDir = folderInput?.value.trim() || undefined;
      ws.send(JSON.stringify({ type: "user_input", text: val, target_dir: targetDir }));
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
document.querySelectorAll<HTMLButtonElement>(".settings-nav-item").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.panel) switchSettingsTab(btn.dataset.panel);
  });
});

function openSettingsModal(tab?: string) {
  if (!settingsModalEl) return;

  // Fermer le clavier visuel pour éviter la superposition
  if (keyboardEnabled) {
    keyboardEnabled = false;
    keyboardToggleButtonEl?.setAttribute("aria-pressed", "false");
    if (keyboardHudEl) keyboardHudEl.style.display = "none";
  }

  ["display", "opacity", "visibility"].forEach(p => settingsModalEl.style.removeProperty(p));
  settingsModalEl.classList.remove("hidden");
  settingsModalEl.classList.add("visible");
  switchSettingsTab(tab || "profil");

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "get_settings" }));
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

function closeSettingsModal() {
  if (!settingsModalEl) return;
  settingsModalEl.classList.remove("visible");
  // On purge tout style inline hérité : sans cela un display:flex résiduel
  // maintiendrait la modale affichée malgré le retrait de .visible.
  ["display", "opacity", "visibility"].forEach(p => settingsModalEl.style.removeProperty(p));
}

// (Pas d'écouteur direct sur #settings-button : il est dans le carrousel, dont le
//  dispatcher appelle l'action — en avoir deux annulait le clic.)

settingsCloseBtn?.addEventListener("click", closeSettingsModal);
swarmLoungeClose?.addEventListener("click", () => {
  swarmLoungeHud?.classList.add("hidden");
  if (swarmLoungeHud) swarmLoungeHud.style.display = "none";
});

// ── Hologramme mode toggle ────────────────────────────────────────────────────
let _holoActive = false;
const _holoOverlay = document.getElementById("holo-overlay") as HTMLDivElement;

function _openHolo() {
  _holoActive = true;
  if (_holoOverlay) _holoOverlay.style.display = "block";
  if (holoButtonEl) holoButtonEl.setAttribute("aria-pressed", "true");
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) orbCanvas.style.display = "none";
  hideCarouselArrow();
  activerHolo();
}
(window as any)._openHolo = _openHolo;

function _closeHolo() {
  _holoActive = false;
  desactiverHolo();
  if (_holoOverlay) _holoOverlay.style.display = "none";
  if (holoButtonEl) holoButtonEl.setAttribute("aria-pressed", "false");
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) orbCanvas.style.display = "block";
  showCarouselArrow();
}
(window as any)._closeHolo = _closeHolo;

// Écouteur direct de #holo-button supprimé : doublon du dispatcher du carrousel
// (double bascule par clic → ouverture/fermeture immédiate, donc « ne marche pas »).
document.getElementById("holo-close-btn")?.addEventListener("click", _closeHolo);
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
    appDetectBtn.textContent = "🔍 SCAN...";
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "detect_apps" }));
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
  
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "update_settings", settings }));
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
          eye.textContent = "🙈";
        } else {
          input.type = "password";
          eye.textContent = "👁️";
        }
      }
    }
  });
});

// ── Boot Sequence ─────────────────────────────────────────────────────────────
// Fait tourner en vraie 3D la sphère de points au centre de l'orbe (chaque
// point a ses coordonnées x/y/z d'origine en attributs data-*, générées une
// fois par script et figées dans le HTML). Rotation autour de l'axe Y :
// projection 2D + taille/opacité selon la profondeur (effet de volume).
function initBootOrbSphere(): void {
  const dots = Array.from(document.querySelectorAll<SVGCircleElement>(".boot-orb-dot"));
  if (!dots.length) return;

  const points = dots.map((el) => ({
    el,
    x: parseFloat(el.dataset.x || "0"),
    y: parseFloat(el.dataset.y || "0"),
    z: parseFloat(el.dataset.z || "0"),
  }));

  const R = 26;
  const CX = 100, CY = 100;
  let angle = 0;

  // setInterval plutôt que requestAnimationFrame : un écran de démarrage doit
  // continuer de tourner même si la fenêtre perd le focus ou est masquée un
  // instant (rAF est mis en pause par le navigateur dans un onglet/fenêtre
  // en arrière-plan, ce qui gèlerait la sphère au pire moment).
  const intervalId = window.setInterval(() => {
    angle += 0.02;
    const cosA = Math.cos(angle), sinA = Math.sin(angle);
    for (const p of points) {
      const x = p.x * cosA - p.z * sinA;
      const z = p.x * sinA + p.z * cosA;
      const depth = (z + 1) / 2; // 0 = derriere, 1 = devant
      p.el.setAttribute("cx", (CX + x * R).toFixed(2));
      p.el.setAttribute("cy", (CY + p.y * R).toFixed(2));
      p.el.setAttribute("r", (0.5 + depth * 1.2).toFixed(2));
      p.el.style.opacity = (0.35 + depth * 0.65).toFixed(2);
    }
  }, 33);
  bootOrbSphereStop = () => window.clearInterval(intervalId);
}

function runBootSequence(): void {
  const overlay     = document.getElementById("boot-overlay") as HTMLDivElement;
  const logoSection = document.getElementById("boot-logo-section") as HTMLDivElement;
  const statusText  = document.getElementById("boot-status-text") as HTMLDivElement;
  const buildYear   = document.getElementById("boot-build-year") as HTMLSpanElement;

  if (!overlay) return;
  if (buildYear) buildYear.textContent = new Date().getFullYear().toString();

  // Durée d'affichage minimale : évite un flash désagréable si la connexion
  // WebSocket (souvent locale, quasi instantanée) répond avant même que le
  // logo ait fini son fondu d'entrée.
  const MIN_DISPLAY_MS = 1200;
  const bootStart = performance.now();

  function finishBoot() {
    const elapsed = performance.now() - bootStart;
    const wait = Math.max(0, MIN_DISPLAY_MS - elapsed);
    setTimeout(() => {
      // Le noyau du réacteur passe du cyan pulsant au vert stable : c'est
      // l'indicateur de progression, plus de barre séparée à animer.
      logoSection.classList.add("online");
      statusText.textContent = "SYSTÈMES OPÉRATIONNELS";

      setTimeout(() => {
        // Retirer la protection anti-FOUC pour révéler l'interface
        document.body.classList.remove("loading");
        overlay.style.opacity = "0";
        setTimeout(() => { overlay.style.display = "none"; bootOrbSphereStop?.(); }, 900);
      }, 1100);
    }, wait);
  }

  statusText.textContent = "CONNEXION AU SERVEUR EN COURS...";

  if (wsConnectedBeforeBoot) {
    finishBoot();
  } else {
    bootConnectedCallback = finishBoot;
    // Sécurité : ferme le boot après 25 s si le serveur ne répond pas
    setTimeout(() => {
      if (bootConnectedCallback) {
        bootConnectedCallback = null;
        statusText.textContent = "CONNEXION INDISPONIBLE — POURSUITE HORS-LIGNE";
        document.body.classList.remove("loading");
        overlay.style.opacity = "0";
        setTimeout(() => { overlay.style.display = "none"; bootOrbSphereStop?.(); }, 900);
      }
    }, 25_000);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
setConnected(false);
applyState("idle");
setMuted(false);
injectVisionButton();
initJarvisGlobe();
initHandTracking();
initHADashboard(ws);
initDynamicAmbientGlow();
initMagneticButtons();
initBootOrbSphere();
runBootSequence();

// ── Carrousel de conseils (extrait dans ui/tips.ts) ──
initDynamicUserTips();
// ── Help HUD Logic ───────────────────────────────────────────────────────────
// Handle du masquage automatique de la liste des commandes (voir showHelpHUD)
let helpAutoHideTimer: number | null = null;

function hideHelpHUD() {
  if (!helpOverlayEl) return;
  if (helpAutoHideTimer !== null) {
    clearTimeout(helpAutoHideTimer);
    helpAutoHideTimer = null;
  }
  // On pilote la classe : le CSS #help-overlay.visible porte un display !important
  // qu'un simple style.display = "none" inline ne peut pas battre.
  helpOverlayEl.classList.remove("visible");
  helpOverlayEl.classList.add("hidden");
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
}

function showHelpHUD() {
  if (!helpOverlayEl) return;
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
  helpOverlayEl.classList.remove("hidden");
  helpOverlayEl.classList.add("visible");
  helpOverlayEl.innerHTML = "";
    // Select 16 random commands (8 on each side) to keep them visible within the viewport
  const shuffled = [...HELP_COMMANDS].sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, 16);

  selected.forEach((cmd, i) => {
    const isRight = i % 2 === 1;
    const widget = document.createElement("div");
    widget.className = `help-widget ${isRight ? 'right' : ''}`;

    // Grid-like positioning with absolute geometric alignment (no overlap)
    const row = Math.floor(i / 2);
    const top = 120 + (row * 84);
    widget.style.top = `${top}px`;

    // Position them on the left or right side with identical margins
    const sideOffset = 45;
    if (isRight) widget.style.right = `${sideOffset}px`;
    else widget.style.left = `${sideOffset}px`;

    // Cinematic reveal delay (shorter timeout for faster entrance)
    widget.style.transitionDelay = `${(i % 5) * 0.15}s`;

    widget.innerHTML = `
      <div class="help-widget-title" style="display:flex; justify-content: space-between;">
        <span>CAPACITÉ ${Math.floor(Math.random() * 999)}</span>
        <span style="opacity:0.3">[SYNC]</span>
      </div>
      <div class="help-widget-cmd">"${cmd}"</div>
    `;

    helpOverlayEl.appendChild(widget);

    // Cinematic reveal (set transition visible immediately or on next tick)
    requestAnimationFrame(() => {
      setTimeout(() => widget.classList.add("visible"), 50);
    });
  });

  // Masquage automatique au bout de 20 s.
  // Le handle est mémorisé et annulé à chaque ouverture/fermeture : sans cela,
  // ouvrir puis refermer puis rouvrir la liste faisait survivre le timer du
  // PREMIER clic, qui refermait 20 s plus tard l'overlay fraîchement rouvert.
  if (helpAutoHideTimer !== null) clearTimeout(helpAutoHideTimer);
  helpAutoHideTimer = window.setTimeout(() => {
    const widgets = document.querySelectorAll(".help-widget");
    widgets.forEach((w, i) => {
      setTimeout(() => w.classList.remove("visible"), i * 100);
    });
    helpAutoHideTimer = window.setTimeout(() => hideHelpHUD(), 2000);
  }, 20000);
}

// ── Timer Logic ─────────────────────────────────────────────────────────────
function startTimer(duration: number) {
  stopTimer();
  timerSeconds = duration;
  timerTotalSeconds = duration;
  timerHudEl.style.display = "block";
  updateTimerDisplay();

  timerInterval = window.setInterval(() => {
    timerSeconds--;
    updateTimerDisplay();
    if (timerSeconds <= 0) {
      timerDisplayEl.textContent = "FINISH";
      timerDisplayEl.style.color = "#ff3d00";
      setTimeout(() => stopTimer(), 3000);
    }
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval);
    timerInterval = null;
  }
  timerHudEl.style.display = "none";
}

function addTimer(extraSeconds: number) {
  timerSeconds += extraSeconds;
  timerTotalSeconds += extraSeconds;
  updateTimerDisplay();
}

function removeTimer(lessSeconds: number) {
  timerSeconds = Math.max(0, timerSeconds - lessSeconds);
  updateTimerDisplay();
}

function updateTimerDisplay() {
  const mins = Math.floor(timerSeconds / 60);
  const secs = timerSeconds % 60;
  timerDisplayEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

  const progress = ((timerTotalSeconds - timerSeconds) / timerTotalSeconds) * 100;
  timerProgressEl.style.width = `${progress}%`;

  // Flash effect if near end
  if (timerSeconds <= 10) {
    timerDisplayEl.style.color = (timerSeconds % 2 === 0) ? "#ff3d00" : "#00e5ff";
  } else {
    timerDisplayEl.style.color = "#00e5ff";
  }
}

connect();

// ── Clock Logic ─────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString('fr-FR', { hour12: false });

  // Globe overlay clock (existing)
  const clockEl = document.getElementById("globe-clock");
  if (clockEl) clockEl.textContent = timeStr;

  // Orb HUD clock (top of screen, always visible)
  const orbTime = document.getElementById("orb-time-display");
  if (orbTime) orbTime.textContent = timeStr;

  const orbDate = document.getElementById("orb-date-display");
  if (orbDate) {
    orbDate.textContent = now.toLocaleDateString('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric'
    });
  }
}
setInterval(updateClock, 1000);
updateClock();
// Silence unused-import warning for showError
void showError;

// ── Temp Panel (left side — Home Assistant interior) ────────────────────────

const TEMP_DURATION_MS = 3 * 60 * 1000; // 3 minutes

// Comfort scale: 10°C → 30°C maps to 0% → 100%
function tempToPercent(t: number): number {
  return Math.min(100, Math.max(0, ((t - 10) / 20) * 100));
}

let _tpTimer: ReturnType<typeof setInterval> | null = null;
let _tpHideTimer: ReturnType<typeof setTimeout> | null = null;
let _tpEndTime = 0;

function showTempPanel(d: {
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

document.getElementById("tp-close-btn")?.addEventListener("click", hideTempPanel);

// ── Weather Panel ────────────────────────────────────────────────────────────

const WEATHER_DURATION_MS = 2 * 60 * 1000; // 2 minutes
const WEATHER_ICONS: Record<number, string> = {
  0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
  45: "🌫", 48: "🌫",
  51: "🌦", 53: "🌦", 55: "🌧",
  61: "🌧", 63: "🌧", 65: "🌧",
  71: "🌨", 73: "🌨", 75: "❄️", 77: "🌨",
  80: "🌦", 81: "🌦", 82: "⛈",
  85: "🌨", 86: "❄️",
  95: "⛈", 96: "⛈", 99: "⛈",
};

let _wpTimer: ReturnType<typeof setInterval> | null = null;
let _wpHideTimer: ReturnType<typeof setTimeout> | null = null;
let _wpEndTime = 0;

function showWeatherPanel(d: {
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
  (document.getElementById("wp-icon") as HTMLElement).textContent = WEATHER_ICONS[d.code] ?? "🌡";

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

document.getElementById("wp-close-btn")?.addEventListener("click", hideWeatherPanel);

// ── Recipe Modal Logic ───────────────────────────────────────────────────────

const recipeModal = document.getElementById("recipe-modal");
const closeRecipeBtn = document.getElementById("close-recipe");
const recipeHeader = document.getElementById("recipe-header");

if (closeRecipeBtn && recipeModal) {
  closeRecipeBtn.addEventListener("click", () => {
    recipeModal.classList.add("hidden");
  });
}
// Drag & Drop for Recipe Modal
if (recipeModal && recipeHeader) {
  let isDragging = false;
  let offsetX = 0;
  let offsetY = 0;

  recipeHeader.addEventListener("mousedown", (e) => {
    isDragging = true;
    const rect = recipeModal.getBoundingClientRect();
    offsetX = e.clientX - rect.left;
    offsetY = e.clientY - rect.top;
    recipeModal.style.cursor = "grabbing";
  });

  document.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    
    // Prevent dragging outside the window
    let newX = e.clientX - offsetX;
    let newY = e.clientY - offsetY;
    
    // Boundaries
    const maxX = window.innerWidth - recipeModal.offsetWidth;
    const maxY = window.innerHeight - recipeModal.offsetHeight;
    
    newX = Math.max(0, Math.min(newX, maxX));
    newY = Math.max(0, Math.min(newY, maxY));

    recipeModal.style.left = `${newX}px`;
    recipeModal.style.top = `${newY}px`;
    recipeModal.style.transform = "none"; // disable original translation for dragging
  });

  document.addEventListener("mouseup", () => {
    if (isDragging) {
      isDragging = false;
      recipeModal.style.cursor = "default";
    }
  });
}
// ── Image HUD Logic ──────────────────────────────────────────────────────────
// (showImageHUD extrait dans panels/image_panels.ts)

// ── Control Buttons Events ───────────────────────────────────────────────────
document.getElementById("fullscreen-btn")?.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "toggle_fullscreen" }));
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

// mute-button = Stopper JARVIS (interrompre la parole)
muteButtonEl?.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "stop_audio" }));
  }
  // Flash visuel rapide
  muteButtonEl.style.boxShadow = "0 0 25px rgba(0, 229, 255, 0.8)";
  setTimeout(() => { muteButtonEl.style.boxShadow = ""; }, 400);
});

// mic-btn = Couper/réactiver le microphone
micBtnEl?.addEventListener("click", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "toggle_mic" }));
  }
  // Feedback visuel optimiste (l'état réel sera confirmé par mic_state)
  const isMuted = micBtnEl.classList.contains("is-muted");
  setMuted(!isMuted);
});



setTimeout(() => initWidgets(ws), 2000);

// ── Drag & Drop souris pour les widgets HUD (extrait dans ui/draggable.ts) ──
// Appliquer le drag à tous les widgets HUD au chargement (ils existent dans le DOM même si cachés)
["calendar-hud", "weather-hud", "music-hud", "dev-swarm-hud", "website-builder-hud", "swarm-lounge-hud"].forEach(id => {
  const el = document.getElementById(id);
  if (el) makeDraggable(el);
});

// ── Dock carrousel (extrait dans ui/carousel.ts) ──
initCarouselDock();
// (Panneau antivirus extrait dans panels/antivirus_panel.ts)

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

// (Modal info antivirus extrait dans panels/antivirus_panel.ts)

// (Listeners désinstallateur extraits dans panels/uninstaller_panel.ts)

// (Panneau courses extrait dans panels/shopping_panel.ts)

// ── LOGIQUE DU DASHBOARD DOMOTIQUE HOME ASSISTANT ────────────────────────────
haToggleBtn?.addEventListener("click", () => {
  if (!haPanel) return;
  const isHidden = haPanel.classList.contains("hidden");
  if (isHidden) {
    haPanel.classList.remove("hidden");
    haToggleBtn.setAttribute("aria-pressed", "true");
    haToggleBtn.classList.add("active");
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ha_get_states" }));
    }
  } else {
    haPanel.classList.add("hidden");
    haToggleBtn.setAttribute("aria-pressed", "false");
    haToggleBtn.classList.remove("active");
  }
});


// (Panneaux images extraits dans panels/image_panels.ts)

// (Désinstallateur extrait dans panels/uninstaller_panel.ts)

// (Panneau winget extrait dans panels/winget_panel.ts)

// ══ NAVIGATEUR SÉCURISÉ CONTRÔLES & ÉVÉNEMENTS ══
(window as any).updateBrowserUIState = (state: string) => {
  const browserControls = document.getElementById("hud-browser-controls");
  const dockBtn = document.getElementById("hud-browser-dock-btn");
  if (state === "docked") {
    document.body.classList.add("browser-open");
    if (browserControls) browserControls.classList.remove("hidden");
    if (dockBtn) dockBtn.innerText = "⚡ DÉTACHER";
  } else if (state === "undocked") {
    document.body.classList.remove("browser-open");
    if (browserControls) browserControls.classList.remove("hidden");
    if (dockBtn) dockBtn.innerText = "🔗 ANCRER";
  } else if (state === "closed") {
    document.body.classList.remove("browser-open");
    if (browserControls) browserControls.classList.add("hidden");
  }
};

const browserBtnEl = document.getElementById("browser-btn") as HTMLButtonElement;
if (browserBtnEl) {
  browserBtnEl.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "open_browser" }));
    }
  });
}

const hudBrowserDockBtn = document.getElementById("hud-browser-dock-btn") as HTMLButtonElement;
const hudBrowserCloseBtn = document.getElementById("hud-browser-close-btn") as HTMLButtonElement;

if (hudBrowserDockBtn) {
  hudBrowserDockBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (document.body.classList.contains("browser-open")) {
        ws.send(JSON.stringify({ type: "undock_browser" }));
      } else {
        ws.send(JSON.stringify({ type: "dock_browser" }));
      }
    }
  });
}
if (hudBrowserCloseBtn) {
  hudBrowserCloseBtn.addEventListener("click", () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "close_browser" }));
    }
  });
}

// (Effets ambiants extraits dans ui/effects.ts)

// ── BINDINGS D'ÉVÉNEMENTS POUR LE DOCK CAROUSEL OPERATIONAL ──
(window as any)._carouselActions = (window as any)._carouselActions || {};

const bindCarouselAction = (btnId: string, actionFn: (btn: HTMLElement) => void) => {
  (window as any)._carouselActions[btnId] = actionFn;
};

// 0. Vision Button
bindCarouselAction("vision-button", (btn) => {
  toggleVision(btn);
});

// 1. GPU Boost
bindCarouselAction("gpu-button", (btn) => {
  const isPressed = btn.getAttribute("aria-pressed") === "true";
  const newState = !isPressed;
  // .active est réservée au bouton centré du carrousel → on passe par l'état
  // « allumé » (aria-pressed + .is-toggled-on), sinon renderCarousel l'écrase.
  setCarouselBtnState(btn, newState);
  if (newState) {
    orb.setQuality("high");
    console.log("GPU Acceleration Enabled");
  } else {
    orb.setQuality("low");
    console.log("GPU Acceleration Disabled");
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "toggle_gpu", enabled: newState }));
  }
});

// 2. Hologramme
bindCarouselAction("holo-button", (btn) => {
  if (_holoActive) {
    _closeHolo();
    setCarouselBtnState(btn, false);
  } else {
    _openHolo();
    setCarouselBtnState(btn, true);
  }
});

// 3. HUD Text Subtitles
bindCarouselAction("subtitle-toggle", (btn) => {
  subtitlesEnabled = !subtitlesEnabled;
  setCarouselBtnState(btn, subtitlesEnabled);
  btn.innerHTML = subtitlesEnabled ? '<span class="btn-icon">💬</span> HUD TEXT' : '<span class="btn-icon">💬</span> TEXT OFF';
  const subHud = document.getElementById("subtitle-hud");
  if (subHud && !subtitlesEnabled) {
    // On masque à la désactivation. À l'activation on NE force PAS l'affichage :
    // showSubtitles() ouvrira la boîte quand JARVIS aura réellement du texte à
    // afficher — sinon on laissait un cadre vide impossible à faire disparaître.
    subHud.style.display = "none";
  }
});

// 4. Mode AR Gestures
bindCarouselAction("gestures-toggle", async (btn) => {
  const isPressed = btn.getAttribute("aria-pressed") === "true";
  const newState = !isPressed;
  (btn as HTMLButtonElement).disabled = true;
  btn.innerHTML = newState ? '<span class="btn-icon">⏳</span> CHARGEMENT...' : '<span class="btn-icon">🖐️</span> MODE AR';
  const active = await toggleHandTracking(newState);
  (btn as HTMLButtonElement).disabled = false;
  setCarouselBtnState(btn, active);
  btn.classList.toggle("ar-active", active);
  btn.innerHTML = active ? '<span class="btn-icon">🖐️</span> AR ACTIF' : '<span class="btn-icon">🖐️</span> MODE AR';
});

// ── État visuel des boutons du carrousel ──────────────────────────────────────
// N.B. : on n'utilise PAS la classe .active ici — elle est réservée au bouton
// centré par renderCarousel(). L'état « allumé » passe par aria-pressed +
// .is-toggled-on, que le CSS du carrousel sait déjà styler.
function setCarouselBtnState(btnOrId: HTMLElement | string, on: boolean): void {
  const b = typeof btnOrId === "string" ? document.getElementById(btnOrId) : btnOrId;
  if (!b) return;
  b.setAttribute("aria-pressed", String(on));
  b.classList.toggle("is-toggled-on", on);
}

// Helper d'ouverture/fermeture d'un panneau HUD.
// IMPORTANT : on ne pilote QUE les classes .hidden/.visible, qui sont le contrat
// des feuilles de style (.xxx-panel.hidden { display:none !important }).
// Poser des styles inline !important ici (comme le faisait la version
// précédente) les laissait collés sur l'élément après fermeture : tous les
// autres chemins d'ouverture (commande vocale, menu déroulant, message
// WebSocket) remettaient bien les bonnes classes mais le panneau restait
// invisible, car le display:none inline gagnait sur le CSS.
function toggleHudPanel(panelId: string, btn: HTMLElement, onOpen?: () => void, onClose?: () => void): boolean {
  const p = document.getElementById(panelId);
  if (!p) {
    console.warn(`[CAROUSEL] Panneau introuvable : #${panelId}`);
    return false;
  }

  // Purge des styles inline hérités qui écraseraient le CSS
  ["display", "opacity", "visibility", "z-index"].forEach(prop => p.style.removeProperty(prop));

  const estOuvert = !p.classList.contains("hidden");

  if (estOuvert) {
    p.classList.add("hidden");
    p.classList.remove("visible");
    setCarouselBtnState(btn, false);
    if (onClose) onClose();
    return false;
  }

  p.classList.remove("hidden");
  p.classList.add("visible");
  setCarouselBtnState(btn, true);
  if (onOpen) onOpen();
  return true;
}

// 6. Désinstallateur
bindCarouselAction("carousel-uninstaller-btn", (btn) => {
  const panneau = document.getElementById("uninstaller-panel");
  const estOuvert = panneau ? !panneau.classList.contains("hidden") : false;
  if (estOuvert) {
    closeUninstallerPanel();
    setCarouselBtnState(btn, false);
  } else {
    openUninstallerPanel();
    setCarouselBtnState(btn, true);
    setCarouselBtnState("carousel-winget-btn", false); // openUninstallerPanel ferme l'autre
  }
});

// 7. Winget / Mises à jour
// Le panneau réel est #winget-panel (l'ancien code ciblait #winget-logs-panel,
// qui n'existe pas → le bouton ne faisait rien). On réutilise les fonctions du
// module, qui gèrent aussi la requête des mises à jour et le bouton du menu.
bindCarouselAction("carousel-winget-btn", (btn) => {
  const panneau = document.getElementById("winget-panel");
  const estOuvert = panneau ? !panneau.classList.contains("hidden") : false;
  if (estOuvert) {
    closeWingetPanel();
    setCarouselBtnState(btn, false);
  } else {
    openWingetPanel();
    setCarouselBtnState(btn, true);
    setCarouselBtnState("carousel-uninstaller-btn", false); // openWingetPanel ferme l'autre
  }
});

// 8. Antivirus Scan
// openAntivirusPanel() affiche le panneau ET envoie av_scan_start (le type
// attendu par le backend ; l'ancien code envoyait start_av_scan, jamais traité).
bindCarouselAction("carousel-av-scan-btn", (btn) => {
  const panneau = document.getElementById("av-panel");
  // On teste « .visible » et non « !.hidden » : la fermeture est animée sur
  // 400 ms, pendant lesquelles le panneau ne porte NI l'une NI l'autre classe.
  // Avec !.hidden, un clic dans cette fenêtre était interprété comme « c'est
  // ouvert, referme » — le panneau ne se rouvrait donc jamais.
  const estOuvert = panneau ? panneau.classList.contains("visible") : false;
  if (estOuvert) {
    closeAntivirusPanel();
    setCarouselBtnState(btn, false);
  } else {
    openAntivirusPanel();
    setCarouselBtnState(btn, true);
  }
});

// 9. Domotique (Home Assistant)
bindCarouselAction("carousel-ha-btn", (btn) => {
  toggleHudPanel("ha-panel", btn as HTMLElement, () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ha_get_states" }));
    }
  });
});

// 9.5. Application Mobile Smartphone
bindCarouselAction("carousel-mobile-btn", (btn) => {
  toggleHudPanel("mobile-info-modal", btn as HTMLElement, () => {
    const urlDisplay = document.getElementById("mobile-url-display");
    const host = window.location.hostname || "localhost";
    if (urlDisplay) {
      urlDisplay.textContent = `http://${host}:8080`;
    }
  });
});



// 10. Navigateur Sécurisé
bindCarouselAction("carousel-browser-btn", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "open_browser" }));
  }
});

// 11. Liste des commandes (Toggle ON/OFF)
bindCarouselAction("carousel-commands-btn", () => {
  if (!helpOverlayEl) return;
  if (helpOverlayEl.classList.contains("visible")) {
    hideHelpHUD();
  } else {
    showHelpHUD();
  }
});

// 12. Clés API — ouvre la page paramètres sur l'onglet Clés API (Toggle ON/OFF)
bindCarouselAction("carousel-api-btn", () => {
  if (settingsModalEl?.classList.contains("visible")
    && document.querySelector('.settings-nav-item[data-panel="api"]')?.classList.contains("active")) {
    closeSettingsModal();
  } else {
    openSettingsModal("api");
  }
});

// 13. Vider Cache
bindCarouselAction("clear-cache-btn", (btn) => {
  // Refermer le menu déroulant s'il est ouvert (le bouton y figure aussi)
  if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
  if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");

  (btn as HTMLButtonElement).disabled = true;
  btn.innerHTML = '<span class="btn-icon">⏳</span> CACHE...';

  const banner = document.getElementById("update-banner");
  if (banner) {
    banner.style.display = "block";
    banner.style.cursor = "default";
    banner.textContent = "⏳ NETTOYAGE DU CACHE EN COURS...";
    banner.style.background = "linear-gradient(90deg, rgba(0,30,80,0.95), rgba(0,100,180,0.85))";
  }

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "clear_cache" }));
  } else {
    setTimeout(() => location.reload(), 1500);
  }
});

// 14. Paramètres Globaux (settings-modal)
bindCarouselAction("settings-button", () => {
  if (settingsModalEl?.classList.contains("visible")) {
    closeSettingsModal();
  } else {
    openSettingsModal();
  }
});

// ── SYNCHRONISATION D'ÉTAT DES BOUTONS DU CARROUSEL ───────────────────────────
// Un panneau peut s'ouvrir/se fermer par bien d'autres chemins que le carrousel :
// commande vocale, menu déroulant, message WebSocket, bouton ✕ interne...
// Sans cela, le bouton du dock affichait un état mensonger (allumé alors que le
// panneau est fermé, et inversement) et il fallait cliquer deux fois pour
// retrouver la cohérence. On observe donc la classe .hidden des panneaux — seule
// source de vérité — et on aligne le bouton correspondant.
const CAROUSEL_PANEL_MAP: Record<string, string[]> = {
  "uninstaller-panel": ["carousel-uninstaller-btn"],
  "winget-panel":      ["carousel-winget-btn"],
  "ha-panel":          ["carousel-ha-btn"],
  "mobile-info-modal": ["carousel-mobile-btn"],
  "av-panel":          ["carousel-av-scan-btn"],
  "help-overlay":      ["carousel-commands-btn"],
  // La page paramètres unifiée a deux points d'entrée (bouton haut + dock) : les deux
  // doivent refléter son état ouvert/fermé.
  "settings-modal":    ["settings-button", "carousel-api-btn"],
};

Object.entries(CAROUSEL_PANEL_MAP).forEach(([panelId, btnIds]) => {
  const panneau = document.getElementById(panelId);
  if (!panneau) return;

  const synchroniser = () => {
    const ouvert = !panneau.classList.contains("hidden")
                && panneau.style.display !== "none"
                && getComputedStyle(panneau).display !== "none";
    btnIds.forEach(btnId => setCarouselBtnState(btnId, ouvert));
    refreshCarousel();
  };

  new MutationObserver(synchroniser).observe(panneau, {
    attributes: true,
    attributeFilter: ["class", "style"],
  });

  synchroniser(); // état initial
});

// ── VOICE VAULT UI LOGIC ──────────────────────────────────────────────────────
function updateVoiceVaultUI(data: any) {
  const panel = document.getElementById("vault-panel");
  const lockedScreen = document.getElementById("vault-locked-screen");
  const unlockedScreen = document.getElementById("vault-unlocked-screen");
  const errorMsg = document.getElementById("vault-error-msg");
  const filesList = document.getElementById("vault-files-list");

  if (data.force_open_hud && panel) {
    panel.classList.remove("hidden");
    panel.classList.add("visible");
    panel.style.setProperty("display", "flex", "important");
  }

  if (data.type === "vault_lock_result" && panel) {
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    panel.style.setProperty("display", "none", "important");
  }

  const isUnlocked = data.is_unlocked === true || data.success === true;
  const isConfigured = data.is_configured !== false;
  const lockTitle = document.getElementById("vault-lock-title");
  const unlockBtn = document.getElementById("vault-unlock-btn");

  if (lockTitle) {
    lockTitle.textContent = isConfigured
      ? "ENTREZ VOTRE CODE PIN OU MOT DE PASSE"
      : "INITIALISATION : CRÉEZ VOTRE MOT DE PASSE OU CODE PIN";
  }

  if (unlockBtn) {
    unlockBtn.textContent = isConfigured ? "DÉVERROUILLER" : "CRÉER LE COFFRE";
  }

  if (errorMsg) {
    if (data.type === "vault_unlock_result" && !data.success) {
      errorMsg.textContent = "❌ Mot de passe ou PIN incorrect.";
    } else {
      errorMsg.textContent = "";
    }
  }

  if (isUnlocked) {
    if (lockedScreen) lockedScreen.style.display = "none";
    if (unlockedScreen) unlockedScreen.style.display = "flex";

    if (filesList && data.files) {
      if (data.files.length === 0) {
        filesList.innerHTML = '<div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); text-align: center; padding: 20px;">Aucun fichier dans le coffre-fort.</div>';
      } else {
        filesList.innerHTML = data.files.map((file: any) => `
          <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.15); padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;">
            <div>
              <div style="font-size: 11px; font-weight: bold; color: #fff;">📄 ${file.filename}</div>
              <div style="font-size: 9px; color: rgba(0, 229, 255, 0.6);">${file.size_kb} KB · Crypté AES-256</div>
            </div>
            <div style="display: flex; gap: 6px;">
              <button onclick="window.exportVaultFile('${file.filename}')" style="background: rgba(0, 229, 255, 0.15); border: 1px solid #00e5ff; color: #00e5ff; padding: 4px 8px; border-radius: 4px; font-size: 9px; cursor: pointer;">📥 EXPORTER</button>
              <button onclick="window.deleteVaultFile('${file.filename}')" style="background: rgba(255, 51, 102, 0.15); border: 1px solid #ff3366; color: #ff3366; padding: 4px 8px; border-radius: 4px; font-size: 9px; cursor: pointer;">🗑️</button>
            </div>
          </div>
        `).join('');
      }
    }
  } else {
    if (lockedScreen) lockedScreen.style.display = "flex";
    if (unlockedScreen) unlockedScreen.style.display = "none";
  }
}

(window as any).exportVaultFile = (filename: string) => {
  const wsInst = (window as any)._jarvisWs || (window as any).ws;
  if (wsInst && wsInst.readyState === 1) {
    wsInst.send(JSON.stringify({ type: "vault_export_file", filename }));
    alert(`Fichier "${filename}" déchiffré et exporté vers votre dossier Téléchargements !`);
  }
};

(window as any).deleteVaultFile = (filename: string) => {
  const wsInst = (window as any)._jarvisWs || (window as any).ws;
  if (confirm(`Voulez-vous vraiment supprimer "${filename}" du coffre-fort ?`)) {
    if (wsInst && wsInst.readyState === 1) {
      wsInst.send(JSON.stringify({ type: "vault_delete_file", filename }));
    }
  }
};

// Listeners Vault
setTimeout(() => {
  const unlockBtn = document.getElementById("vault-unlock-btn");
  const lockBtn = document.getElementById("vault-lock-btn");
  const pinInput = document.getElementById("vault-pin-input") as HTMLInputElement | null;
  const addBtn = document.getElementById("vault-add-btn");
  const fileInput = document.getElementById("vault-file-input") as HTMLInputElement | null;

  if (unlockBtn && pinInput) {
    const triggerUnlock = () => {
      const pin = pinInput.value.trim();
      const wsInst = (window as any)._jarvisWs || (window as any).ws;
      if (pin && wsInst && wsInst.readyState === 1) {
        wsInst.send(JSON.stringify({ type: "vault_unlock", password: pin }));
      }
    };
    unlockBtn.onclick = triggerUnlock;
    pinInput.onkeyup = (e) => { if (e.key === "Enter") triggerUnlock(); };
  }

  if (lockBtn) {
    lockBtn.onclick = () => {
      const wsInst = (window as any)._jarvisWs || (window as any).ws;
      if (wsInst && wsInst.readyState === 1) {
        wsInst.send(JSON.stringify({ type: "vault_lock" }));
      }
    };
  }

  if (addBtn && fileInput) {
    addBtn.onclick = () => fileInput.click();
    fileInput.onchange = () => {
      if (fileInput.files && fileInput.files[0]) {
        const filePath = (fileInput.files[0] as any).path || fileInput.files[0].name;
        const wsInst = (window as any)._jarvisWs || (window as any).ws;
        if (wsInst && wsInst.readyState === 1) {
          wsInst.send(JSON.stringify({ type: "vault_add_file", file_path: filePath }));
        }
      }
    };
  }
}, 1000);
