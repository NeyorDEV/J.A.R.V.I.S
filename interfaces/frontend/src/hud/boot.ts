import { hudState } from "./state";

let bootOrbSphereStop: (() => void) | null = null;

// ── Boot Sequence ─────────────────────────────────────────────────────────────
// Fait tourner en vraie 3D la sphère de points au centre de l'orbe (chaque
// point a ses coordonnées x/y/z d'origine en attributs data-*, générées une
// fois par script et figées dans le HTML). Rotation autour de l'axe Y :
// projection 2D + taille/opacité selon la profondeur (effet de volume).
export function initBootOrbSphere(): void {
  const dots = Array.from(document.querySelectorAll<SVGCircleElement>(".boot-orb-dot"));
  if (!dots.length) return;

  const points = dots.map((el) => ({
    el,
    x: parseFloat(el.dataset.x || "0"),
    y: parseFloat(el.dataset.y || "0"),
    z: parseFloat(el.dataset.z || "0"),
  }));

  const R = 26;
  const CX = 100, CY = 100;
  let angle = 0;

  // setInterval plutôt que requestAnimationFrame : un écran de démarrage doit
  // continuer de tourner même si la fenêtre perd le focus ou est masquée un
  // instant (rAF est mis en pause par le navigateur dans un onglet/fenêtre
  // en arrière-plan, ce qui gèlerait la sphère au pire moment).
  const intervalId = window.setInterval(() => {
    angle += 0.02;
    const cosA = Math.cos(angle), sinA = Math.sin(angle);
    for (const p of points) {
      const x = p.x * cosA - p.z * sinA;
      const z = p.x * sinA + p.z * cosA;
      const depth = (z + 1) / 2; // 0 = derriere, 1 = devant
      p.el.setAttribute("cx", (CX + x * R).toFixed(2));
      p.el.setAttribute("cy", (CY + p.y * R).toFixed(2));
      p.el.setAttribute("r", (0.5 + depth * 1.2).toFixed(2));
      p.el.style.opacity = (0.35 + depth * 0.65).toFixed(2);
    }
  }, 33);
  bootOrbSphereStop = () => window.clearInterval(intervalId);
}

export function runBootSequence(): void {
  const overlay     = document.getElementById("boot-overlay") as HTMLDivElement;
  const logoSection = document.getElementById("boot-logo-section") as HTMLDivElement;
  const statusText  = document.getElementById("boot-status-text") as HTMLDivElement;

  if (!overlay) return;

  // Durée d'affichage minimale : évite un flash désagréable si la connexion
  // WebSocket (souvent locale, quasi instantanée) répond avant même que le
  // logo ait fini son fondu d'entrée.
  const MIN_DISPLAY_MS = 1200;
  const bootStart = performance.now();

  function finishBoot() {
    const elapsed = performance.now() - bootStart;
    const wait = Math.max(0, MIN_DISPLAY_MS - elapsed);
    setTimeout(() => {
      // Le noyau du réacteur passe du cyan pulsant au vert stable : c'est
      // l'indicateur de progression, plus de barre séparée à animer.
      logoSection.classList.add("online");

      setTimeout(() => {
        // Retirer la protection anti-FOUC pour révéler l'interface
        document.body.classList.remove("loading");
        overlay.style.opacity = "0";
        setTimeout(() => { overlay.style.display = "none"; bootOrbSphereStop?.(); }, 900);
      }, 1100);
    }, wait);
  }

  if (hudState.wsConnectedBeforeBoot) {
    finishBoot();
  } else {
    hudState.bootConnectedCallback = finishBoot;
    // Sécurité : ferme le boot après 25 s si le serveur ne répond pas
    setTimeout(() => {
      if (hudState.bootConnectedCallback) {
        hudState.bootConnectedCallback = null;
        statusText.textContent = "CONNEXION INDISPONIBLE — POURSUITE HORS-LIGNE";
        document.body.classList.remove("loading");
        overlay.style.opacity = "0";
        setTimeout(() => { overlay.style.display = "none"; bootOrbSphereStop?.(); }, 900);
      }
    }, 25_000);
  }
}
