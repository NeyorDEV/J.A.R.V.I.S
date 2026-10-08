// ── Panneau liste de courses — extrait de main.ts ──

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";

let currentShoppingList: string[] = [];

// Shopping Panel DOM refs
const shoppingPanel = document.getElementById("shopping-panel") as HTMLDivElement;
const shoppingCloseBtn = document.getElementById("shopping-panel-close-btn") as HTMLButtonElement;
const shoppingListContainer = document.getElementById("shopping-list-container") as HTMLDivElement;
const shoppingAddInput = document.getElementById("shopping-add-input") as HTMLInputElement;
const shoppingAddBtn = document.getElementById("shopping-add-btn") as HTMLButtonElement;
const shoppingClearBtn = document.getElementById("shopping-clear-btn") as HTMLButtonElement;
const shoppingHeader = document.getElementById("shopping-panel-header") as HTMLDivElement;
const shoppingCount = document.getElementById("shopping-count") as HTMLDivElement;


// ── LOGIQUE DU PANNEAU DE COURSES (SHOPPING PANEL) ───────────────────────────
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
  shoppingListContainer.innerHTML = "";
  const restants = currentShoppingList.filter(i => !i.startsWith("[x] ")).length;
  if (shoppingCount) {
    const total = currentShoppingList.length;
    shoppingCount.textContent = total === 0
      ? "LISTE VIDE"
      : `${total} ARTICLE${total > 1 ? "S" : ""}` + (restants < total ? ` · ${restants} À PRENDRE` : "");
  }
  if (shoppingClearBtn) shoppingClearBtn.disabled = currentShoppingList.length === 0;
  if (currentShoppingList.length === 0) {
    const empty = document.createElement("div");
    empty.className = "shopping-empty";
    empty.textContent = "AUCUN ARTICLE DANS LA LISTE";
    shoppingListContainer.appendChild(empty);
    return;
  }
  currentShoppingList.forEach((itemText) => {
    const isChecked = itemText.startsWith("[x] ");
    const cleanText = isChecked ? itemText.substring(4) : itemText;

    const div = document.createElement("div");
    div.className = `shopping-item${isChecked ? " checked" : ""}`;

    const cb = document.createElement("div");
    cb.className = "shopping-checkbox";
    cb.onclick = () => {
      const idx = currentShoppingList.indexOf(itemText);
      if (idx !== -1) {
        if (isChecked) {
          currentShoppingList[idx] = cleanText;
        } else {
          currentShoppingList[idx] = `[x] ${cleanText}`;
        }
        sendShoppingListToBackend();
      }
    };

    const textSpan = document.createElement("span");
    textSpan.className = "shopping-item-text";
    textSpan.textContent = cleanText;

    const del = document.createElement("button");
    del.className = "shopping-item-delete";
    del.innerHTML = "&times;";
    del.onclick = () => {
      currentShoppingList = currentShoppingList.filter(i => i !== itemText);
      sendShoppingListToBackend();
    };

    div.appendChild(cb);
    div.appendChild(textSpan);
    div.appendChild(del);
    shoppingListContainer.appendChild(div);
  });
}

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
