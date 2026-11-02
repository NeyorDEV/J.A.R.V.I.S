// ── Actions DOM envoyées par le backend (plugins/dom_controller_resolver.py, send_web_action) ───────────────────
// Exécutées directement, une par une : pas de curseur animé (il volait vers l'élément avant de cliquer, et partait
// dans le vide quand l'élément était caché).

const pause = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

// ── File d'actions DOM, pour éviter les courses entre actions successives ────────────────────────────────────
async function executeSingleDomAction(domAction: any): Promise<void> {
  // Cas dom_sequence : exécuter chaque step dans l'ordre avec délai
  if (domAction.action === "dom_sequence") {
    const steps: any[] = domAction.steps || [];
    for (const step of steps) {
      await pause((step.delay || 0.5) * 1000);
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

  if (domAction.action === "click") {
    element.click();
    await pause(300);
  } else if (domAction.action === "type") {
    element.focus();
    const text = domAction.text || "";
    const input = element as HTMLInputElement;
    input.value = "";
    for (let i = 0; i < text.length; i++) {
      input.value += text[i];
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
      await pause(40);
    }
    await pause(200);
  } else if (domAction.action === "focus") {
    element.focus();
    await pause(200);
  } else if (domAction.action === "select") {
    (element as HTMLSelectElement).value = domAction.text || "";
    element.dispatchEvent(new Event("change", { bubbles: true }));
    await pause(200);
  } else if (domAction.action === "add_class") {
    element.classList.add(domAction.class_name || "");
  } else if (domAction.action === "remove_class") {
    element.classList.remove(domAction.class_name || "");
  }
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
