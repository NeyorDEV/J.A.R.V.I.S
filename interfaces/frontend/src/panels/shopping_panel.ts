// ── Panneau liste de courses (style verre : css/13 et css/14) ──────────────────

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { esc, icone } from "./pm_utils";

let currentShoppingList: string[] = [];

const shoppingPanel = document.getElementById("shopping-panel") as HTMLDivElement;
const shoppingCloseBtn = document.getElementById("shopping-panel-close-btn") as HTMLButtonElement;
const shoppingListContainer = document.getElementById("shopping-list-container") as HTMLDivElement;
const shoppingAddInput = document.getElementById("shopping-add-input") as HTMLInputElement;
const shoppingAddBtn = document.getElementById("shopping-add-btn") as HTMLButtonElement;
const shoppingClearBtn = document.getElementById("shopping-clear-btn") as HTMLButtonElement;
const shoppingHeader = document.getElementById("shopping-panel-header") as HTMLDivElement;
const shoppingCount = document.getElementById("shopping-count") as HTMLDivElement;
const shoppingRestants = document.getElementById("shopping-restants") as HTMLSpanElement;

if (shoppingPanel && shoppingHeader) {
  makePanelDraggable(shoppingPanel, shoppingHeader);
}

shoppingCloseBtn?.addEventListener("click", () => {
  shoppingPanel.classList.add("hidden");
  shoppingPanel.classList.remove("visible");
});

shoppingClearBtn?.addEventListener("click", () => {
  currentShoppingList = [];
  sendShoppingListToBackend();
});

function renderShoppingList() {
  if (!shoppingListContainer) return;
  const total = currentShoppingList.length;
  const restants = currentShoppingList.filter(i => !i.startsWith("[x] ")).length;
  if (shoppingCount) {
    shoppingCount.textContent = total === 0
      ? "Liste vide"
      : `${total} article${total > 1 ? "s" : ""}` + (restants < total ? ` · ${restants} à prendre` : "");
  }
  if (shoppingRestants) shoppingRestants.textContent = total === 0 ? "" : `${restants} restant${restants > 1 ? "s" : ""}`;
  if (shoppingClearBtn) shoppingClearBtn.disabled = total === 0;
  if (total === 0) {
    shoppingListContainer.innerHTML = '<div class="pm-vide">AUCUN ARTICLE DANS LA LISTE</div>';
    return;
  }
  shoppingListContainer.innerHTML = currentShoppingList.map((itemText, idx) => {
    const fait = itemText.startsWith("[x] ");
    const nom = fait ? itemText.substring(4) : itemText;
    return `
      <div class="pm-ligne${fait ? " pm-fait" : ""}" data-idx="${idx}">
        <input type="checkbox" class="pm-case" data-action="cocher" ${fait ? "checked" : ""}>
        <div class="pm-texte"><div class="pm-nom">${esc(nom)}</div></div>
        <button class="pm-icone-bouton pm-action-survol" data-action="supprimer" title="Retirer">${icone("corbeille")}</button>
      </div>`;
  }).join("");
}

// Un seul écouteur pour toutes les lignes (cocher / retirer)
shoppingListContainer?.addEventListener("click", (e) => {
  const cible = (e.target as HTMLElement).closest<HTMLElement>("[data-action]");
  const ligne = (e.target as HTMLElement).closest<HTMLElement>(".pm-ligne");
  if (!cible || !ligne) return;
  const idx = Number(ligne.dataset.idx);
  if (!Number.isInteger(idx) || idx < 0 || idx >= currentShoppingList.length) return;
  const texte = currentShoppingList[idx];
  if (cible.dataset.action === "cocher") {
    currentShoppingList[idx] = texte.startsWith("[x] ") ? texte.substring(4) : `[x] ${texte}`;
    sendShoppingListToBackend();
  } else if (cible.dataset.action === "supprimer") {
    currentShoppingList.splice(idx, 1);
    sendShoppingListToBackend();
  }
});

function sendShoppingListToBackend() {
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "update_shopping_list",
      items: currentShoppingList
    }));
  }
}

function addShoppingItem() {
  if (!shoppingAddInput) return;
  const val = shoppingAddInput.value.trim();
  if (val) {
    currentShoppingList.push(val);
    shoppingAddInput.value = "";
    sendShoppingListToBackend();
  }
}

shoppingAddBtn?.addEventListener("click", addShoppingItem);
shoppingAddInput?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") addShoppingItem();
});


// ── API pour le dispatch WebSocket de main.ts ──
export function setShoppingList(items: string[]) {
  currentShoppingList = items;
  renderShoppingList();
}

export function openShoppingPanel() {
  if (shoppingPanel) {
    shoppingPanel.classList.remove("hidden");
    shoppingPanel.classList.add("visible");
  }
}
