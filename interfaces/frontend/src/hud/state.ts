// ── État partagé du HUD (ex-variables globales de main.ts) ─────────────────────
// Toujours y accéder via « hudState.xxx » : une variable « export let » est en
// lecture seule pour les modules qui l'importent, d'où cet objet mutable.
export const hudState = {
  // Boot sequence state
  bootConnectedCallback: null as (() => void) | null,
  wsConnectedBeforeBoot: false,
  subtitlesEnabled: true,
  keyboardEnabled: false,
};
