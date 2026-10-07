import { fermerHote, ouvrirDansHote, vueOuverte } from "../vues_3d";
import { hideCarouselArrow, showCarouselArrow } from "../ui/carousel";

// ── Vues 3D plein écran (explorateur, maison, cortex, échecs, radar) ─────────
// Remplace l'ancien mode hologramme : chaque vue s'ouvre directement (commande
// vocale ou message du backend), une seule à la fois. Le conteneur garde son id
// historique #holo-overlay, utilisé par les vues.

export type TypeVue3D = "explorer" | "domotic" | "cortex" | "chess" | "radar";

const overlay = document.getElementById("holo-overlay") as HTMLDivElement | null;

/** Affiche la vue demandée (en fermant l'autre) et renvoie son instance, ou null. */
export function ouvrirVue3D(type: TypeVue3D): any {
  if (overlay && overlay.style.display !== "block") {
    overlay.style.display = "block";
    const orbCanvas = document.getElementById("orb-canvas");
    if (orbCanvas) orbCanvas.style.display = "none";
    hideCarouselArrow();
  }
  const vue = ouvrirDansHote(type);
  if (!vue) fermerVues3D();
  return vue;
}

/** Ferme la vue ouverte et revient à l'interface JARVIS. */
export function fermerVues3D(): void {
  fermerHote();
  if (overlay) overlay.style.display = "none";
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) orbCanvas.style.display = "block";
  showCarouselArrow();
}

/** Vrai si une vue 3D est ouverte (ou cette vue précise, si `type` est donné). */
export function vue3DOuverte(type?: TypeVue3D): boolean {
  const v = vueOuverte();
  return !!v && (!type || v.type === type);
}

export function initVues3D(): void {
  // Utilisé par les vues elles-mêmes (bouton QUITTER des échecs, ✕ du radar)
  (window as any)._fermerVues3D = fermerVues3D;
  document.getElementById("holo-close-btn")?.addEventListener("click", fermerVues3D);
}
