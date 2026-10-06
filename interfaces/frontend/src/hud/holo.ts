import { activerHolo, desactiverHolo } from "../hologramme";
import { holoButtonEl } from "./dom_refs";
import { hideCarouselArrow, showCarouselArrow } from "../ui/carousel";

// ── Hologramme mode toggle ────────────────────────────────────────────────────
export let _holoActive = false;
const _holoOverlay = document.getElementById("holo-overlay") as HTMLDivElement;

export function _openHolo() {
  _holoActive = true;
  if (_holoOverlay) _holoOverlay.style.display = "block";
  if (holoButtonEl) holoButtonEl.setAttribute("aria-pressed", "true");
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) orbCanvas.style.display = "none";
  hideCarouselArrow();
  activerHolo();
}

export function _closeHolo() {
  _holoActive = false;
  desactiverHolo();
  if (_holoOverlay) _holoOverlay.style.display = "none";
  if (holoButtonEl) holoButtonEl.setAttribute("aria-pressed", "false");
  const orbCanvas = document.getElementById("orb-canvas");
  if (orbCanvas) orbCanvas.style.display = "block";
  showCarouselArrow();
}

export function initHolo(): void {
  (window as any)._openHolo = _openHolo;
  (window as any)._closeHolo = _closeHolo;

  // Écouteur direct de #holo-button supprimé : doublon du dispatcher du carrousel
  // (double bascule par clic → ouverture/fermeture immédiate, donc « ne marche pas »).
  document.getElementById("holo-close-btn")?.addEventListener("click", _closeHolo);
}
