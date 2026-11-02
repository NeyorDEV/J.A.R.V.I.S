import { fermerHote, ouvrirDansHote, vueOuverte } from "../vues_3d";
import { hideCarouselArrow, showCarouselArrow } from "../ui/carousel";
import { fermerPleinEcran, ouvrirPleinEcran } from "./plein_ecran";

// ── Vues 3D plein écran (explorateur, maison, cortex, échecs, radar) ─────────
// Remplace l'ancien mode hologramme : chaque vue s'ouvre directement (commande
// vocale ou message du backend), une seule à la fois. Le conteneur garde son id
// historique #holo-overlay, utilisé par les vues.

export type TypeVue3D = "explorer" | "domotic" | "cortex" | "chess" | "radar";

const overlay = document.getElementById("holo-overlay") as HTMLDivElement | null;
let fermeture = false;   // la vue se rétracte dans le cylindre
// Fiche de la roue du cylindre (orb_themes.ts) d'où sort chaque vue
const MODULES: Record<TypeVue3D, [string, string]> = {
  chess: ["JEUX ET 3D", "Échecs"], explorer: ["JEUX ET 3D", "Explorateur"], domotic: ["JEUX ET 3D", "Maison 3D"],
  cortex: ["JEUX ET 3D", "Cortex"], radar: ["JEUX ET 3D", "Radar réseau"],
};

/** Affiche la vue demandée (en fermant l'autre) et renvoie son instance, ou null. */
export function ouvrirVue3D(type: TypeVue3D): any {
  if (overlay && overlay.style.display !== "block") {
    overlay.style.display = "block";
    hideCarouselArrow();
    // la vue sort du cylindre ; l'orbe n'est masqué qu'une fois la vue étendue par-dessus
    ouvrirPleinEcran("vue3d", overlay, MODULES[type], () => {
      const orbCanvas = document.getElementById("orb-canvas");
      if (orbCanvas) orbCanvas.style.display = "none";
    });
  }
  const vue = ouvrirDansHote(type);
  if (!vue) fermerVues3D();
  return vue;
}

/** Ferme la vue ouverte : elle se rétracte dans le cylindre, puis on revient à l'interface JARVIS. */
export function fermerVues3D(): void {
  if (!overlay || overlay.style.display !== "block") { fermerHote(); showCarouselArrow(); return; }
  if (fermeture) return;
  fermeture = true;
  showCarouselArrow();
  fermerPleinEcran("vue3d", overlay, () => {
    fermerHote();
    overlay.style.display = "none";
    fermeture = false;
  }, () => {
    const orbCanvas = document.getElementById("orb-canvas");
    if (orbCanvas) orbCanvas.style.display = "block";
  });
  // fermée avant d'avoir fini de s'ouvrir : l'orbe n'a jamais été masqué
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
