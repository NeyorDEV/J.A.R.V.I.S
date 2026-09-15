// ── Panneau mises à jour winget — extrait de main.ts ──

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { closeUninstallerPanel } from "./uninstaller_panel";

// ── Winget Upgrade DOM Refs ────────────────────────────────────────────────
const wingetPanel = document.getElementById("winget-panel") as HTMLDivElement;
const wingetToggleBtn = document.getElementById("winget-toggle-btn") as HTMLButtonElement;
const wingetCloseBtn = document.getElementById("winget-panel-close-btn") as HTMLButtonElement;
const wingetHeader = document.getElementById("winget-panel-header") as HTMLDivElement;
const wingetSearchInput = document.getElementById("winget-search-input") as HTMLInputElement;
const wingetList = document.getElementById("winget-upgrades-list") as HTMLDivElement;
const wingetSelectAll = document.getElementById("winget-select-all") as HTMLInputElement;
const wingetRefreshBtn = document.getElementById("winget-refresh-btn") as HTMLButtonElement;
const wingetUpgradeSelectedBtn = document.getElementById("winget-upgrade-selected-btn") as HTMLButtonElement;
const wingetUpgradeAllBtn = document.getElementById("winget-upgrade-all-btn") as HTMLButtonElement;
const wingetLogsContainer = document.getElementById("winget-logs-container") as HTMLDivElement;
const wingetConsole = document.getElementById("winget-console") as HTMLPreElement;
const wingetCloseLogsBtn = document.getElementById("winget-close-logs-btn") as HTMLButtonElement;
const wingetCountBadge = document.getElementById("winget-count-badge") as HTMLSpanElement;

interface WingetUpgradeItem {
  name: string;
  id: string;
  version: string;
  available: string;
  source: string;
}

let allWingetUpgrades: WingetUpgradeItem[] = [];


// ── Winget Upgrade Panel Toggle and Draggable ──
if (wingetPanel && wingetHeader) {
  makePanelDraggable(wingetPanel, wingetHeader);
}

wingetCloseBtn?.addEventListener("click", () => {
  closeWingetPanel();
});

wingetToggleBtn?.addEventListener("click", () => {
  const isHidden = wingetPanel.classList.contains("hidden");
  if (isHidden) {
    openWingetPanel();
  } else {
    closeWingetPanel();
  }
});

// ── Winget Upgrade Panel Core Functions ──
export function openWingetPanel() {
  if (wingetPanel) {
    wingetPanel.classList.remove("hidden");
    wingetPanel.classList.add("visible");
    wingetToggleBtn?.setAttribute("aria-pressed", "true");
    
    // Synchroniser avec le bouton du menu dropdown unifié
    const menuBtn = document.getElementById("winget-toggle-btn");
    if (menuBtn) {
      menuBtn.setAttribute("aria-pressed", "true");
      menuBtn.classList.add("active");
    }
    
    // Close other panels if needed
    closeUninstallerPanel(); // vérifie l'existence du panneau en interne
    
    wingetLogsContainer?.classList.add("hidden");
    
    if (wingetList) {
      wingetList.innerHTML = '<div class="uninstaller-loading" style="color: #00e5ff;">RECHERCHE DES MISES À JOUR...</div>';
    }
    
    // Request winget upgrades
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "get_winget_upgrades" }));
    }
  }
}

export function closeWingetPanel() {
  if (wingetPanel) {
    wingetPanel.classList.add("hidden");
    wingetPanel.classList.remove("visible");
    wingetToggleBtn?.setAttribute("aria-pressed", "false");
    
    // Synchroniser avec le bouton du menu dropdown unifié
    const menuBtn = document.getElementById("winget-toggle-btn");
    if (menuBtn) {
      menuBtn.setAttribute("aria-pressed", "false");
      menuBtn.classList.remove("active");
    }
  }
}

function renderWingetUpgrades(upgrades: WingetUpgradeItem[]) {
  if (!wingetList) return;
  wingetList.innerHTML = "";
  
  if (upgrades.length === 0) {
    const empty = document.createElement("div");
    empty.className = "uninstaller-loading";
    empty.style.color = "#00e5ff";
    empty.textContent = "VOTRE SYSTÈME EST À JOUR";
    wingetList.appendChild(empty);
    
    if (wingetCountBadge) {
      wingetCountBadge.textContent = "0";
      wingetCountBadge.classList.add("hidden");
    }
    return;
  }
  
  if (wingetCountBadge) {
    wingetCountBadge.textContent = upgrades.length.toString();
    wingetCountBadge.classList.remove("hidden");
  }
  
  upgrades.forEach((item, idx) => {
    const el = document.createElement("div");
    el.className = "uninstaller-app-item";
    el.innerHTML = `
      <div class="uninstaller-app-info" style="display:flex; flex-direction:row; align-items:center; gap:10px; width:65%;">
        <input type="checkbox" class="winget-select-checkbox" data-idx="${idx}" checked style="accent-color: #00e5ff;">
        <div style="flex:1;">
          <div class="uninstaller-app-name" style="color:#00e5ff;">${item.name}</div>
          <div class="uninstaller-app-publisher" style="font-size:9px; opacity:0.7;">
            ID: ${item.id} | v${item.version} → <span style="color:#00ff88;">v${item.available}</span>
          </div>
        </div>
      </div>
      <button class="uninstaller-app-btn winget-upgrade-item-btn" data-id="${item.id}" style="border-color:#00e5ff; color:#00e5ff; background:rgba(0,229,255,0.05);">METTRE À JOUR</button>
    `;
    
    const btn = el.querySelector(".winget-upgrade-item-btn") as HTMLButtonElement;
    btn.addEventListener("click", () => {
      runWingetUpgrade([item.id]);
    });
    
    wingetList.appendChild(el);
  });
}

function runWingetUpgrade(ids: string[]) {
  if (ids.length === 0) return;
  if (wingetLogsContainer && wingetConsole) {
    wingetLogsContainer.classList.remove("hidden");
    wingetConsole.textContent = `[JARVIS] Lancement de la mise à jour pour:\n- ${ids.join("\n- ")}\n\n`;
    wingetConsole.scrollTop = wingetConsole.scrollHeight;
  }
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "run_winget_upgrade",
      ids: ids
    }));
  }
}

// Event Listeners for Winget controls
wingetSearchInput?.addEventListener("input", () => {
  const query = wingetSearchInput.value.trim().toLowerCase();
  const items = document.querySelectorAll("#winget-upgrades-list .uninstaller-app-item");
  items.forEach(item => {
    const text = item.textContent?.toLowerCase() || "";
    if (text.includes(query)) {
      (item as HTMLElement).style.display = "";
    } else {
      (item as HTMLElement).style.display = "none";
    }
  });
});

wingetSelectAll?.addEventListener("change", () => {
  const checked = wingetSelectAll.checked;
  const checkboxes = document.querySelectorAll(".winget-select-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    cb.checked = checked;
  });
});

wingetRefreshBtn?.addEventListener("click", () => {
  if (wingetList) {
    wingetList.innerHTML = '<div class="uninstaller-loading" style="color: #00e5ff;">RECHERCHE DES MISES À JOUR...</div>';
  }
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "get_winget_upgrades" }));
  }
});

wingetUpgradeSelectedBtn?.addEventListener("click", () => {
  const ids: string[] = [];
  const checkboxes = document.querySelectorAll(".winget-select-checkbox") as NodeListOf<HTMLInputElement>;
  checkboxes.forEach(cb => {
    // La recherche masque les lignes non correspondantes SANS décocher leur case.
    // Sans ce test, filtrer sur une application puis cliquer « mettre à jour la
    // sélection » mettait à jour TOUS les logiciels, y compris les invisibles.
    const ligne = cb.closest(".uninstaller-app-item") as HTMLElement | null;
    if (ligne && ligne.style.display === "none") return;

    if (cb.checked) {
      const idx = parseInt(cb.getAttribute("data-idx") || "0");
      const item = allWingetUpgrades[idx];
      if (item) ids.push(item.id);   // garde-fou : index hors bornes possible
    }
  });
  if (ids.length === 0) {
    alert("Veuillez sélectionner au moins un logiciel visible à mettre à jour.");
    return;
  }
  runWingetUpgrade(ids);
});

wingetUpgradeAllBtn?.addEventListener("click", () => {
  if (allWingetUpgrades.length === 0) {
    alert("Aucune mise à jour disponible à installer.");
    return;
  }
  if (wingetLogsContainer && wingetConsole) {
    wingetLogsContainer.classList.remove("hidden");
    wingetConsole.textContent = "[JARVIS] Lancement de la mise à jour globale du système...\n\n";
    wingetConsole.scrollTop = wingetConsole.scrollHeight;
  }
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "run_winget_upgrade",
      all: true
    }));
  }
});

wingetCloseLogsBtn?.addEventListener("click", () => {
  wingetLogsContainer?.classList.add("hidden");
  // Refresh the list after upgrade closes
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "get_winget_upgrades" }));
  }
});


// ── API pour le dispatch WebSocket de main.ts ──
export function handleWingetUpgrades(upgrades: WingetUpgradeItem[]) {
  allWingetUpgrades = upgrades;
  renderWingetUpgrades(allWingetUpgrades);
}

export function appendWingetProgress(progressData: any) {
  if (wingetConsole) {
    if (progressData.status === "running") {
      wingetConsole.textContent += progressData.log;
      wingetConsole.scrollTop = wingetConsole.scrollHeight;
    } else if (progressData.status === "complete") {
      wingetConsole.textContent += `\n[JARVIS] Processus de mise à jour terminé (Code: ${progressData.returncode}).\n`;
      wingetConsole.scrollTop = wingetConsole.scrollHeight;
    }
  }
}
