import { LiveAudioEngine } from "../live_audio";
import { captureFrame } from "../screen_capture";
import { wsRef } from "../ws_link";
import { createDomActionQueue } from "../hud/dom_automation";
import { applyState, setConnected } from "../hud/orb_state";
import { handleSettingsMessage } from "../hud/settings";
import { hudState } from "../hud/state";
import { handleCodeWorkshopMessage } from "../panels/code_workshop";
import { type JarvisMessage } from "./message_types";
import { handleVues3DMessage } from "./messages_vues3d";
import { handleHudMessage } from "./messages_hud";
import { handleAutopilotMessage, handleSystemMessage } from "./messages_system";

// ── Config ────────────────────────────────────────────────────────────────────
const WS_URL = `ws://${window.location.hostname}:8765`;
const RECONNECT_INTERVAL_MS = 2_000;

// ── WebSocket with auto-reconnect ─────────────────────────────────────────────
let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;


export function connect(): void {
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
    if (hudState.bootConnectedCallback) {
      hudState.bootConnectedCallback();
      hudState.bootConnectedCallback = null;
    } else {
      hudState.wsConnectedBeforeBoot = true;
    }
  });


  const pushDomAction = createDomActionQueue();

  ws.addEventListener("message", async (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data as string) as JarvisMessage;
      // Mêmes branches, dans le même ordre, que l'ancien gestionnaire unique :
      // chaque handle*() renvoie true là où il faisait « return; ».
      if (handleAutopilotMessage(data)) return;

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

      if (handleSystemMessage(data)) return;
      if (handleCodeWorkshopMessage(data)) return;
      if (handleVues3DMessage(data)) return;
      if (handleSettingsMessage(data)) return;
      handleHudMessage(data, pushDomAction);
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

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_INTERVAL_MS);
}
