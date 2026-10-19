// ════════════════════════════════════════════════════════════
//   ha_dashboard.ts — Home Assistant Control Dashboard
//   (panneau au style commun css/13_panneaux_modules.css)
// ════════════════════════════════════════════════════════════

import { esc, icone } from "./panels/pm_utils";
import { wsRef } from "./ws_link";

interface HAEntity {
  entity_id: string;
  state: string;
  attributes: {
    friendly_name?: string;
    unit_of_measurement?: string;
    [key: string]: any;
  };
}

interface PinnedPosition {
  left: string;
  top: string;
}

interface PinnedPositionsMap {
  [entity_id: string]: PinnedPosition;
}

// Connexion : toujours wsRef.current (réassignée à chaque reconnexion). Avant, la socket
// passée au démarrage était gardée à vie : après une reconnexion, interrupteurs et
// « Actualiser » ne faisaient plus rien, sans message.
function _ws(): WebSocket | null {
  return wsRef.current;
}
let _entities: HAEntity[] = [];
let _activeCategory: string = "all";
let _searchQuery: string = "";

// Drag and drop state for main panel
let _isDragging = false;
let _dragOffX = 0;
let _dragOffY = 0;

export function initHADashboard(ws: WebSocket | null): void {
  void ws; // conservé pour compatibilité (main.ts)

  const panel = document.getElementById("ha-panel");
  const dragHandle = document.getElementById("ha-panel-drag-handle");
  const closeBtn = document.getElementById("ha-panel-close-btn");
  const refreshBtn = document.getElementById("ha-refresh-btn");
  const searchInput = document.getElementById("ha-search-input") as HTMLInputElement;
  const toggleBtn = document.getElementById("ha-toggle-btn");

  if (!panel) return;

  // Restore saved main panel position if exists
  const savedLeft = localStorage.getItem("ha-panel-left");
  const savedTop = localStorage.getItem("ha-panel-top");
  if (savedLeft && savedTop) {
    let leftVal = parseFloat(savedLeft);
    let topVal = parseFloat(savedTop);
    
    // Clamp to screen bounds to prevent it from going offscreen
    const maxLeft = Math.max(0, window.innerWidth - 300);
    const maxTop = Math.max(0, window.innerHeight - 80);
    leftVal = Math.max(0, Math.min(maxLeft, leftVal));
    topVal = Math.max(0, Math.min(maxTop, topVal));
    
    panel.style.transform = "none";
    panel.style.left = leftVal + "px";
    panel.style.top = topVal + "px";
  }

  // ── Drag Logic (Main Panel) ────────────────────────────────────────────────
  if (dragHandle) {
    dragHandle.addEventListener("mousedown", (e: MouseEvent) => {
      if ((e.target as HTMLElement).closest(".ha-panel-controls")) return;
      _isDragging = true;
      const rect = panel.getBoundingClientRect();
      _dragOffX = e.clientX - rect.left;
      _dragOffY = e.clientY - rect.top;
      panel.style.transform = "none";
      panel.style.left = rect.left + "px";
      panel.style.top = rect.top + "px";
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e: MouseEvent) => {
      if (_isDragging) {
        let newLeft = e.clientX - _dragOffX;
        let newTop = e.clientY - _dragOffY;
        const rect = panel.getBoundingClientRect();
        const maxLeft = Math.max(0, window.innerWidth - rect.width);
        const maxTop = Math.max(0, window.innerHeight - 40);
        newLeft = Math.max(0, Math.min(maxLeft, newLeft));
        newTop = Math.max(0, Math.min(maxTop, newTop));
        panel.style.left = newLeft + "px";
        panel.style.top = newTop + "px";
      }
    });

    document.addEventListener("mouseup", () => {
      if (_isDragging) {
        _isDragging = false;
        localStorage.setItem("ha-panel-left", panel.style.left);
        localStorage.setItem("ha-panel-top", panel.style.top);
      }
    });
  }

  // ── Close logic ──────────────────────────────────────────────────────────
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      panel.classList.add("hidden");
      if (toggleBtn) {
        toggleBtn.setAttribute("aria-pressed", "false");
        toggleBtn.classList.remove("active");
      }
    });
  }

  // ── Refresh logic ────────────────────────────────────────────────────────
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      fetchHAStates();
    });
  }

  // ── Search logic ─────────────────────────────────────────────────────────
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      _searchQuery = (e.target as HTMLInputElement).value.toLowerCase();
      renderGrid();
    });
  }

  // ── Category Tabs logic ──────────────────────────────────────────────────
  const tabBtns = document.querySelectorAll(".ha-tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      _activeCategory = btn.getAttribute("data-category") || "all";
      renderGrid();
    });
  });

  // Request initial HA states
  fetchHAStates();
}

export function handleHAMessage(data: any): void {
  const panelStatus = document.querySelector(".ha-status-label");

  if (data.type === "ha_states") {
    if (data.success && Array.isArray(data.states)) {
      _entities = data.states;
      if (panelStatus) {
        panelStatus.innerHTML = `<span class="pm-ok">●</span> Home Assistant · ${data.states.length} appareil${data.states.length > 1 ? "s" : ""}`;
      }
      renderGrid();
      renderPinnedWidgets();
    } else {
      showError("Impossible de lire les appareils de Home Assistant");
      if (panelStatus) panelStatus.innerHTML = `<span class="pm-erreur">●</span> Home Assistant non configuré ou injoignable`;
    }
  } else if (data.type === "ha_state_changed") {
    if (data.entity_id && data.state) {
      const idx = _entities.findIndex(e => e.entity_id === data.entity_id);
      if (idx !== -1) {
        _entities[idx] = data.state;
      } else {
        _entities.push(data.state);
      }
      updateSingleCard(data.state);
      updateSingleFloatingWidget(data.state);
    }
  } else if (data.type === "ha_service_result") {
    if (data.success && data.entity_id && data.state) {
      const idx = _entities.findIndex(e => e.entity_id === data.entity_id);
      if (idx !== -1) {
        _entities[idx] = data.state;
      }
      updateSingleCard(data.state);
      updateSingleFloatingWidget(data.state);
    }
  }
}

function fetchHAStates(): void {
  const ws = _ws();
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  const grid = document.getElementById("ha-entities-grid");
  if (grid) {
    grid.innerHTML = `<div class="ha-loading-msg">SYNCHRONISATION AVEC HOME ASSISTANT…</div>`;
  }

  ws.send(JSON.stringify({ type: "ha_get_states" }));
}

function callHAService(domain: string, service: string, entity_id: string, service_data?: any): void {
  const ws = _ws();
  if (!ws || ws.readyState !== WebSocket.OPEN) return;

  ws.send(JSON.stringify({
    type: "ha_call_service",
    domain,
    service,
    entity_id,
    service_data
  }));
}

// Icônes au trait (pm_utils) à la place des emojis : rendu net et cohérent avec les autres
// panneaux, couleur pilotée par le CSS (ambre quand l'appareil est allumé).
function getEntityIcon(entity_id: string, _state: string, friendly_name: string): string {
  const domain = entity_id.split(".")[0];
  const nameLower = friendly_name.toLowerCase();

  switch (domain) {
    case "light":
      return icone("ampoule");
    case "switch":
    case "input_boolean":
      return icone("prise");
    case "valve":
      return icone("robinet");
    case "fan":
      return icone("ventilateur");
    case "vacuum":
      return icone("robot");
    case "climate":
      return icone("flocon");
    case "binary_sensor":
      if (nameLower.includes("mouvement") || nameLower.includes("motion") || nameLower.includes("presence")) {
        return icone("mouvement");
      }
      if (nameLower.includes("porte") || nameLower.includes("fenetre") || nameLower.includes("door") || nameLower.includes("window")) {
        return icone("porte");
      }
      return icone("bouclier");
    case "sensor":
      if (nameLower.includes("temp")) return icone("thermometre");
      if (nameLower.includes("humi")) return icone("goutte");
      if (nameLower.includes("batterie") || nameLower.includes("battery")) return icone("batterie");
      if (nameLower.includes("puissance") || nameLower.includes("power") || nameLower.includes("energie") || nameLower.includes("energy")) {
        return icone("eclair");
      }
      if (nameLower.includes("lux") || nameLower.includes("luminosite") || nameLower.includes("light")) return icone("soleil");
      return icone("graphique");
    default:
      return icone("engrenage");
  }
}

function getDomainCategory(entity_id: string): string {
  const domain = entity_id.split(".")[0];
  if (domain === "light") return "light";
  if (domain === "switch" || domain === "input_boolean" || domain === "valve") return "switch";
  if (domain === "sensor" || domain === "binary_sensor" || domain === "climate") return "sensor";
  if (domain === "fan") return "fan";
  if (domain === "vacuum") return "vacuum";
  return "other";
}

const ETATS_ASPIRATEUR: Record<string, string> = {
  docked: "À la base", cleaning: "Nettoyage", returning: "Retour à la base",
  idle: "En attente", paused: "En pause", error: "Erreur",
};

function getFormattedState(entity: HAEntity): string {
  const stateVal = entity.state;
  const domain = entity.entity_id.split(".")[0];
  const attrs = entity.attributes || {};

  if (stateVal === "unavailable" || stateVal === "unknown") return "Hors ligne";
  if (domain === "vacuum") {
    const batterie = attrs.battery_level !== undefined ? ` · ${attrs.battery_level} %` : "";
    return (ETATS_ASPIRATEUR[stateVal] || stateVal) + batterie;
  }
  if (stateVal === "on") {
    // Détail utile : luminosité d'une lampe, consommation d'une prise
    if (domain === "light" && typeof attrs.brightness === "number") return `Allumée · ${Math.round(attrs.brightness / 2.55)} %`;
    const watts = attrs.current_power_w ?? attrs.power ?? attrs.current_consumption;
    if (typeof watts === "number") return `Allumé · ${Math.round(watts)} W`;
    return domain === "light" ? "Allumée" : "Allumé";
  }
  if (stateVal === "off") return domain === "light" ? "Éteinte" : "Éteint";
  if (stateVal === "open") return "Ouvert";
  if (stateVal === "closed") return "Fermé";

  // Valeur de capteur : nombre au format français, avec son unité
  const unit = attrs.unit_of_measurement;
  const nombre = Number(stateVal);
  const valeur = stateVal !== "" && !isNaN(nombre)
    ? nombre.toLocaleString("fr-FR", { maximumFractionDigits: 1 })
    : stateVal;
  return unit ? `${valeur} ${unit}` : valeur.charAt(0).toUpperCase() + valeur.slice(1);
}

function buildCardHTML(entity: HAEntity): string {
  const isOn = entity.state === "on" || entity.state === "open";
  const name = entity.attributes.friendly_name || entity.entity_id;
  const icon = getEntityIcon(entity.entity_id, entity.state, name);
  const domain = entity.entity_id.split(".")[0];
  const formattedState = getFormattedState(entity);

  // Check if pinned
  const positions = getPinnedPositions();
  const isPinned = !!positions[entity.entity_id];

  let bottomControls = "";

  if (domain === "light" || domain === "switch" || domain === "input_boolean" || domain === "valve") {
    bottomControls = `
      <label class="ha-switch">
        <input type="checkbox" class="ha-toggle-input" data-entity="${entity.entity_id}" data-domain="${domain}" ${isOn ? "checked" : ""}>
        <span class="ha-slider"></span>
      </label>
    `;
  } else if (domain === "vacuum") {
    const isDocked = entity.state === "docked" || entity.state === "idle";
    bottomControls = `
      <div class="ha-card-actions">
        ${isDocked ? 
          `<button class="ha-action-btn vacuum-btn" data-action="start" data-entity="${entity.entity_id}">Lancer</button>` : 
          `<button class="ha-action-btn vacuum-btn" data-action="return_to_base" data-entity="${entity.entity_id}">Retour à la base</button>`
        }
      </div>
    `;
  } else if (domain === "fan") {
    bottomControls = `
      <label class="ha-switch">
        <input type="checkbox" class="ha-toggle-input" data-entity="${entity.entity_id}" data-domain="${domain}" ${isOn ? "checked" : ""}>
        <span class="ha-slider"></span>
      </label>
    `;
  }

  return `
    <div class="ha-entity-card domain-${domain} ${isOn ? "state-on" : ""}" id="ha-card-${entity.entity_id.replace(/\./g, "-")}">
      <div class="ha-entity-top">
        <div class="ha-entity-info">
          <span class="ha-entity-name" title="${esc(name)}">${esc(name)}</span>
          <span class="ha-entity-domain">${entity.entity_id}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <button class="ha-pin-btn ${isPinned ? "active" : ""}" data-entity="${entity.entity_id}" title="Épingler sur l'interface">${icone("epingle")}</button>
          <div class="ha-entity-icon-wrapper">
            ${icon}
          </div>
        </div>
      </div>
      <div class="ha-entity-middle">
        <span class="ha-entity-state">${formattedState}</span>
        <div class="ha-entity-control">
          ${bottomControls}
        </div>
      </div>
    </div>
  `;
}

function renderGrid(): void {
  const grid = document.getElementById("ha-entities-grid");
  if (!grid) return;

  // Filtrer par catégorie
  let filtered = _entities;
  if (_activeCategory !== "all") {
    filtered = _entities.filter(e => getDomainCategory(e.entity_id) === _activeCategory);
  }

  // Filtrer par recherche
  if (_searchQuery) {
    filtered = filtered.filter(e => {
      const name = (e.attributes.friendly_name || "").toLowerCase();
      const entityId = e.entity_id.toLowerCase();
      return name.includes(_searchQuery) || entityId.includes(_searchQuery);
    });
  }

  if (filtered.length === 0) {
    grid.innerHTML = `<div class="ha-empty-msg">AUCUN APPAREIL POUR CE FILTRE</div>`;
    return;
  }

  // Trier par friendly_name
  filtered.sort((a, b) => {
    const nameA = (a.attributes.friendly_name || a.entity_id).toLowerCase();
    const nameB = (b.attributes.friendly_name || b.entity_id).toLowerCase();
    return nameA.localeCompare(nameB);
  });

  grid.innerHTML = filtered.map(e => buildCardHTML(e)).join("");

  // Attacher les listeners
  attachControlsListeners(grid);
}

function updateSingleCard(entity: HAEntity): void {
  const cardId = `ha-card-${entity.entity_id.replace(/\./g, "-")}`;
  const card = document.getElementById(cardId);
  if (!card) return;

  const isOn = entity.state === "on" || entity.state === "open";
  const name = entity.attributes.friendly_name || entity.entity_id;
  const icon = getEntityIcon(entity.entity_id, entity.state, name);
  const formattedState = getFormattedState(entity);

  // Mettre à jour les classes
  card.className = `ha-entity-card domain-${entity.entity_id.split(".")[0]} ${isOn ? "state-on" : ""}`;
  
  // Mettre à jour l'icône
  const iconWrapper = card.querySelector(".ha-entity-icon-wrapper");
  if (iconWrapper) iconWrapper.innerHTML = icon;

  // Mettre à jour le texte d'état
  const stateLabel = card.querySelector(".ha-entity-state");
  if (stateLabel) stateLabel.textContent = formattedState;

  // Mettre à jour les contrôles (checkboxes) sans re-créer tout l'élément pour éviter les sauts de focus
  const toggleInput = card.querySelector(".ha-toggle-input") as HTMLInputElement;
  if (toggleInput) {
    toggleInput.checked = isOn;
  }

  // Mettre à jour les boutons si c'est un aspirateur
  const domain = entity.entity_id.split(".")[0];
  if (domain === "vacuum") {
    const isDocked = entity.state === "docked" || entity.state === "idle";
    const controlDiv = card.querySelector(".ha-entity-control");
    if (controlDiv) {
      controlDiv.innerHTML = `
        <div class="ha-card-actions">
          ${isDocked ? 
            `<button class="ha-action-btn vacuum-btn" data-action="start" data-entity="${entity.entity_id}">Lancer</button>` : 
            `<button class="ha-action-btn vacuum-btn" data-action="return_to_base" data-entity="${entity.entity_id}">Retour à la base</button>`
          }
        </div>
      `;
      // Ré-attacher le listener sur ce nouveau bouton
      const btn = controlDiv.querySelector(".vacuum-btn");
      if (btn) {
        btn.addEventListener("click", () => {
          const ent = btn.getAttribute("data-entity") || "";
          const action = btn.getAttribute("data-action") || "";
          callHAService("vacuum", action, ent);
        });
      }
    }
  }
}

function attachControlsListeners(container: HTMLElement): void {
  // Checkbox/Toggle Toggles
  container.querySelectorAll(".ha-toggle-input").forEach(input => {
    input.addEventListener("change", (e) => {
      const el = e.target as HTMLInputElement;
      const entityId = el.getAttribute("data-entity") || "";
      const domain = el.getAttribute("data-domain") || "";
      let service = el.checked ? "turn_on" : "turn_off";
      if (domain === "valve") {
        service = el.checked ? "open_valve" : "close_valve";
      }
      callHAService(domain, service, entityId);
    });
  });

  // Vacuum Buttons
  container.querySelectorAll(".vacuum-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const entityId = btn.getAttribute("data-entity") || "";
      const action = btn.getAttribute("data-action") || "";
      callHAService("vacuum", action, entityId);
    });
  });

  // Pin Buttons
  container.querySelectorAll(".ha-pin-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const entityId = btn.getAttribute("data-entity") || "";
      if (btn.classList.contains("active")) {
        unpinEntity(entityId);
      } else {
        pinEntity(entityId);
      }
    });
  });
}

function showError(msg: string): void {
  const grid = document.getElementById("ha-entities-grid");
  if (grid) {
    grid.innerHTML = `<div class="ha-empty-msg pm-erreur">${esc(msg)}</div>`;
  }
}

export function updateHAWS(_ws_inutile: WebSocket | null): void {
  // La connexion courante est lue dans wsRef à chaque envoi (voir _ws)
}

// ── Pinned Widgets Logic ─────────────────────────────────────────────────────

function getPinnedPositions(): PinnedPositionsMap {
  try {
    const val = localStorage.getItem("ha-pinned-positions");
    return val ? JSON.parse(val) : {};
  } catch {
    return {};
  }
}

function savePinnedPositions(map: PinnedPositionsMap): void {
  localStorage.setItem("ha-pinned-positions", JSON.stringify(map));
}

function renderPinnedWidgets(): void {
  // Clear existing floating widgets
  document.querySelectorAll(".ha-floating-widget").forEach(el => el.remove());
  
  const positions = getPinnedPositions();
  for (const entity_id in positions) {
    const entity = _entities.find(e => e.entity_id === entity_id);
    if (entity) {
      createFloatingWidget(entity, positions[entity_id]);
    }
  }
}

function createFloatingWidget(entity: HAEntity, pos: PinnedPosition): void {
  // Remove if already exists
  const existing = document.getElementById(`ha-float-${entity.entity_id.replace(/\./g, "-")}`);
  if (existing) existing.remove();
  
  const isOn = entity.state === "on" || entity.state === "open";
  const name = entity.attributes.friendly_name || entity.entity_id;
  const icon = getEntityIcon(entity.entity_id, entity.state, name);
  const domain = entity.entity_id.split(".")[0];
  const formattedState = getFormattedState(entity);
  
  let bottomControls = "";
  if (domain === "light" || domain === "switch" || domain === "input_boolean" || domain === "valve") {
    bottomControls = `
      <label class="ha-switch">
        <input type="checkbox" class="ha-toggle-input" data-entity="${entity.entity_id}" data-domain="${domain}" ${isOn ? "checked" : ""}>
        <span class="ha-slider"></span>
      </label>
    `;
  } else if (domain === "vacuum") {
    const isDocked = entity.state === "docked" || entity.state === "idle";
    bottomControls = `
      <div class="ha-card-actions">
        ${isDocked ? 
          `<button class="ha-action-btn vacuum-btn" data-action="start" data-entity="${entity.entity_id}">Lancer</button>` : 
          `<button class="ha-action-btn vacuum-btn" data-action="return_to_base" data-entity="${entity.entity_id}">Retour à la base</button>`
        }
      </div>
    `;
  } else if (domain === "fan") {
    bottomControls = `
      <label class="ha-switch">
        <input type="checkbox" class="ha-toggle-input" data-entity="${entity.entity_id}" data-domain="${domain}" ${isOn ? "checked" : ""}>
        <span class="ha-slider"></span>
      </label>
    `;
  }
  
  const widget = document.createElement("div");
  widget.id = `ha-float-${entity.entity_id.replace(/\./g, "-")}`;
  widget.className = `ha-entity-card ha-floating-widget domain-${domain} ${isOn ? "state-on" : ""}`;
  widget.style.position = "absolute";
  widget.style.left = pos.left;
  widget.style.top = pos.top;
  widget.style.width = "230px";
  widget.style.zIndex = "400";
  widget.style.cursor = "grab";
  
  widget.innerHTML = `
    <div class="ha-entity-top">
      <div class="ha-entity-info">
        <span class="ha-entity-name" title="${esc(name)}">${esc(name)}</span>
        <span class="ha-entity-domain">${entity.entity_id}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <button class="ha-pin-btn active" data-entity="${entity.entity_id}" title="Désépingler">${icone("epingle")}</button>
        <div class="ha-entity-icon-wrapper">
          ${icon}
        </div>
      </div>
    </div>
    <div class="ha-entity-middle">
      <span class="ha-entity-state">${formattedState}</span>
      <div class="ha-entity-control">
        ${bottomControls}
      </div>
    </div>
  `;
  
  document.body.appendChild(widget);
  
  // Attach drag logic
  makeFloatingWidgetDraggable(widget, entity.entity_id);
  
  // Attach control listeners to this widget
  attachControlsListeners(widget);
  
  // Attach pin toggling listener on this widget
  const pinBtn = widget.querySelector(".ha-pin-btn");
  if (pinBtn) {
    pinBtn.addEventListener("click", () => {
      unpinEntity(entity.entity_id);
    });
  }
}

function makeFloatingWidgetDraggable(el: HTMLElement, entity_id: string): void {
  let isWidgetDragging = false;
  let startX = 0, startY = 0;
  
  el.addEventListener("mousedown", (e: MouseEvent) => {
    // If clicking on a toggle input, button, or pushpin, don't drag
    if ((e.target as HTMLElement).closest(".ha-toggle-input, .ha-action-btn, .ha-pin-btn, .ha-slider")) return;
    
    isWidgetDragging = true;
    el.style.cursor = "grabbing";
    const rect = el.getBoundingClientRect();
    startX = e.clientX - rect.left;
    startY = e.clientY - rect.top;
    el.style.transform = "none";
    el.style.left = rect.left + "px";
    el.style.top = rect.top + "px";
    el.style.margin = "0";
    e.preventDefault();
  });
  
  document.addEventListener("mousemove", (e: MouseEvent) => {
    if (isWidgetDragging) {
      let newLeft = e.clientX - startX;
      let newTop = e.clientY - startY;
      
      // Clamp to screen bounds
      const maxLeft = window.innerWidth - el.offsetWidth;
      const maxTop = window.innerHeight - el.offsetHeight;
      newLeft = Math.max(0, Math.min(maxLeft, newLeft));
      newTop = Math.max(0, Math.min(maxTop, newTop));
      
      el.style.left = newLeft + "px";
      el.style.top = newTop + "px";
    }
  });
  
  document.addEventListener("mouseup", () => {
    if (isWidgetDragging) {
      isWidgetDragging = false;
      el.style.cursor = "grab";
      
      // Save position to localStorage
      const positions = getPinnedPositions();
      positions[entity_id] = {
        left: el.style.left,
        top: el.style.top
      };
      savePinnedPositions(positions);
    }
  });
}

function unpinEntity(entity_id: string): void {
  const positions = getPinnedPositions();
  delete positions[entity_id];
  savePinnedPositions(positions);
  
  // Remove floating widget element
  const el = document.getElementById(`ha-float-${entity_id.replace(/\./g, "-")}`);
  if (el) el.remove();
  
  // Update the card in the main HA dashboard grid if open
  const mainCard = document.getElementById(`ha-card-${entity_id.replace(/\./g, "-")}`);
  if (mainCard) {
    const pinBtn = mainCard.querySelector(".ha-pin-btn");
    if (pinBtn) pinBtn.classList.remove("active");
  }
}

function pinEntity(entity_id: string): void {
  // Check if already pinned
  const positions = getPinnedPositions();
  if (positions[entity_id]) return;
  
  // Default position: center of the screen
  const left = `${window.innerWidth / 2 - 115}px`;
  const top = `${window.innerHeight / 2 - 50}px`;
  
  positions[entity_id] = { left, top };
  savePinnedPositions(positions);
  
  const entity = _entities.find(e => e.entity_id === entity_id);
  if (entity) {
    createFloatingWidget(entity, { left, top });
  }
  
  // Update pin button in the main HA dashboard grid if open
  const mainCard = document.getElementById(`ha-card-${entity_id.replace(/\./g, "-")}`);
  if (mainCard) {
    const pinBtn = mainCard.querySelector(".ha-pin-btn");
    if (pinBtn) pinBtn.classList.add("active");
  }
}

function updateSingleFloatingWidget(entity: HAEntity): void {
  const widgetId = `ha-float-${entity.entity_id.replace(/\./g, "-")}`;
  const widget = document.getElementById(widgetId);
  if (!widget) return;

  const isOn = entity.state === "on" || entity.state === "open";
  const name = entity.attributes.friendly_name || entity.entity_id;
  const icon = getEntityIcon(entity.entity_id, entity.state, name);
  const formattedState = getFormattedState(entity);

  // Update classes
  widget.className = `ha-entity-card ha-floating-widget domain-${entity.entity_id.split(".")[0]} ${isOn ? "state-on" : ""}`;
  
  // Update icon
  const iconWrapper = widget.querySelector(".ha-entity-icon-wrapper");
  if (iconWrapper) iconWrapper.innerHTML = icon;

  // Update state text
  const stateLabel = widget.querySelector(".ha-entity-state");
  if (stateLabel) stateLabel.textContent = formattedState;

  // Update switch checkbox
  const toggleInput = widget.querySelector(".ha-toggle-input") as HTMLInputElement;
  if (toggleInput) {
    toggleInput.checked = isOn;
  }

  // Update vacuum buttons if vacuum
  const domain = entity.entity_id.split(".")[0];
  if (domain === "vacuum") {
    const isDocked = entity.state === "docked" || entity.state === "idle";
    const controlDiv = widget.querySelector(".ha-entity-control");
    if (controlDiv) {
      controlDiv.innerHTML = `
        <div class="ha-card-actions">
          ${isDocked ? 
            `<button class="ha-action-btn vacuum-btn" data-action="start" data-entity="${entity.entity_id}">Lancer</button>` : 
            `<button class="ha-action-btn vacuum-btn" data-action="return_to_base" data-entity="${entity.entity_id}">Retour à la base</button>`
          }
        </div>
      `;
      // Re-attach listeners to vacuum buttons on widget
      const btn = controlDiv.querySelector(".vacuum-btn");
      if (btn) {
        btn.addEventListener("click", () => {
          const ent = btn.getAttribute("data-entity") || "";
          const action = btn.getAttribute("data-action") || "";
          callHAService("vacuum", action, ent);
        });
      }
    }
  }
}
