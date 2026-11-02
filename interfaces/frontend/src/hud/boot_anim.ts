// Séquence d'initialisation (écran de chargement), en lignes fines comme le reste du HUD : les modules se connectent
// un à un autour de l'anneau de progression. Le cylindre n'est pas redessiné ici : c'est celui de l'orbe lui-même (son
// canvas, visible sous cet écran) : une bande monte avec la progression, à 100 % il se dresse tout entier, reste allumé
// un instant, puis se referme en disque de veille ; le HUD réel prend alors le relais en fondu.
// Le temps de la séquence (« t », en secondes de conception) avance plus vite que le temps réel ; il s'arrête à
// PORTE (100 %) tant que le serveur n'a pas répondu, puis la séquence se termine d'elle-même (rappel `fini`).

import { orb } from "./orb_state";

const TAU = Math.PI * 2, K = 0.22;
const VITESSE = 9.2 / 5;         // secondes de conception par seconde réelle (5 s en tout)
const PORTE = 4.4;               // la séquence attend ici (100 %) la connexion au serveur
const REVELE = 8.5;              // le HUD réel apparaît en fondu (rappel `fini`) alors que le disque de veille se dessine
const FIN = 9.2;
const HF = 345, HB = 58;   // hauteur du cylindre de l'orbe ouvert, et de la bande pendant le chargement
const C = "80,165,255", GR = "120,255,190", WH = "235,248,255", BL = "70,150,255";
const MODULES = ["VOIX", "VISION", "MÉMOIRE", "CERVEAU", "DOMOTIQUE", "RÉSEAU", "MUSIQUE"];
const FONT = `"Orbitron",system-ui,sans-serif`;

const cl = (x: number, a = 0, b = 1): number => Math.max(a, Math.min(b, x));
const seg = (t: number, a: number, b: number): number => cl((t - a) / (b - a));
const eio = (x: number): number => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const eo = (x: number): number => 1 - Math.pow(1 - x, 3);

export interface BootAnim {
  /** Le serveur a répondu : la séquence reprend et se termine. */
  connecte(): void;
  /** Message affiché à la place de la ligne d'état (ex. connexion indisponible). */
  message(texte: string): void;
  stop(): void;
}

export function demarrerAnimationBoot(canvas: HTMLCanvasElement, fini: () => void): BootAnim {
  const g = canvas.getContext("2d")!;
  const lettres = g as any;
  let dpr = 1, w = 0, h = 0;
  let t = 0, ta = 0, connecte = false, termine = false, revele = false, msg = "";
  let dernier = performance.now(), attenteDepuis = -1;
  let orbeOuvert = false, orbeFerme = false;
  const orbCanvas = document.getElementById("orb-canvas") as HTMLCanvasElement | null;
  if (orbCanvas) { orbCanvas.style.opacity = "0"; window.setTimeout(() => { orbCanvas.style.opacity = "1"; }, 300); }

  const taille = (): void => {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
  };
  taille();
  window.addEventListener("resize", taille);
  try { void (document as any).fonts?.load(`12px Orbitron`); } catch { /* police de repli */ }

  const txt = (s: string, x: number, y: number, px: number, col: string, a: number, al: CanvasTextAlign = "center", ls = 0): void => {
    if (a <= 0.01) return;
    g.font = `400 ${px}px ${FONT}`; g.textAlign = al; g.textBaseline = "middle"; g.fillStyle = `rgba(${col},${a})`;
    if ("letterSpacing" in g) lettres.letterSpacing = ls + "px";
    g.fillText(s, x, y);
    if ("letterSpacing" in g) lettres.letterSpacing = "0px";
  };
  const lueur = (x: number, y: number, r: number, col: string, a: number): void => {
    if (a <= 0.005) return;
    const q = g.createRadialGradient(x, y, 0, x, y, r);
    q.addColorStop(0, `rgba(255,255,255,${a})`); q.addColorStop(0.3, `rgba(${col},${a * 0.5})`); q.addColorStop(1, `rgba(${col},0)`);
    g.fillStyle = q; g.fillRect(x - r, y - r, r * 2, r * 2);
  };
  // arc d'ellipse (centre à l'origine, aplatie par K) du sommet, sur la fraction f du tour
  const ell = (rx: number, f: number, col: string, a: number, lw: number, dec = 0): void => {
    if (f <= 0 || a <= 0.005) return;
    g.beginPath(); g.ellipse(0, 0, rx, rx * K, 0, -Math.PI / 2 + dec, -Math.PI / 2 + dec + TAU * f);
    g.strokeStyle = `rgba(${col},${a})`; g.lineWidth = lw; g.stroke();
  };

  function dessiner(): void {
    // ── placement identique à celui de l'orbe : centre à la moitié de la largeur, base à 74 % de la hauteur
    const baseY = h * 0.74;
    const s = cl(Math.min((baseY - 130) / (HF + 50), w / 1000), 0.45, 1.6);

    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.globalCompositeOperation = "source-over"; g.globalAlpha = 1;
    g.clearRect(0, 0, w, h);   // transparent : le fond et le cylindre sont ceux de l'orbe, dessous
    const globale = 1 - seg(t, 8.7, 9.2);
    g.globalAlpha = globale;

    // ── phases
    const lp = seg(t, 1.3, 4.4), pr = eio(lp) * 0.3 + lp * 0.7, fait = t >= 4.4;
    const progA = 1 - seg(t, 4.6, 5.6), cardsA = 1 - seg(t, 4.4, 5.0);
    const lvl = fait ? 1 : pr;

    // ── le vrai cylindre de l'orbe : bande qui monte avec la progression, dressé à 100 %, puis refermé en disque de veille
    if (!orbeOuvert && t < 7.4) { orbeOuvert = true; orb?.setMenu(true); }
    orb?.setMenuHauteur(t >= 7.4 ? 0 : fait && t >= 4.7 ? 1 : (HB / HF) * lvl);
    if (!orbeFerme && t >= 7.4) { orbeFerme = true; orb?.setMenu(false); }

    // ── monde : origine au centre du socle, échelle de l'orbe
    g.setTransform(dpr * s, 0, 0, dpr * s, dpr * w / 2, dpr * baseY);
    g.globalCompositeOperation = "lighter";

    // anneau de progression
    if (progA > 0.01) {
      ell(190, 1, C, 0.1 * progA, 0.6);
      ell(190, lp > 0 ? pr : 0, GR, 0.8 * progA, 1);
      if (lp > 0 && !fait) { const ha = -Math.PI / 2 + TAU * pr; lueur(Math.cos(ha) * 190, Math.sin(ha) * 190 * K, 14, GR, 0.8); }
    }

    // ── modules : cartes de verre reliées à un nœud de l'anneau
    if (cardsA > 0.01) MODULES.forEach((m, i) => {
      const th = i / MODULES.length * TAU + 0.55, cx = 310 * Math.cos(th), cy = 105 * Math.sin(th) - 28;
      const nx = 190 * Math.cos(th), ny = 190 * K * Math.sin(th);
      const t0 = 1.3 + i * 0.4, ap = eo(seg(t, t0 - 0.4, t0 + 0.1)) * cardsA, ok = t > t0 + 0.5;
      if (ap <= 0.01) return;
      const mx = (cx + nx) / 2, my = Math.min(cy, ny) - 14;
      g.beginPath(); g.moveTo(cx, cy + (cy < ny ? 15 : -15)); g.quadraticCurveTo(mx, my, nx, ny);
      g.strokeStyle = `rgba(${ok ? GR : C},${0.35 * ap})`; g.lineWidth = 0.6; g.stroke();
      const on = seg(t, t0, t0 + 0.5);
      g.beginPath(); g.arc(nx, ny, 2.2, 0, TAU); g.fillStyle = `rgba(${ok ? GR : C},${(0.3 + 0.7 * on) * ap})`; g.fill();
      if (t > t0 && t < t0 + 0.9) { const q = seg(t, t0, t0 + 0.9); g.beginPath(); g.ellipse(nx, ny, 3 + q * 16, (3 + q * 16) * K * 2, 0, 0, TAU); g.strokeStyle = `rgba(${GR},${0.7 * (1 - q) * ap})`; g.lineWidth = 0.6; g.stroke(); }
      g.beginPath(); g.roundRect(cx - 46, cy - 15, 92, 30, 9);
      g.fillStyle = `rgba(${C},${0.05 * ap})`; g.fill();
      g.strokeStyle = `rgba(${ok ? GR : C},${(ok ? 0.55 : 0.32) * ap})`; g.lineWidth = 0.7; g.stroke();
      txt(m, cx, cy - 3.5, 8.5, ok ? WH : C, (ok ? 0.95 : 0.6) * ap, "center", 1.2);
      txt(ok ? "EN LIGNE" : t > t0 ? "INITIALISATION" : "EN ATTENTE", cx, cy + 8, 5.5, ok ? GR : C, (ok ? 0.9 : 0.55) * ap, "center", 1.2);
    });

    // pourcentage au-dessus de la bande
    g.globalCompositeOperation = "source-over";
    txt(Math.round(pr * 100) + " %", 0, -HB - 50 * 1, 16, WH, 0.9 * progA * eo(seg(t, 1.2, 1.8)), "center", 4);

    // ── repères à l'écran : équerres, titre, barre, ligne d'état
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const cn = eo(seg(t, 0.1, 1.2)), L = 26 * cn, cA = 0.4 * (1 - seg(t, 7.4, 8.6));
    g.strokeStyle = `rgba(${C},${cA})`; g.lineWidth = 0.8;
    for (const [x, y, sx, sy] of [[22, 22, 1, 1], [w - 22, 22, -1, 1], [22, h - 22, 1, -1], [w - 22, h - 22, -1, -1]]) {
      g.beginPath(); g.moveTo(x, y + sy * L); g.lineTo(x, y); g.lineTo(x + sx * L, y); g.stroke();
    }
    const tA = eo(seg(t, 0.3, 1.2)) * (1 - seg(t, 7, 8));
    txt("J.A.R.V.I.S", w / 2 + 7, 96, 28, WH, tA, "center", 14);
    const bA = eo(seg(t, 1, 1.6)) * progA;
    if (bA > 0.01) {
      const bw = 420, x0 = w / 2 - bw / 2, y = h - 100;
      g.fillStyle = `rgba(${C},${0.15 * bA})`; g.fillRect(x0, y, bw, 1);
      g.fillStyle = `rgba(${GR},${0.9 * bA})`; g.fillRect(x0, y, bw * pr, 1);
    }
    const attendu = !connecte && fait && attenteDepuis >= 0 && ta - attenteDepuis > 1.5;
    const etat = msg ? msg : attendu ? "CONNEXION AU SERVEUR…" : t < 1.3 ? "ALIMENTATION" : t < 4.4 ? "CONNEXION DES MODULES" : t < 7.4 ? "SYSTÈMES EN LIGNE" : "MISE EN VEILLE";
    const ecol = msg ? "255,170,110" : t >= 7.4 ? BL : fait ? GR : C;
    txt(etat, w / 2 + 3, h - 70, 13, ecol, 0.85 * eo(seg(t, 0.3, 1)), "center", 6);
  }

  // setInterval plutôt que requestAnimationFrame : l'écran de démarrage doit continuer d'avancer même si la
  // fenêtre est masquée un instant (rAF est suspendu et gèlerait la séquence au pire moment).
  const id = window.setInterval(() => {
    const maintenant = performance.now(), dt = Math.min(0.1, (maintenant - dernier) / 1000);
    dernier = maintenant;
    ta += dt * VITESSE;
    if (!termine) {
      t += dt * VITESSE;
      if (!connecte && t >= PORTE) { t = PORTE; if (attenteDepuis < 0) attenteDepuis = ta; }
      if (t >= REVELE && !revele) { revele = true; fini(); }
      if (t >= FIN) { termine = true; t = FIN; }
    }
    dessiner();
  }, 16);

  return {
    connecte: () => { connecte = true; },
    message: (texte) => { msg = texte; },
    stop: () => {
      window.clearInterval(id); window.removeEventListener("resize", taille);
      if (orbCanvas) orbCanvas.style.opacity = "";
      orb?.setMenuHauteur(1); orb?.setMenu(false);
    },
  };
}
