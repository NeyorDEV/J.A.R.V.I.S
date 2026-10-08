// ── Panneau désinstallateur (style Revo) — extrait de main.ts ──

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { closeWingetPanel } from "./winget_panel";

// ── Uninstaller DOM Refs ───────────────────────────────────────────────────
const uninstallerPanel = document.getElementById("uninstaller-panel") as HTMLDivElement;
const uninstallerToggleBtn = document.getElementById("uninstaller-toggle-btn") as HTMLButtonElement;
const uninstallerCloseBtn = document.getElementById("uninstaller-panel-close-btn") as HTMLButtonElement;
const uninstallerHeader = document.getElementById("uninstaller-panel-header") as HTMLDivElement;
const uninstallerSearchInput = document.getElementById("uninstaller-search-input") as HTMLInputElement;
const uninstallerAppsList = document.getElementById("uninstaller-apps-list") as HTMLDivElement;
const uninstallerListView = document.getElementById("uninstaller-list-view") as HTMLDivElement;
const uninstallerActionView = document.getElementById("uninstaller-action-view") as HTMLDivElement;
const uninstallerStatusMsg = document.getElementById("uninstaller-status-msg") as HTMLDivElement;
const uninstallerRadarContainer = document.getElementById("uninstaller-radar-container") as HTMLDivElement;
const uninstallerLeftoversContainer = document.getElementById("uninstaller-leftovers-container") as HTMLDivElement;
const uninstallerLeftoversList = document.getElementById("uninstaller-leftovers-list") as HTMLDivElement;
const uninstallerSelectAll = document.getElementById("uninstaller-select-all") as HTMLInputElement;
const uninstallerCleanBtn = document.getElementById("uninstaller-clean-btn") as HTMLButtonElement;
const uninstallerSkipBtn = document.getElementById("uninstaller-skip-btn") as HTMLButtonElement;

let allInstalledPrograms: Array<{
  name: string;
  subkey: string;
  publisher: string;
  version: string;
  uninstall_string: string;
  install_location: string;
  icon_path: string;
  hive: string;
}> = [];
let currentLeftovers: Array<{
  type: string;
  path: string;
  desc: string;
  hive?: string;
}> = [];


// ── LOGIQUE DU DÉSINSTALLATEUR (UNINSTALLER PANEL) ──────────────────────────
if (uninstallerPanel && uninstallerHeader) {
  makePanelDraggable(uninstallerPanel, uninstallerHeader);
}

uninstallerCloseBtn?.addEventListener("click", () => {
  closeUninstallerPanel();
});

uninstallerToggleBtn?.addEventListener("click", () => {
  const isHidden = uninstallerPanel.classList.contains("hidden");
  if (isHidden) {
    openUninstallerPanel();
  } else {
    closeUninstallerPanel();
  }
});


// ── Uninstaller core functions and listeners ──
export function openUninstallerPanel() {
  if (uninstallerPanel) {
    uninstallerPanel.classList.remove("hidden");
    uninstallerPanel.classList.add("visible");
    uninstallerToggleBtn?.setAttribute("aria-pressed", "true");
    
    // Synchroniser avec le bouton du menu dropdown unifié
    const menuBtn = document.getElementById("menu-uninstaller-toggle-btn");
    if (menuBtn) {
      menuBtn.setAttribute("aria-pressed", "true");
      menuBtn.classList.add("active");
    }
    
    closeWingetPanel(); // vérifie l'existence du panneau en interne
    
    // Switch to list view initially
    uninstallerListView?.classList.remove("hidden");
    uninstallerActionView?.classList.add("hidden");
    
    // Set loading status
    if (uninstallerAppsList) {
      uninstallerAppsList.innerHTML = '<div class="uninstaller-loading">CHARGEMENT DE LA LISTE DES LOGICIELS...</div>';
    }
    
    // Request installed programs
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "get_installed_programs" }));
    }
  }
}

export function closeUninstallerPanel() {
  if (uninstallerPanel) {
    uninstallerPanel.classList.add("hidden");
    uninstallerPanel.classList.remove("visible");
    uninstallerToggleBtn?.setAttribute("aria-pressed", "false");
    
    // Synchroniser avec le bouton du menu dropdown unifié
    const menuBtn = document.getElementById("menu-uninstaller-toggle-btn");
    if (menuBtn) {
      menuBtn.setAttribute("aria-pressed", "false");
      menuBtn.classList.remove("active");
    }
  }
}

function renderInstalledPrograms(programs: typeof allInstalledPrograms) {
  if (!uninstallerAppsList) return;
  uninstallerAppsList.innerHTML = "";
  
  if (programs.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-loading";
    empty.textContent = "AUCUN LOGICIEL TROUVÉ";
    uninstallerAppsList.appendChild(empty);
    return;
  }
  
  programs.forEach(prog => {
    const item = document.createElement("div");
    item.className = "uninstaller-app-item";
    
    item.innerHTML = `
      <div class="uninstaller-app-info">
        <div class="uninstaller-app-name">${prog.name}</div>
        <div class="uninstaller-app-publisher">${prog.publisher || 'Éditeur inconnu'} - v${prog.version || 'Inconnue'} (${prog.hive})</div>
      </div>
      <button class="uninstaller-app-btn">DÉSINSTALLER</button>
    `;
    
    const btn = item.querySelector(".uninstaller-app-btn") as HTMLButtonElement;
    btn.addEventListener("click", () => {
      triggerUninstall(prog);
    });
    
    uninstallerAppsList.appendChild(item);
  });
}

function triggerUninstall(prog: typeof allInstalledPrograms[0]) {
  uninstallerListView?.classList.add("hidden");
  uninstallerActionView?.classList.remove("hidden");
  
  uninstallerRadarContainer?.classList.remove("hidden");
  uninstallerLeftoversContainer?.classList.add("hidden");
  if (uninstallerStatusMsg) {
    uninstallerStatusMsg.textContent = `Lancement de la désinstallation de ${prog.name}...`;
  }
  
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "uninstall_program",
      name: prog.name,
      publisher: prog.publisher,
      install_location: prog.install_location,
      uninstall_string: prog.uninstall_string
    }));
  }
}

export function updateUninstallProgress(data: any) {
  if (uninstallerStatusMsg) {
    uninstallerStatusMsg.textContent = data.message || "En cours...";
  }
}

export function showUninstallComplete(data: any) {
  uninstallerRadarContainer?.classList.add("hidden");
  uninstallerLeftoversContainer?.classList.remove("hidden");
  
  currentLeftovers = data.leftovers || [];

  // Reset Select All checkbox
  if (uninstallerSelectAll) {
    uninstallerSelectAll.checked = true;
  }

  // Désinstallation annulée ou ratée : on le dit, au lieu de « aucune trace résiduelle »
  const echec = data.success === false
    ? (data.cancelled ? "Désinstallation annulée." : (data.message || "La désinstallation n'a pas abouti."))
    : null;
  renderLeftovers(echec);
}

function renderLeftovers(messageVide: string | null = null) {
  if (!uninstallerLeftoversList) return;
  uninstallerLeftoversList.innerHTML = "";

  if (currentLeftovers.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-leftover-empty";
    empty.textContent = messageVide || "Aucune trace résiduelle détectée sur le système.";
    uninstallerLeftoversList.appendChild(empty);
    if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = true;
    return;
  }
  
  if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = false;
  
  currentLeftovers.forEach((leftover, idx) => {
    const item = document.createElement("div");
    item.className = "uninstaller-leftover-item";
    
    const icon = leftover.type === 'folder' ? '📁' : '🔑';
    const typeLabel = leftover.type === 'folder' ? 'Dossier' : 'Registre';
    
    item.innerHTML = `
      <label class="uninstaller-leftover-label">
        <input type="checkbox" class="uninstaller-leftover-checkbox" data-idx="${idx}" checked>
        <span class="uninstaller-leftover-icon">${icon}</span>
        <div class="uninstaller-leftover-details">
          <div class="uninstaller-leftover-path" title="${leftover.path}">${leftover.path}</div>
          <div class="uninstaller-leftover-desc">${typeLabel} - ${leftover.desc}</div>
        </div>
      </label>
    `;
    
    uninstallerLeftoversList.appendChild(item);
  });
}

export function showCleanComplete(data: any) {
  const cleaned = data.cleaned_count || 0;
  const total = data.total_count || 0;
  alert(`Nettoyage terminé : ${cleaned}/${total} traces supprimées.`);
  
  // Go back to program list
  openUninstallerPanel();
}

// Event Listeners for Uninstaller Controls
uninstallerSearchInput?.addEventListener("input", () => {
  const query = uninstallerSearchInput.value.trim().toLowerCase();
  if (!query) {
    renderInstalledPrograms(allInstalledPrograms);
  } else {
    const filtered = allInstalledPrograms.filter(p => 
      p.name.toLowerCase().includes(query) || 
      (p.publisher && p.publisher.toLowerCase().includes(query))
    );
    renderInstalledPrograms(filtered);
  }
});

uninstallerSelectAll?.addEventListener("change", () => {
  const checked = uninstallerSelectAll.checked;
  const checkboxes = document.querySelectorAll(".uninstaller-leftover-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    cb.checked = checked;
  });
});

uninstallerCleanBtn?.addEventListener("click", () => {
  const selectedItems: any[] = [];
  const checkboxes = document.querySelectorAll(".uninstaller-leftover-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    if (cb.checked) {
      const idx = parseInt(cb.getAttribute("data-idx") || "0");
      selectedItems.push(currentLeftovers[idx]);
    }
  });
  
  if (selectedItems.length === 0) {
    alert("Veuillez sélectionner au moins une trace à nettoyer.");
    return;
  }
  
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "clean_leftovers",
      items: selectedItems
    }));
  }
});

uninstallerSkipBtn?.addEventListener("click", () => {
  openUninstallerPanel();
});


// ── API pour le dispatch WebSocket de main.ts ──
export function handleInstalledPrograms(programs: typeof allInstalledPrograms) {
  allInstalledPrograms = programs;
  renderInstalledPrograms(allInstalledPrograms);
}
