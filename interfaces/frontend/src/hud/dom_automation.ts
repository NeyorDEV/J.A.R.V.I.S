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
      cursor.getBoundingClientRect();
    }

    const coords = await getElementCoordinates(element);

    setTimeout(() => {
      cursor.style.left = `${coords.x}px`;
      cursor.style.top = `${coords.y}px`;
      
      setTimeout(resolve, 800);
    }, 50);
  });
}

// ── DOM Automation Queue to prevent race conditions ───────────────────────────
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

// File d'actions DOM : une par connexion WebSocket, comme dans l'ancien connect().
export function createDomActionQueue(): (domAction: any) => void {
  const domActionQueue: any[] = [];
  let domActionProcessing = false;

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

  return (domAction: any) => {
    domActionQueue.push(domAction);
    processDomActionQueue();
  };
}
