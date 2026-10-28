// ── Jeton de l'extension de navigateur (Paramètres › Sécurité) ───────────────────────────────
// Le backend (core/extension_bridge.py) n'accepte une extension que si elle présente ce jeton.
import { wsRef } from "../ws_link";

let jeton = "";

function demander(): void {
  const ws = wsRef.current;
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "get_extension_token" }));
}

export function handleExtensionTokenMessage(data: any): boolean {
  if (data.type !== "extension_token") return false;
  jeton = String(data.token || "");
  const champ = document.getElementById("settings-ext-jeton") as HTMLInputElement | null;
  if (champ) champ.value = jeton;
  return true;
}

export function initExtensionJeton(): void {
  const champ = document.getElementById("settings-ext-jeton") as HTMLInputElement | null;
  const etat = document.getElementById("settings-ext-etat");
  if (!champ) return;
  document.querySelector('.settings-nav-item[data-panel="securite"]')?.addEventListener("click", demander);
  document.getElementById("settings-ext-afficher")?.addEventListener("click", (e) => {
    const visible = champ.type === "text";
    champ.type = visible ? "password" : "text";
    (e.currentTarget as HTMLButtonElement).textContent = visible ? "Afficher" : "Masquer";
  });
  document.getElementById("settings-ext-copier")?.addEventListener("click", async () => {
    if (!jeton) {
      demander();
      return;
    }
    try {
      await navigator.clipboard.writeText(jeton);
      if (etat) { etat.textContent = "Jeton copié."; etat.className = "maj-etat maj-ok"; }
    } catch {
      champ.type = "text";
      champ.select();
      if (etat) { etat.textContent = "Copie impossible ici : sélectionnez le jeton et copiez-le avec Ctrl+C."; etat.className = "maj-etat maj-ko"; }
    }
  });
}
