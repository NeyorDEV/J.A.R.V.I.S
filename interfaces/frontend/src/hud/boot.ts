import { hudState } from "./state";
import { demarrerAnimationBoot } from "./boot_anim";

// ── Séquence de démarrage ─────────────────────────────────────────────────────
// L'animation (boot_anim.ts) dure environ 7 s ; elle attend la connexion réelle au serveur WebSocket avant sa
// dernière partie (le réacteur devient le socle du cylindre), puis rend la main à l'interface qui apparaît.
export function runBootSequence(): void {
  const overlay = document.getElementById("boot-overlay") as HTMLDivElement;
  const canvas = document.getElementById("boot-canvas") as HTMLCanvasElement;
  if (!overlay || !canvas) return;

  let anim: ReturnType<typeof demarrerAnimationBoot> | null = null;
  let ferme = false;

  const reveler = (): void => {
    if (ferme) return;
    ferme = true;
    // Retirer la protection anti-FOUC pour révéler l'interface sous l'écran de démarrage qui s'efface
    document.body.classList.remove("loading");
    overlay.style.opacity = "0";
    setTimeout(() => { overlay.style.display = "none"; anim?.stop(); }, 900);
  };

  anim = demarrerAnimationBoot(canvas, reveler);

  if (hudState.wsConnectedBeforeBoot) {
    anim.connecte();
  } else {
    hudState.bootConnectedCallback = () => anim?.connecte();
    // Sécurité : ferme le boot après 25 s si le serveur ne répond pas
    setTimeout(() => {
      if (hudState.bootConnectedCallback) {
        hudState.bootConnectedCallback = null;
        anim?.message("CONNEXION INDISPONIBLE — POURSUITE HORS-LIGNE");
        setTimeout(reveler, 1500);
      }
    }, 25_000);
  }
}
