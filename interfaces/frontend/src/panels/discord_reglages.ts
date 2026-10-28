// ── Réglages Discord (Paramètres › Discord) : salons, jeton du bot, envoi en mon nom ─────────────
// Le backend (module/discord_service.py) ne renvoie jamais une adresse de webhook en clair :
// une ligne dont l'adresse est masquée est conservée telle quelle à l'enregistrement.
import { wsRef } from "../ws_link";

const MASQUE_BOT = "••••••••••••";

function elements() {
  return {
    salons: document.getElementById("settings-discord-salons") as HTMLTextAreaElement | null,
    bot: document.getElementById("settings-discord-bot") as HTMLInputElement | null,
    ui: document.getElementById("settings-discord-ui") as HTMLInputElement | null,
    etat: document.getElementById("settings-discord-etat"),
  };
}

/** Lu sans être consommé : remplit les champs quand les réglages arrivent. */
export function handleDiscordSettings(data: any): boolean {
  if (data.type !== "settings_data" || !data.data) return false;
  const { salons, bot, ui } = elements();
  const s = data.data.discord_salons && typeof data.data.discord_salons === "object" ? data.data.discord_salons : {};
  if (salons) salons.value = Object.entries(s).map(([nom, valeur]) => `${nom} = ${valeur}`).join("\n");
  if (bot) bot.value = data.data.api_keys?.DISCORD_BOT_TOKEN || "";
  if (ui) ui.checked = data.data.discord_envoi_ui === true;
  return false;
}

export function initDiscordReglages(): void {
  const { salons, bot, ui, etat } = elements();
  document.getElementById("settings-discord-save")?.addEventListener("click", () => {
    if (!salons || !bot || !ui) return;
    const liste: Record<string, string> = {};
    for (const ligne of salons.value.split("\n")) {
      const i = ligne.indexOf("=");
      const nom = (i < 0 ? "" : ligne.slice(0, i)).trim();
      const valeur = (i < 0 ? "" : ligne.slice(i + 1)).trim();
      if (nom && valeur) liste[nom] = valeur;
    }
    const reglages: Record<string, unknown> = { discord_salons: liste, discord_envoi_ui: ui.checked };
    const jeton = bot.value.trim();
    if (jeton && !jeton.startsWith(MASQUE_BOT.slice(0, 4))) reglages.api_keys = { DISCORD_BOT_TOKEN: jeton };
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "update_settings", settings: reglages }));
      ws.send(JSON.stringify({ type: "get_settings" })); // rafraîchit l'affichage (adresses masquées)
      if (etat) { etat.textContent = "Réglages Discord enregistrés (les lignes invalides sont ignorées)."; etat.className = "maj-etat maj-ok"; }
    } else if (etat) {
      etat.textContent = "JARVIS n'est pas connecté.";
      etat.className = "maj-etat maj-ko";
    }
  });
}
