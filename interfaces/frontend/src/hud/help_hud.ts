import { helpOverlayEl } from "./dom_refs";

// ── Aide : palette de commandes ──────────────────────────────────────────────
// #help-overlay ne porte plus que l'état affiché / masqué (classe « visible ») : le contenu — catégories, recherche, liste, détail —
// est fait de pièces éclatées (pieces_outils.ts), construites d'après l'index de hud/aide_commandes.ts. Ouverture : entrée AIDE du
// menu en roue, commande vocale « aide », Ctrl+K.

export function hideHelpHUD() {
  if (!helpOverlayEl) return;
  // On pilote la classe : le CSS #help-overlay.visible porte un display !important
  // qu'un simple style.display = "none" inline ne peut pas battre.
  helpOverlayEl.classList.remove("visible");
  helpOverlayEl.classList.add("hidden");
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
}

export function showHelpHUD() {
  if (!helpOverlayEl) return;
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
  helpOverlayEl.classList.remove("hidden");
  helpOverlayEl.classList.add("visible");
}
