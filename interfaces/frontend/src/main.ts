/**
 * J.A.R.V.I.S — Interface Web avec Orbe Three.js
 *
 * Point d'entrée du HUD : n'orchestre plus que le démarrage. La logique vit dans
 *   hud/    — état partagé, orbe, menus, paramètres, clavier, aide, minuteur, carrousel...
 *   ws/     — connexion WebSocket (ws://localhost:8765) et traitement des messages du backend
 *   panels/ — panneaux (atelier de code, confirmation, météo, recette, coffre-fort...)
 *
 * L'ordre des imports (évaluation des modules) et des appels init*() reprend
 * exactement celui de l'ancien main.ts monolithique : ne pas le réordonner.
 */

import "./orb";
import { injectVisionButton } from "./screen_capture";
import { initJarvisGlobe } from "./globe";
import { initWidgets } from "./widgets";
import "./cards";
import "./holo_clock";
import { initHandTracking } from "./hand_tracking";
import "./vues_3d";
import { SpatialFileExplorer } from "./spatial_explorer";
import { DomoticMap } from "./domotic_map";
import { CortexMap } from "./cortex_map";
import { initHADashboard } from "./ha_dashboard";
import { ChessMap } from "./chess_map";
import { NetworkRadar } from "./network_radar";
import { wsRef } from "./ws_link";
import { makeDraggable } from "./ui/draggable";
import { initDynamicUserTips } from "./ui/tips";
import { initDynamicAmbientGlow, initMagneticButtons } from "./ui/effects";
import { initCarouselDock } from "./ui/carousel";
import "./panels/image_panels";
import "./panels/antivirus_panel";
import "./panels/shopping_panel";
import "./panels/uninstaller_panel";
import "./panels/winget_panel";
import "./swarm_lounge";

import "./css/index.css";
import "./widgets.css";
import { initBootOrbSphere, runBootSequence } from "./hud/boot";
import { initCarouselActions } from "./hud/carousel_actions";
import { initControlButtons, initPanelShortcuts } from "./hud/control_buttons";
import { initVues3D } from "./hud/vues_3d";
import { initKeyboard } from "./hud/keyboard";
import { initMenu } from "./hud/menu";
import { applyState, initOrb, setConnected, setMuted } from "./hud/orb_state";
import { initSettingsForm, initSettingsNav } from "./hud/settings";
import { initClock } from "./hud/timer_clock";
import { initSwarmLounge, initWebsiteBuilderHud } from "./panels/code_workshop";
import { initConfirmDialog } from "./panels/confirm_dialog";
import { initRecipePanel } from "./panels/recipe_panel";
import { initVaultPanel } from "./panels/vault_panel";
import { initSystemPanel } from "./panels/system_panel";
import { initWeatherTempPanels } from "./panels/weather_temp_panels";
import { connect } from "./ws/connection";

// Classes des vues 3D exposées pour vues_3d.js (qui les instancie à la demande)
(window as any).SpatialFileExplorer = SpatialFileExplorer;
(window as any).DomoticMap = DomoticMap;
(window as any).CortexMap = CortexMap;
(window as any).ChessMap = ChessMap;
(window as any).NetworkRadar = NetworkRadar;

// ── Initialisation, dans l'ordre exact de l'ancien main.ts monolithique ──────
initSwarmLounge();
initConfirmDialog();
initWebsiteBuilderHud();

// ── Orb ──
initOrb();

initMenu();
initKeyboard();
initSettingsNav();
initVues3D();
initSettingsForm();

// ── Boot ──────────────────────────────────────────────────────────────────────
setConnected(false);
applyState("idle");
setMuted(false);
injectVisionButton();
initJarvisGlobe();
initHandTracking();
initHADashboard(wsRef.current);
initDynamicAmbientGlow();
initMagneticButtons();
initBootOrbSphere();
runBootSequence();

// ── Carrousel de conseils (extrait dans ui/tips.ts) ──
initDynamicUserTips();

connect();
initClock();
initWeatherTempPanels();
initRecipePanel();
initControlButtons();

setTimeout(() => initWidgets(wsRef.current), 2000);

// ── Drag & Drop souris pour les widgets HUD (extrait dans ui/draggable.ts) ──
// Appliquer le drag à tous les widgets HUD au chargement (ils existent dans le DOM même si cachés)
["calendar-hud", "weather-hud", "music-hud", "dev-swarm-hud", "website-builder-hud", "swarm-lounge-hud"].forEach(id => {
  const el = document.getElementById(id);
  if (el) makeDraggable(el);
});

// ── Dock carrousel (extrait dans ui/carousel.ts) ──
initCarouselDock();

initPanelShortcuts();
initCarouselActions();
initVaultPanel();
initSystemPanel();
