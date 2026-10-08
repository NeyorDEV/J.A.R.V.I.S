import { cardManager } from "../cards";
import { handleHAMessage } from "../ha_dashboard";
import { updateMusicUI, updateWeatherUI } from "../widgets";
import { fermerVues3D, ouvrirVue3D, vue3DOuverte } from "../hud/vues_3d";
import { orb } from "../hud/orb_state";
import { closeConfirmDialog, showConfirmDialog } from "../panels/confirm_dialog";
import { showImageHUD } from "../panels/image_panels";
import { openShoppingPanel, setShoppingList } from "../panels/shopping_panel";
import { type JarvisMessage } from "./message_types";

// Messages backend : vues 3D (échecs, radar réseau, domotique, cortex, explorateur),
// cartes, météo, musique, courses, Home Assistant (extrait du gestionnaire de main.ts).
// Les vues 3D s'ouvrent directement, sans passer par l'ancien mode hologramme.
export function handleVues3DMessage(data: JarvisMessage): boolean {
  // ── Chess Map 3D ──
  if (data.action === "chess_start") {
    ouvrirVue3D("chess");
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

        // « On joue aux échecs » envoie chess_start sans état de partie (le plateau attend
        // alors sa configuration) : handleGameState(undefined) levait une TypeError.
        if (data.state) chess.handleGameState(data.state);
      }
    }, 100);
    return true;
  }

  if (data.action === "chess_reset") {
    const chess = (window as any)._chessMap;
    if (chess) {
      chess.resetGame(true); // reset forcé (sans confirm prompt)
    }
    return true;
  }

  if (data.action === "chess_stop") {
    if (vue3DOuverte("chess")) fermerVues3D();
    return true;
  }

  if (data.action === "chess_game_state") {
    const chess = (window as any)._chessMap;
    if (chess) {
      chess.handleGameState(data.state, (data as any).last_move);
    }
    return true;
  }

  if (data.action === "chess_thinking") {
    const chess = (window as any)._chessMap;
    if (chess) {
      chess.handleThinking((data as any).thinking);
    }
    return true;
  }
        // ── Network Radar 3D ──
  if (data.action === "network_radar_show") {
    ouvrirVue3D("radar");
    const connections = (data as any).connections;
    if (connections) {
      setTimeout(() => {
        const radar = (window as any)._networkRadar;
        if (radar) radar.handleRadarUpdate(connections);
      }, 200);
    }
    return true;
  }
  if (data.action === "network_radar_update") {
    const radar = (window as any)._networkRadar;
    if (radar) radar.handleRadarUpdate((data as any).connections || []);
    return true;
  }
  if (data.action === "network_radar_hide") {
    if (vue3DOuverte("radar")) fermerVues3D();
    return true;
  }
  if (data.action === "blocked_ips") {
    const radar = (window as any)._networkRadar;
    if (radar) radar.handleBlockedIps((data as any).ips || []);
    return true;
  }

  // ── Domotic Map 3D ──

  if (data.action === "domotic_map_update") {
    const domMap = (window as any)._domoticMap;
    if (domMap) domMap.handleServerResponse(data);
    return true;
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
    return true;
  }

  if (data.action === "cortex_search") {
    ouvrirVue3D("cortex");
    setTimeout(() => {
      const cortex = (window as any)._cortexMap;
      if (cortex && typeof (data as any).query === "string") {
        cortex.searchCortex((data as any).query);
      }
    }, 250);
    return true;
  }

  if (data.action === "cortex_vocal_speak_request") {
    const cortex = (window as any)._cortexMap;
    if (cortex) {
      cortex.handleVocalSpeakRequest();
    }
    return true;
  }

  if (data.action === "open_spatial_explorer") {
    ouvrirVue3D("explorer");
    return true;
  }

  if (data.action === "domotic_audio_route_animation") {
    ouvrirVue3D("domotic");
    setTimeout(() => {
      const domMap = (window as any)._domoticMap;
      if (domMap) domMap.handleServerResponse(data);
    }, 250);
    return true;
  }

  if (data.action === "open_domotic_map") {
    ouvrirVue3D("domotic");
    return true;
  }
  if (data.action === "open_cortex") {
    ouvrirVue3D("cortex");
    return true;
  }

  // Fermeture de la vue 3D ouverte (« ferme le cortex », « ferme la vue 3D »...)
  if (data.action === "close_3d_view") {
    fermerVues3D();
    return true;
  }

  if (data.action === "orb_write_word" && (data as any).word) {
    if (orb) {
      orb.writeWord((data as any).word);
    }
    return true;
  }

  if (data.action === "display_image" && data.url) {
    showImageHUD(data.url, data.prompt || "--");
    return true;
  }
  if (data.type === "confirm_request" && (data as any).id) {
    showConfirmDialog((data as any).id, (data as any).message || "Confirmer cette action ?");
    return true;
  }
  if (data.type === "confirm_closed" && (data as any).id) {
    closeConfirmDialog((data as any).id);
    return true;
  }
  if (data.action === "ctx_card") {
    cardManager.showCard({
      title: data.title || "INFORMATION",
      content: data.text || "",
      type: data.type as any,
      duration: data.duration,
      icon: data.icon
    });
    return true;
  }
  if (data.action === "weather_update" && data.weather) {
    updateWeatherUI(data.weather, data.weather_type as 'local' | 'monistrol');
    return true;
          }
  if (data.action === "music_update" && data.data) {
    updateMusicUI(data.data);
    return true;
  }

  // ── Shopping List ────────────────────────────────────────────────────
  if (data.type === "shopping_list" && (data as any).items !== undefined) {
    setShoppingList((data as any).items);
    return true;
  }
  if (data.type === "shopping_open") {
    openShoppingPanel();
    return true;
  }

  // ── Home Assistant WS Messages ──
  if (data.type === "ha_states" || data.type === "ha_state_changed" || data.type === "ha_service_result") {
    handleHAMessage(data);
    return true;
  }
  return false;
}
