/**
 * Orbe de JARVIS : cylindre holographique (canvas 2D), inspiré d'une borne holographique.
 *
 * États (OrbState du backend) :
 *   idle      → disque posé au sol, anneaux au repos
 *   listening → le cylindre se dresse, vide ; colonnes de pixels lentes qui montent du socle
 *   thinking  → la sélection parcourt les fiches (modules), ralentit et se verrouille sur la bonne
 *   speaking  → la fiche trouvée sort du cylindre et s'affiche à gauche ; ondes douces au sol
 *   searching → le cylindre s'étire en écran panoramique
 *
 * Même interface que l'ancien orbe (setState, setVolume, setAnalyser…) : le reste du HUD n'a pas changé.
 */

import { CATEGORIES, DEFAUT, choisir } from "./orb_themes";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "searching";

export interface Orb {
  setState(s: OrbState): void;
  setVolume(v: number): void;
  setAnalyser(a: AnalyserNode | null): void;
  triggerDemo(): void;
  writeWord(w: string): void;
  setTheme(t: string): void;
  /** Dernière phrase prononcée ou saisie : sert à choisir la fiche « trouvée ». */
  noteText(t: string): void;
  /** Ouvre le cylindre en écran tant qu'au moins une « raison » est active ; l'écran prend la taille de l'élément (panneau) donné. */
  setOuvert(raison: string, ouvert: boolean, element?: HTMLElement, centre?: boolean): void;
  /** Joue la recherche de la fiche (défilement, arrêt sur le thème de `texte`, envol à gauche) puis rend la main : l'appelant ouvre ensuite l'écran. */
  chercher(texte?: string): Promise<void>;
  /** Écran presque entièrement ouvert (les widgets attendent ce moment pour apparaître). */
  ecranOuvert(): boolean;
  /** Position (pixels écran) où poser un élément pour qu'il occupe l'écran du cylindre. */
  emplacement(element: HTMLElement): { left: number; top: number };
  destroy(): void;
}

type Item = [string, string];
type Mode = "veille" | "ecoute" | "reflexion" | "parole" | "ouvert";
interface Cible { h: number; cards: number; panels: number; open: number; spec: number; fast: number; voice: number }
interface Colonne { r: number; th: number; sp: number; ph: number; w: number }

const W = 900, CX = 450, BY = 452, TAU = Math.PI * 2, RX = 108, HF = 345, TOP0 = BY - HF, NL = 130, PLX = 44;
const TIERS = [1.06, 0.94, 0.82, 0.7, 0.58, 0.44, 0.3];
// Rotation de teinte appliquée au canvas pour les styles de l'orbe (le style « cyan » est la teinte d'origine)
export const TEINTES: Record<string, number> = { cyan: 0, default: 0, emerald: -50, amber: -165, red: -200, gold: -150, anneaux: 70 };

const hash = (n: number): number => { const x = Math.sin(n * 127.1) * 43758.5453; return x - Math.floor(x); };
const cl = (v: number, a: number, b: number): number => (v < a ? a : v > b ? b : v);
const sm = (v: number): number => { v = cl(v, 0, 1); return v * v * (3 - 2 * v); };
const A = (c: string, a: number): string => `rgba(${c},${a})`;
const sansAccent = (s: string): string => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

const CIBLES: Record<Mode, Cible> = {
  veille: { h: 0, cards: 0, panels: 0, open: 0, spec: 0, fast: 0, voice: 0 },
  ecoute: { h: 1, cards: 0, panels: 1, open: 0, spec: 1, fast: 0, voice: 0 },
  reflexion: { h: 1, cards: 1, panels: 1, open: 0, spec: 0, fast: 1, voice: 0 },
  parole: { h: 1, cards: 1, panels: 1, open: 0, spec: 0, fast: 0, voice: 1 },
  ouvert: { h: 1, cards: 0, panels: 0, open: 1, spec: 0, fast: 0, voice: 0.6 },
};
const MODE_DE_ETAT: Record<OrbState, Mode> = { idle: "veille", listening: "ecoute", thinking: "reflexion", speaking: "parole", searching: "ouvert" };

export function createOrb(canvas: HTMLCanvasElement): Orb {
  const g = canvas.getContext("2d") as CanvasRenderingContext2D;
  const dots: number[][] = [];
  const colonnes: Colonne[] = [];
  for (let i = 0; i < 420; i++) dots.push([(i / 420) * TAU, hash(i) - 0.5, hash(i + 9) * 1.6 + 0.5, hash(i + 3) * TAU]);
  for (let i = 0; i < 72; i++) colonnes.push({ r: Math.sqrt(hash(i * 3.7)) * 0.9, th: hash(i * 8.3) * TAU, sp: 0.1 + 0.17 * hash(i * 2.1), ph: hash(i * 6.1) * TAU, w: 2.5 + hash(i) * 3.5 });

  const P = { h: 0, cards: 0, panels: 0, open: 0, spec: 0, fast: 0, voice: 0, info: 0 };
  let mode: Mode = "veille";
  let cible: Cible = CIBLES.veille;
  let tSeq = 0;             // début de la séquence « recherche de la fiche » (s) : continue de réflexion à parole
  let tempoVeille: ReturnType<typeof setTimeout> | null = null;
  let rechercheForcee = false;  // recherche jouée à la demande (widget) : l'état du backend ne la coupe pas
  let cibleCat = DEFAUT, cibleSous = 0;  // catégorie et sous-catégorie trouvées pour la phrase en cours
  let volume = 0;
  let micNiveau = 0;
  let analyser: AnalyserNode | null = null;
  let analyseData: Uint8Array<ArrayBuffer> | null = null;
  let mot: { texte: string; fin: number } | null = null;

  // Recherche en deux temps : une roue pour les catégories, puis une pour les sous-catégories. La liste part avec son premier
  // élément en haut de la roue et défile toujours dans le même sens ; plus la cible est loin, plus la roue dure.
  const NV = 7;  // éléments visibles à la fois
  const distanceRoue = (n: number, visee: number): number => { const d = ((visee - (Math.min(n, NV) - 1) / 2) % n + n) % n; return d < 1 ? d + n : d; };
  function sequence(): { d1: number; d2: number; T: number } {
    const d1 = Math.min(1.75, 0.63 + distanceRoue(CATEGORIES.length, cibleCat) * 0.086);
    const d2 = Math.min(1.75, 0.63 + distanceRoue(CATEGORIES[cibleCat].sous.length, cibleSous) * 0.086);
    return { d1, d2, T: d1 + 0.35 + d2 + 0.35 };
  }
  let demoTimers: ReturnType<typeof setTimeout>[] = [];
  let etatBackend: OrbState = "idle";
  const raisonsOuvert = new Map<string, { el: HTMLElement | null; centre: boolean }>();
  // Un élément « centré » se pose dans l'écran du cylindre : centré sur sa colonne, bas de l'écran au-dessus du socle
  const emplacementCentre = (el: HTMLElement): { left: number; top: number } => {
    const basPx = origY + (BY - 62) * echelle;
    return { left: Math.round(largeur / 2 - el.offsetWidth / 2), top: Math.round(Math.max(34, basPx - el.offsetHeight)) };
  };
  let echelle = 1, origX = 0, origY = 0;  // passage de l'écran (pixels) au repère de l'orbe, mis à jour à chaque image
  const ecran = { demi: W * 0.46, top: BY - HF, bas: BY - 62 };  // taille lissée de l'écran ouvert
  let raf = 0;
  let largeur = 0, hauteur = 0, dpr = 1;

  const ell = (cx: number, cy: number, rx: number, ry: number, a0 = 0, a1 = TAU): void => {
    g.beginPath(); g.ellipse(cx, cy, Math.max(rx, 0.1), Math.max(ry, 0.1), 0, a0, a1);
  };

  function rings(cy: number, rx0: number, ry0: number, a: number, t: number, dir: number, ouv: number): void {
    // dir > 0 : anneau du haut (les cercles intérieurs descendent en escalier) ; dir < 0 : socle (ils montent en escalier)
    const f = 1 - ouv * 0.1, st = dir * 2.4 * (1 - ouv), wh = Math.abs(st), rim = 15 * (1 - ouv * 0.5), RR = rx0 * TIERS[0] * f, RY = ry0 * TIERS[0] * f;
    for (let i = 0; i < TIERS.length - 1; i++) {
      const m = TIERS[i] * f, m2 = TIERS[i + 1] * f, o1 = i * st, o2 = (i + 1) * st;
      g.beginPath();
      g.moveTo(CX + rx0 * m, cy + o1); g.ellipse(CX, cy + o1, rx0 * m, ry0 * m, 0, 0, TAU);
      g.moveTo(CX + rx0 * m2, cy + o2); g.ellipse(CX, cy + o2, rx0 * m2, ry0 * m2, 0, 0, TAU);
      g.fillStyle = A(i === 0 ? "40,120,255" : i % 2 ? "30,100,255" : "15,60,225", a * (i === 0 ? 0.2 : 0.16 + 0.05 * (i % 2)));
      g.fill("evenodd");
    }
    // Marches : chaque cercle intérieur a sa paroi (moitié arrière vue d'en haut, moitié avant vue du socle)
    const [p0, p1] = dir > 0 ? [Math.PI, TAU] : [0, Math.PI];
    for (let i = 1; i < TIERS.length; i++) {
      const rxw = rx0 * TIERS[i] * f, ryw = ry0 * TIERS[i] * f, y = cy + i * st;
      const pg = g.createLinearGradient(0, y - ryw, 0, y + wh + ryw);
      pg.addColorStop(0, A("70,160,255", 0.42 * a)); pg.addColorStop(1, A("20,70,230", 0.1 * a));
      g.beginPath(); g.ellipse(CX, y, rxw, ryw, 0, p0, p1, false); g.ellipse(CX, y + wh, rxw, ryw, 0, p1, p0, true); g.closePath();
      g.fillStyle = pg; g.fill();
      g.lineWidth = 0.5;
      for (let k = 0; k <= 26; k++) {
        const an = p0 + ((p1 - p0) * k) / 26, x = CX + rxw * Math.cos(an), yy = y + ryw * Math.sin(an);
        g.strokeStyle = A("150,215,255", a * 0.22); g.beginPath(); g.moveTo(x, yy); g.lineTo(x, yy + wh); g.stroke();
      }
      g.strokeStyle = A("60,150,255", 0.55 * a); g.beginPath(); g.ellipse(CX, y + wh, rxw, ryw, 0, p0, p1, false); g.stroke();
    }
    g.shadowColor = "#2a7bff"; g.shadowBlur = 14;
    const wg = g.createLinearGradient(0, cy - rim, 0, cy + RY);
    wg.addColorStop(0, A("70,160,255", 0.42 * a)); wg.addColorStop(1, A("25,80,235", 0.12 * a));
    g.beginPath(); g.ellipse(CX, cy - rim, RR, RY, 0, 0, Math.PI, false); g.lineTo(CX - RR, cy); g.ellipse(CX, cy, RR, RY, 0, Math.PI, 0, true); g.closePath();
    g.fillStyle = wg; g.fill();
    g.lineWidth = 1;
    for (let j = 0; j <= 70; j++) {
      const an = (j / 70) * Math.PI, x = CX + RR * Math.cos(an), s = Math.sin(an);
      g.strokeStyle = A("150,215,255", a * (0.12 + 0.3 * s));
      g.beginPath(); g.moveTo(x, cy - rim + RY * s); g.lineTo(x, cy + RY * s); g.stroke();
    }
    for (let l = 0; l < 6; l++) {
      const oy = (-rim * l) / 5;
      for (let idx = 0; idx < dots.length; idx++) {
        if ((idx + l * 5) % 3) continue;
        const d = dots[idx], an = d[0] + t * 0.04, sn = Math.sin(an), jj = d[1] * 9, front = sn > 0 ? 1 : 0.35;
        g.fillStyle = A("165,222,255", a * front * (0.22 + 0.3 * Math.sin(t * 3 + d[3] + l) * 0.5 + 0.25) * (1 - l * 0.08));
        g.fillRect(CX + (RR + jj) * Math.cos(an), cy + oy + (RY + jj * 0.3) * sn, d[2], d[2]);
      }
    }
    g.lineWidth = 1.6; g.strokeStyle = A("90,170,255", a * 0.7); ell(CX, cy, RR, RY); g.stroke();
    g.lineWidth = 2.6; g.strokeStyle = A("225,248,255", a); ell(CX, cy - rim, RR, RY); g.stroke();
    TIERS.forEach((m0, i) => {
      if (i === 0) return;
      const m = m0 * f;
      g.lineWidth = i % 2 ? 1.2 : 1.7; g.strokeStyle = A(i % 2 ? "0,229,255" : "110,190,255", a * (0.98 - i * 0.06));
      ell(CX, cy + i * st, rx0 * m, ry0 * m); g.stroke();
    });
    g.lineWidth = 3; g.strokeStyle = A("240,252,255", a);
    const s0 = t * 1.1 * (1 + P.fast * 2); ell(CX, cy - rim, RR, RY, s0, s0 + 0.9); g.stroke();
    g.shadowBlur = 0;
  }

  const icones = CATEGORIES.map((cat) => new Path2D(cat.icone));
  function icone(i: number, cx: number, cy: number, taille: number, couleur: string, epaisseur = 1.5): void {
    g.save(); g.translate(cx - taille / 2, cy - taille / 2); g.scale(taille / 24, taille / 24);
    g.lineWidth = epaisseur; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = couleur; g.stroke(icones[i]);
    g.restore();
  }

  const ls = (px: number): void => { (g as unknown as { letterSpacing: string }).letterSpacing = `${px}px`; };

  function card(cx: number, cy: number, w: number, h: number, it: Item, gi: number, sel: boolean, a: number, glow?: number): void {
    const x = cx - w / 2, c = 6;
    g.save(); g.globalAlpha = a;
    g.beginPath(); g.moveTo(x + c, cy); g.lineTo(x + w, cy); g.lineTo(x + w, cy + h - c); g.lineTo(x + w - c, cy + h); g.lineTo(x, cy + h); g.lineTo(x, cy + c); g.closePath();
    const fg = g.createLinearGradient(x, 0, x + w, 0);
    fg.addColorStop(0, sel ? "rgba(26,100,255,.72)" : "rgba(10,40,150,.5)"); fg.addColorStop(1, sel ? "rgba(8,46,190,.55)" : "rgba(4,18,80,.34)");
    g.fillStyle = fg; g.fill();
    g.strokeStyle = sel ? "#d8f8ff" : "rgba(70,165,255,.8)"; g.lineWidth = sel ? 1.1 : 0.7; g.shadowColor = "#00e5ff"; g.shadowBlur = sel ? (glow ?? 16) : 4; g.stroke(); g.shadowBlur = 0;
    g.strokeStyle = sel ? "#fff" : "rgba(130,215,255,.95)"; g.lineWidth = 1; g.beginPath(); g.moveTo(x + c, cy); g.lineTo(x + w * 0.55, cy); g.stroke();
    icone(gi, x + 18, cy + h / 2, 16, sel ? "#ffffff" : "#bfeaff", 1.5);
    ls(1); g.fillStyle = "#fff"; g.font = `600 ${sel ? 10.5 : 9.5}px Orbitron,Consolas,monospace`; g.textBaseline = "middle"; g.textAlign = "left"; g.fillText(it[0], x + 36, cy + h * 0.36);
    ls(0.6); g.fillStyle = "rgba(130,225,255,.9)"; g.font = "5.5px Consolas,monospace"; g.fillText(it[1], x + 36, cy + h * 0.74); ls(0);
    g.fillStyle = "rgba(0,229,255,.9)"; g.fillRect(x + w - 4, cy + 4, 1.2, h - 8);
    for (let k = 0; k < 3; k++) g.fillRect(x + w - 12 + k * 2.6, cy + h / 2 - 2, 1.2, 4);
    g.restore();
  }

  function chemin(x: number, y: number, w: number, h: number, c: number, tab: boolean): void {
    g.beginPath(); g.moveTo(x, y); g.lineTo(x + w - c, y); g.lineTo(x + w, y + c); g.lineTo(x + w, y + h); g.lineTo(x + c, y + h); g.lineTo(x, y + h - c);
    if (tab) { g.lineTo(x, y + h * 0.62); g.lineTo(x - 5, y + h * 0.62 - 5); g.lineTo(x - 5, y + h * 0.38 + 5); g.lineTo(x, y + h * 0.38); }
    g.closePath();
  }

  /** Cadre d'un panneau : fond sombre, double trait très fin, coin coupé, languette à gauche, coins repères. */
  function fr(x: number, y: number, w: number, h: number, a: number, tab = true): void {
    const fond = g.createLinearGradient(0, y, 0, y + h); fond.addColorStop(0, A("6,24,84", 0.82 * a)); fond.addColorStop(1, A("3,10,42", 0.88 * a));
    chemin(x, y, w, h, 12, tab); g.fillStyle = fond; g.fill();
    g.save(); chemin(x, y, w, h, 12, tab); g.clip(); g.strokeStyle = A("120,200,255", 0.035 * a); g.lineWidth = 0.5;
    for (let yy = y + 2; yy < y + h; yy += 3) { g.beginPath(); g.moveTo(x, yy); g.lineTo(x + w, yy); g.stroke(); }
    g.restore();
    g.shadowColor = "#1a6bff"; g.shadowBlur = 10; g.strokeStyle = A("60,160,255", 0.85 * a); g.lineWidth = 0.9; chemin(x, y, w, h, 12, tab); g.stroke(); g.shadowBlur = 0;
    g.strokeStyle = A("80,170,255", 0.28 * a); g.lineWidth = 0.5; chemin(x + 4, y + 4, w - 8, h - 8, 10, false); g.stroke();
    g.strokeStyle = A("150,230,255", 0.95 * a); g.lineWidth = 1.3;
    g.beginPath(); g.moveTo(x, y + 10); g.lineTo(x, y); g.lineTo(x + 10, y); g.moveTo(x + w, y + h - 10); g.lineTo(x + w, y + h); g.lineTo(x + w - 10, y + h); g.stroke();
  }

  function titre(x: number, y: number, w: number, txt: string, a: number): void {
    ls(1.4); g.font = "600 6px Orbitron,Consolas,monospace"; g.fillStyle = A("130,215,255", 0.9 * a); g.textBaseline = "top"; g.textAlign = "left"; g.fillText(txt, x + 14, y + 9); ls(0);
    g.strokeStyle = A("80,170,255", 0.4 * a); g.lineWidth = 0.5; g.beginPath(); g.moveTo(x + 14, y + 19); g.lineTo(x + w - 14, y + 19); g.stroke();
    g.fillStyle = A("0,229,255", 0.85 * a); g.fillRect(x + w - 24, y + 8, 3, 3); g.fillRect(x + w - 19, y + 8, 3, 3); g.fillRect(x + w - 14, y + 8, 3, 3);
  }

  function cadre(x: number, y: number, w: number, h: number, a: number, txt?: string): void {
    g.strokeStyle = A("70,160,255", 0.45 * a); g.lineWidth = 0.5; g.strokeRect(x, y, w, h);
    g.strokeStyle = A("150,230,255", 0.8 * a); g.lineWidth = 0.9; g.beginPath(); g.moveTo(x, y + 4); g.lineTo(x, y); g.lineTo(x + 4, y); g.stroke();
    if (txt) { ls(0.8); g.font = "4.5px Consolas,monospace"; g.fillStyle = A("110,200,255", 0.7 * a); g.textBaseline = "top"; g.textAlign = "left"; g.fillText(txt, x + 2, y - 6); ls(0); }
  }

  function matrix(x: number, y: number, c: number, r: number, s: number, t: number, col: string, a: number): void {
    for (let i = 0; i < c; i++) for (let j = 0; j < r; j++) {
      if (hash(i * 13 + j * 7 + Math.floor(t * 2.2 + i * 0.3)) > 0.45) { g.fillStyle = A(col, a * (0.5 + hash(i + j * 3) * 0.5)); g.fillRect(x + i * s, y + j * s, s - 1.2, s - 1.2); }
    }
  }

  function radar(cx: number, cy: number, r: number, a: number, t: number): void {
    g.lineWidth = 0.5;
    [1, 0.88, 0.74, 0.58, 0.4].forEach((m, i) => { g.strokeStyle = A("90,180,255", (0.55 - i * 0.07) * a); g.beginPath(); g.arc(cx, cy, r * m, 0, TAU); g.stroke(); });
    g.strokeStyle = A("150,215,255", 0.6 * a);
    for (let i = 0; i < 72; i++) { const an = (i / 72) * TAU, l = i % 6 === 0 ? 3.2 : 1.6; g.beginPath(); g.moveTo(cx + Math.cos(an) * r, cy + Math.sin(an) * r); g.lineTo(cx + Math.cos(an) * (r + l), cy + Math.sin(an) * (r + l)); g.stroke(); }
    g.beginPath(); g.moveTo(cx - r * 1.1, cy); g.lineTo(cx + r * 1.1, cy); g.moveTo(cx, cy - r * 1.1); g.lineTo(cx, cy + r * 1.1); g.strokeStyle = A("90,180,255", 0.3 * a); g.stroke();
    g.lineWidth = 2.6;
    ([["255,205,50", 0.2, 1.3, 0.8], ["70,235,130", 1.5, 3.0, 0.8], ["0,215,255", 3.2, 4.8, 0.8], ["255,120,40", 5.0, 5.9, 0.8], ["0,215,255", 0.4, 2.2, 0.58], ["255,205,50", 2.6, 4.2, 0.58], ["70,235,130", 4.5, 5.8, 0.58]] as [string, number, number, number][]).forEach((q, i) => {
      const rot = t * (i % 2 ? -0.35 : 0.45); g.strokeStyle = A(q[0], 0.95 * a); g.beginPath(); g.arc(cx, cy, r * q[3], q[1] + rot, q[2] + rot); g.stroke();
    });
    const sw = t * 1.3, wedge = g.createConicGradient ? g.createConicGradient(sw - 0.9, cx, cy) : null;
    if (wedge) { wedge.addColorStop(0, "rgba(0,229,255,0)"); wedge.addColorStop(0.14, A("0,229,255", 0.28 * a)); wedge.addColorStop(0.15, "rgba(0,229,255,0)"); g.fillStyle = wedge; g.beginPath(); g.arc(cx, cy, r * 0.9, 0, TAU); g.fill(); }
    g.lineWidth = 0.8; g.strokeStyle = A("200,245,255", 0.9 * a); g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(sw) * r * 0.9, cy + Math.sin(sw) * r * 0.9); g.stroke();
  }

  function barres(x: number, y: number, w: number, h: number, n: number, t: number, a: number): void {
    const bw = w / n;
    for (let i = 0; i < n; i++) {
      const v = 0.25 + 0.7 * hash(i * 5 + Math.floor(t * 0.8 + i * 0.2)), bh = h * v;
      g.fillStyle = A("0,229,255", 0.16 * a); g.fillRect(x + i * bw + 1, y + h - bh, bw - 2, bh);
      g.strokeStyle = A("0,229,255", 0.75 * a); g.lineWidth = 0.5;
      for (let yy = y + h - bh; yy < y + h; yy += 2.4) { g.beginPath(); g.moveTo(x + i * bw + 1, yy); g.lineTo(x + (i + 1) * bw - 1, yy); g.stroke(); }
    }
  }

  function flux(x: number, y: number, w: number, h: number, t: number, a: number): void {
    g.lineWidth = 0.6;
    for (let i = 0; i < 8; i++) {
      const y1 = y + (i / 7) * h, y2 = y + h * (0.5 + 0.35 * Math.sin(i * 1.7 + t * 0.4));
      g.strokeStyle = A("0,229,255", (0.35 + 0.4 * hash(i)) * a); g.beginPath(); g.moveTo(x, y1); g.bezierCurveTo(x + w * 0.5, y1, x + w * 0.5, y2, x + w, y2); g.stroke();
      g.fillStyle = A("150,230,255", 0.9 * a); g.fillRect(x - 1, y1 - 1, 2, 2); g.fillRect(x + w - 1, y2 - 1, 2, 2);
    }
  }

  function nuage(x: number, y: number, w: number, h: number, t: number, a: number): void {
    for (let i = 0; i < 80; i++) {
      const px = x + hash(i * 2.3) * w + Math.sin(t * 0.3 + i) * 1.2, py = y + hash(i * 4.1 + 7) * h + Math.cos(t * 0.25 + i * 1.3) * 1.2;
      g.fillStyle = A(i % 9 === 0 ? "255,205,50" : "120,215,255", (0.4 + 0.5 * hash(i)) * a); g.fillRect(px, py, 1.1, 1.1);
    }
  }

  function audioPanel(a: number, t: number): void {
    if (a < 0.02) return;
    g.save(); const lx = PLX - (1 - a) * 40, ly = TOP0 + 34;
    fr(lx, ly, 215, 215, a); titre(lx, ly, 215, "ENTRÉE AUDIO · MICRO", a); g.globalAlpha = a;
    const gx = lx + 16, gy = ly + 30, gw = 183, gh = 76, niveau = cl(micNiveau + volume, 0, 1), amp = 2 + 8 * P.spec + 26 * niveau;
    g.strokeStyle = "rgba(80,170,255,.14)"; g.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) { g.beginPath(); g.moveTo(gx, gy + (i / 4) * gh); g.lineTo(gx + gw, gy + (i / 4) * gh); g.stroke(); }
    for (let i = 0; i <= 10; i++) { g.beginPath(); g.moveTo(gx + (i / 10) * gw, gy); g.lineTo(gx + (i / 10) * gw, gy + gh); g.stroke(); }
    cadre(gx, gy, gw, gh, a);
    g.shadowColor = "#00e5ff"; g.shadowBlur = 5; g.strokeStyle = A("0,229,255", a); g.lineWidth = 1; g.beginPath();
    for (let x = 0; x <= gw; x += 1.5) { const e = Math.sin((x / gw) * Math.PI), y = gy + gh / 2 + Math.sin(x * 0.21 + t * 9) * Math.sin(x * 0.05 - t * 3) * amp * e; if (x === 0) g.moveTo(gx + x, y); else g.lineTo(gx + x, y); }
    g.stroke(); g.shadowBlur = 0;
    const cur = gx + ((t * 46) % gw); g.strokeStyle = A("200,245,255", 0.55 * a); g.lineWidth = 0.6; g.beginPath(); g.moveTo(cur, gy); g.lineTo(cur, gy + gh); g.stroke();
    const vy = ly + 116, n = 46;
    for (let i = 0; i < n; i++) {
      const lv = cl(0.08 + (0.1 + 0.9 * niveau) * hash(i * 3 + Math.floor(t * 8)), 0, 1), bh = lv * 30;
      g.fillStyle = A(lv > 0.82 ? "255,120,40" : lv > 0.62 ? "255,210,40" : "0,229,255", a * 0.9); g.fillRect(gx + i * 4, vy + 30 - bh, 2.2, bh);
    }
    g.strokeStyle = A("80,170,255", 0.4 * a); g.lineWidth = 0.5; g.beginPath(); g.moveTo(gx, vy + 31); g.lineTo(gx + gw, vy + 31); g.stroke();
    const rcx = lx + 46, rcy = ly + 176;
    g.lineWidth = 0.5; g.strokeStyle = A("90,180,255", 0.55 * a); g.beginPath(); g.arc(rcx, rcy, 20, 0, TAU); g.stroke(); g.beginPath(); g.arc(rcx, rcy, 15, 0, TAU); g.stroke();
    for (let i = 0; i < 48; i++) { const an = (i / 48) * TAU; g.beginPath(); g.moveTo(rcx + Math.cos(an) * 20, rcy + Math.sin(an) * 20); g.lineTo(rcx + Math.cos(an) * 22.5, rcy + Math.sin(an) * 22.5); g.stroke(); }
    g.lineWidth = 2.2; g.strokeStyle = A("0,229,255", a * 0.95); g.beginPath(); g.arc(rcx, rcy, 17.5, -1.5708, -1.5708 + TAU * (0.04 + 0.96 * niveau)); g.stroke();
    ls(0.5); g.font = "600 7px Orbitron,Consolas,monospace"; g.fillStyle = A("200,240,255", a); g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(`${Math.round(niveau * 100)}`, rcx, rcy); g.textAlign = "left"; ls(0);
    matrix(lx + 84, ly + 160, 22, 5, 5, t + 5, "80,255,200", a);
    g.restore();
  }

  function infoPanel(a: number, t: number): void {
    if (a < 0.02) return;
    const lx = PLX, ly = TOP0 + 34, it: Item = mot && performance.now() < mot.fin ? [mot.texte, "MESSAGE DE JARVIS"] : [CATEGORIES[cibleCat].nom, CATEGORIES[cibleCat].sous[cibleSous].nom.toUpperCase()];
    g.save(); fr(lx, ly, 215, 215, a); titre(lx, ly, 215, "MODULE · TROUVÉ", a); g.globalAlpha = a;
    const px = lx + 16, py = ly + 30;
    g.fillStyle = A("30,100,255", 0.14); g.fillRect(px, py, 78, 54); cadre(px, py, 78, 54, a);
    icone(cibleCat, px + 39, py + 27, 34, "#e4f8ff", 1.2);
    for (let i = 0; i < 4; i++) { g.fillStyle = A("0,229,255", 0.8 * a); g.fillRect(px + 88, py + 4 + i * 8, 22 + hash(i + cibleCat) * 50, 1.4); }
    ls(2); g.fillStyle = "#fff"; g.font = `600 ${it[0].length > 9 ? 13 : 17}px Orbitron,Consolas,monospace`; g.textBaseline = "top"; g.textAlign = "left"; g.fillText(it[0], px, ly + 96); ls(0);
    g.strokeStyle = A("80,170,255", 0.45 * a); g.lineWidth = 0.5; g.beginPath(); g.moveTo(px, ly + 120); g.lineTo(lx + 150, ly + 120); g.stroke();
    const lignes: [string, string][] = [["MODULE", it[0]], ["SOURCE", it[1]], ["TRAITEMENT", "JARVIS"], ["ÉTAT", "ACTIF"]];
    lignes.forEach((l, k) => {
      const y = ly + 128 + k * 14; ls(0.8); g.font = "5px Consolas,monospace"; g.fillStyle = A("110,190,240", 0.8 * a); g.fillText(l[0], px, y); g.font = "600 6px Consolas,monospace"; g.fillStyle = A("200,240,255", a); g.fillText(l[1].slice(0, 22), px + 54, y); ls(0);
      g.strokeStyle = A("80,170,255", 0.18 * a); g.lineWidth = 0.5; g.beginPath(); g.moveTo(px, y + 9); g.lineTo(lx + 150, y + 9); g.stroke();
    });
    g.fillStyle = A("0,229,255", 0.9 * a); g.fillRect(lx + 168, ly + 30, 1.6, 150);
    g.save(); g.translate(lx + 182, ly + 105); g.rotate(1.5708); ls(2); g.fillStyle = "#7ff0e0"; g.font = "600 7px Orbitron,Consolas,monospace"; g.textAlign = "center"; g.fillText("TROUVÉ", 0, 0); ls(0); g.restore();
    g.strokeStyle = A("0,229,255", 0.4 * a); g.lineWidth = 0.5; g.strokeRect(px, ly + 190, 134, 5); g.fillStyle = A("0,229,255", 0.5 + 0.35 * Math.sin(t * 3)); g.fillRect(px + 1, ly + 191, 132 * (0.55 + 0.4 * Math.sin(t * 0.7) * 0.5), 3);
    g.restore();
  }

  function rightPanels(a: number, t: number): void {
    if (a < 0.02) return;
    g.save(); const s = (1 - a) * 60, rx = CX + RX + 95 + s, ry = TOP0 + 4;
    fr(rx, ry, 270, 160, a, false); titre(rx, ry, 270, "ANALYSE DES FLUX · SYSTÈME", a); g.globalAlpha = a;
    radar(rx + 56, ry + 66, 34, a, t);
    for (let i = 0; i < 9; i++) { g.fillStyle = A("0,229,255", 0.85 * a); g.fillRect(rx + 112, ry + 30 + i * 6.2, 14 + hash(i + Math.floor(t * 1.4)) * 52, 1.4); g.fillRect(rx + 188, ry + 30 + i * 6.2, 6 + hash(i * 3 + Math.floor(t * 1.1)) * 40, 1.4); }
    g.font = "4.5px Consolas,monospace"; g.fillStyle = A("120,205,255", 0.75 * a); g.textBaseline = "top"; g.textAlign = "left"; ls(0.5);
    for (let i = 0; i < 4; i++) g.fillText(`0x${Math.floor(hash(i + Math.floor(t * 0.7)) * 65535).toString(16).toUpperCase().padStart(4, "0")}`, rx + 232, ry + 30 + i * 12); ls(0);
    cadre(rx + 12, ry + 108, 54, 40, a, "MATRICE"); matrix(rx + 15, ry + 111, 10, 7, 5, t, "80,255,200", a);
    cadre(rx + 72, ry + 108, 54, 40, a, "CHARGE"); barres(rx + 75, ry + 111, 48, 34, 11, t, a);
    cadre(rx + 132, ry + 108, 64, 40, a, "FLUX"); flux(rx + 136, ry + 113, 56, 30, t, a);
    cadre(rx + 202, ry + 108, 56, 40, a, "NUAGE"); nuage(rx + 205, ry + 111, 50, 34, t, a);
    const r2 = ry + 170;
    fr(rx + 20, r2, 250, 86, a, false); titre(rx + 20, r2, 250, "MODULE DE DONNÉES", a);
    cadre(rx + 34, r2 + 28, 66, 44, a); matrix(rx + 37, r2 + 31, 12, 7, 5, t + 3, "120,255,90", a);
    for (let c = 0; c < 4; c++) for (let i = 0; i < 6; i++) { g.fillStyle = A("0,229,255", 0.7 * a); g.fillRect(rx + 112 + c * 20, r2 + 30 + i * 7, 4 + hash(c * 7 + i + Math.floor(t * 0.9)) * 12, 1.4); }
    cadre(rx + 198, r2 + 28, 64, 44, a); matrix(rx + 201, r2 + 31, 12, 7, 5, t + 8, "0,229,255", a);
    ls(1); g.font = "5px Orbitron,Consolas,monospace"; g.fillStyle = A("130,215,255", 0.8 * a); g.fillText("SYNC", rx + 34, r2 + 76); ls(0);
    g.restore();
  }

  function chev(x: number, dir: number, t: number): void {
    g.save(); g.shadowColor = "#00e5ff"; g.shadowBlur = 8;
    for (let i = 0; i < 7; i++) {
      const al = 0.25 + 0.75 * Math.max(0, Math.sin(t * 5 - i * 0.7 * dir)); g.strokeStyle = A("0,200,255", al); g.lineWidth = 1.3;
      const px = x + dir * i * 9; g.beginPath(); g.moveTo(px, 28); g.lineTo(px + dir * 6, 35); g.lineTo(px, 42); g.stroke();
    }
    g.restore();
  }

  function colonnesDePixels(top: number, fa: number, t: number, rxS: number, ryS: number): void {
    const hh = BY - top, mic = 0.6 + 0.2 * Math.sin(t * 0.5) * Math.sin(t * 0.31 + 1), rot = t * 0.035;
    const L = colonnes.map((c) => ({ c, s: Math.sin(c.th + rot) })).sort((a, b) => a.s - b.s);
    L.forEach((o) => {
      const c = o.c, x = CX + rxS * c.r * Math.cos(c.th + rot), yb = BY + ryS * c.r * o.s, dp = 0.55 + 0.45 * (o.s * 0.5 + 0.5);
      const lv = (0.1 + 0.5 * (0.5 + 0.5 * Math.sin(t * c.sp + c.ph))) * P.spec * mic, bh = lv * hh * 0.72 * (0.7 + 0.3 * dp), n = Math.floor(bh / 3.6), w = c.w * dp;
      if (n < 2) return;
      const gl = g.createRadialGradient(x, yb, 1, x, yb, w * 4); gl.addColorStop(0, A("90,190,255", 0.35 * fa * P.spec * dp)); gl.addColorStop(1, "rgba(90,190,255,0)");
      g.fillStyle = gl; g.fillRect(x - w * 4, yb - w * 2, w * 8, w * 4);
      for (let k = 0; k < n; k++) {
        const kk = k / n, fl = hash(c.ph * 100 + k * 3 + Math.floor(t * 1.2 + c.th * 3)) > 0.32 ? 1 : 0.22;
        g.fillStyle = A(k > n * 0.88 ? "235,250,255" : "110,205,255", fa * P.spec * (1 - kk) * 0.85 * fl * dp); g.fillRect(x - w / 2, yb - k * 3.6, w, 2.3);
      }
    });
  }

  function dessiner(t: number): void {
    const tE = t - tSeq;
    const rt: Record<keyof Cible, number> = { h: 0.04, cards: 0.07, panels: 0.06, open: 0.03, spec: 0.06, fast: 0.1, voice: 0.1 };
    (Object.keys(rt) as (keyof Cible)[]).forEach((k) => { P[k] += (cible[k] - P[k]) * rt[k]; });
    // Taille de l'écran : celle des panneaux affichés, plus une marge (le cylindre ne doit pas faire le double du widget)
    if (mode === "ouvert") {
      const rects = [...raisonsOuvert.values()].filter((r) => r.el !== null).map(({ el, centre }) => {
        if (!centre) return (el as HTMLElement).getBoundingClientRect();
        const p = emplacementCentre(el as HTMLElement), w = (el as HTMLElement).offsetWidth, h = (el as HTMLElement).offsetHeight;
        return { left: p.left, right: p.left + w, top: p.top, bottom: p.top + h, width: w, height: h };
      }).filter((r) => r.width > 0 && r.height > 0);
      if (rects.length) {
        const gauche = Math.min(...rects.map((r) => r.left)), droite = Math.max(...rects.map((r) => r.right));
        const haut = Math.min(...rects.map((r) => r.top)), bas = Math.max(...rects.map((r) => r.bottom));
        const cDemi = cl((Math.max(Math.abs(gauche - largeur / 2), Math.abs(droite - largeur / 2)) + 16) / echelle, RX * 1.2, (largeur / 2 - 8) / echelle);
        const cTop = Math.max((haut - 15 - origY) / echelle, (16 - origY) / echelle), cBas = (bas + 15 - origY) / echelle;
        ecran.demi += (cDemi - ecran.demi) * 0.14; ecran.top += (cTop - ecran.top) * 0.14; ecran.bas += (cBas - ecran.bas) * 0.14;
      }
    }
    // L'ouverture ne commence qu'une fois le cylindre dressé (s'il était en veille, il monte d'abord)
    const h = P.h * HF, e = sm(P.open) * cl((P.h - 0.8) / 0.2, 0, 1);
    const ry0 = RX * 0.22, rxS = RX + (ecran.demi - RX) * sm(e / 0.55), ryS = ry0 * (1 - sm(e / 0.55)) + 2.2 * sm(e / 0.55), top = BY - h + (ecran.top - (BY - h)) * sm(e / 0.55), bas = BY + (ecran.bas - BY) * sm((e - 0.3) / 0.7);
    const ch = 28, gap = (HF - 2 * ry0 - 46 - ch) / (NV - 1), cardsA = cl(1 - P.open * 3, 0, 1), y0 = top + ry0 + 22;
    const sq = sequence();
    const flyU = mode === "reflexion" || mode === "parole" ? cl((tE - sq.T) / 0.7, 0, 1) : 0;
    P.info += ((flyU >= 1 || (mot !== null && performance.now() < mot.fin) ? 1 : 0) - P.info) * 0.14;
    if (analyser && analyseData) {
      analyser.getByteFrequencyData(analyseData);
      let somme = 0; for (let i = 0; i < analyseData.length; i++) somme += analyseData[i];
      micNiveau += (cl(somme / analyseData.length / 90, 0, 1) - micNiveau) * 0.2;
    } else micNiveau *= 0.9;

    const bg = g.createRadialGradient(CX, BY, 10, CX, BY - 100, 520); bg.addColorStop(0, "rgba(20,60,200,.35)"); bg.addColorStop(0.5, "rgba(5,12,60,.18)"); bg.addColorStop(1, "rgba(0,0,10,0)");
    g.fillStyle = bg; g.fillRect(-1500, -1000, 3900, 2600);
    chev(34, 1, t); chev(W - 34, -1, t);
    g.save(); g.translate(CX, BY); g.scale(1, ry0 / RX);
    const gd = g.createRadialGradient(0, 0, RX * 0.2, 0, 0, RX * 2.4); gd.addColorStop(0, "rgba(40,110,255,.5)"); gd.addColorStop(1, "rgba(40,110,255,0)");
    g.fillStyle = gd; g.beginPath(); g.arc(0, 0, RX * 2.4, 0, TAU); g.fill(); g.restore();
    [1.3, 1.6, 2, 2.4, 2.9, 3.4].forEach((m, i) => {
      g.strokeStyle = i % 2 ? A("120,80,255", 0.35 - i * 0.03) : A("50,130,255", 0.45 - i * 0.04); g.lineWidth = 1; g.setLineDash(i % 2 ? [3, 9] : [40, 16]);
      g.lineDashOffset = -t * (14 + i * 7) * (i % 2 ? -1 : 1) * (1 + P.fast * 2); ell(CX, BY, RX * m, ry0 * m); g.stroke();
    });
    g.setLineDash([]);
    if (P.voice > 0.3 && P.open < 0.3) for (let q = 0; q < 2; q++) {
      const u = (t * 0.35 + q / 2) % 1, rr = RX * (1.3 + u * 1.1); g.strokeStyle = A("0,229,255", (1 - u) * 0.22 * P.voice); g.lineWidth = 1.2; ell(CX, BY, rr, (ry0 * rr) / RX); g.stroke();
    }
    audioPanel(P.panels * (1 - P.info), t); infoPanel(P.info * P.panels, t); rightPanels(P.panels, t);

    if (h > 6 || e > 0.01) {
      const fa = cl(h / 90, 0, 1);
      const bord = Math.min(0.2, 18 / (rxS * 2));
      const gh = g.createLinearGradient(CX - rxS, 0, CX + rxS, 0);
      gh.addColorStop(0, A("40,120,255", 0.38 * fa)); gh.addColorStop(bord, A("25,80,235", 0.12 * fa)); gh.addColorStop(Math.min(0.45, bord * 2.5), A("20,70,230", 0.03 * fa));
      gh.addColorStop(Math.max(0.55, 1 - bord * 2.5), A("20,70,230", 0.03 * fa)); gh.addColorStop(1 - bord, A("25,80,235", 0.12 * fa)); gh.addColorStop(1, A("40,120,255", 0.38 * fa));
      g.fillStyle = gh; g.fillRect(CX - rxS, top, rxS * 2, bas - top);
      const gv = g.createLinearGradient(0, top, 0, bas); gv.addColorStop(0, A("20,60,230", 0)); gv.addColorStop(0.7, A("25,80,255", 0.04 * fa)); gv.addColorStop(1, A("40,120,255", 0.2 * fa));
      g.fillStyle = gv; g.fillRect(CX - rxS, top, rxS * 2, bas - top);
      for (let i = 0; i < NL; i++) {
        const ph = -1.5708 + ((i + 0.5) / NL) * Math.PI, x = CX + rxS * Math.sin(ph), c = Math.cos(ph), ed = Math.pow(Math.abs(Math.sin(ph)), 3.5);
        g.strokeStyle = A("45,120,235", (0.03 + 0.2 * ed) * fa); g.lineWidth = 1; g.setLineDash([1, 3]); g.lineDashOffset = -t * 8; g.beginPath(); g.moveTo(x, top - ryS * c); g.lineTo(x, bas - ryS * c); g.stroke();
        g.strokeStyle = A("90,175,255", (0.05 + 0.55 * ed) * fa); g.lineDashOffset = t * 12; g.setLineDash([1, 2]); g.beginPath(); g.moveTo(x, top + ryS * c); g.lineTo(x, bas + ryS * c); g.stroke(); g.setLineDash([]);
      }
      if (P.spec > 0.02) colonnesDePixels(top, fa, t, rxS * 0.96, ryS * 0.96);
      g.shadowColor = "#2a7bff"; g.shadowBlur = 8; g.lineWidth = 1.8; g.strokeStyle = A("110,200,255", 0.7 * fa);
      g.beginPath(); g.moveTo(CX - rxS, top); g.lineTo(CX - rxS, bas); g.moveTo(CX + rxS, top); g.lineTo(CX + rxS, bas); g.stroke(); g.shadowBlur = 0;
      const sc = [(t * 0.45) % 1, (t * 0.45 + 0.5) % 1]; if (P.fast > 0.3) sc.push((t * 1.8) % 1, (t * 1.8 + 0.4) % 1);
      if (e < 0.5) sc.forEach((u) => { const yy = top + u * (bas - top); g.strokeStyle = A("0,229,255", 0.3 * fa * (1 - e * 2) * Math.sin(u * Math.PI)); g.lineWidth = 1.4; ell(CX, yy, rxS, ryS); g.stroke(); });
      // Roue : catégories puis sous-catégories. Le cadre de sélection part du haut de la roue et descend au milieu pendant que
      // la liste défile ; la cible s'arrête dans le cadre.
      let niveau = 0, u = 1, locked = 0;
      if (mode === "reflexion" || mode === "parole") {
        const a1 = sq.d1, a2 = a1 + 0.35, a3 = a2 + sq.d2;
        if (tE < a1) { niveau = 1; u = tE / a1; }
        else if (tE < a2) { niveau = 1; locked = cl((tE - a1) / 0.25, 0, 1); }
        else if (tE < a3) { niveau = 2; u = (tE - a2) / sq.d2; }
        else { niveau = 2; locked = cl((tE - a3) / 0.25, 0, 1); }
      } else if (P.voice > 0.5 && P.cards > 0.2) { niveau = 2; locked = 1; }
      if (niveau > 0 && P.cards > 0.05 && cardsA > 0.01) {
        const liste = niveau === 1 ? CATEGORIES.map((k) => k.nom) : CATEGORIES[cibleCat].sous.map((k) => k.nom.toUpperCase());
        const visee = niveau === 1 ? cibleCat : cibleSous, n = liste.length, haut = (Math.min(n, NV) - 1) / 2, demi = haut + 0.5;
        const ue = locked > 0 ? 1 : u, p = haut + distanceRoue(n, visee) * (1 - Math.pow(1 - ue, 3));
        const cs = 1 - Math.pow(1 - Math.min(1, ue * 1.25), 3), yc = y0 + 3 * gap, ys = yc - haut * gap * (1 - cs);
        const base = cl(P.cards / 0.4, 0, 1) * cardsA * cl(h / 200, 0, 1);
        for (let i = 0; i < n; i++) {
          let o = (((i - p) % n) + n) % n; if (o > n / 2) o -= n;
          const ao = Math.abs(o), y = yc + o * gap, proche = Math.abs(y - ys) < gap / 2;
          if (ao > demi + 0.01 || (flyU > 0 && proche)) continue;
          const a = base * Math.max(0.15, 1 - ao * 0.25) * (locked > 0.5 && !proche ? 0.7 : 1);
          if (a < 0.01) continue;
          const sousTitre = niveau === 1 ? CATEGORIES[i].sous.slice(0, 2).map((k) => k.nom.toUpperCase()).join(" · ") : CATEGORIES[cibleCat].nom;
          card(CX, y - (proche ? 3 : 0), (proche ? 206 : 186) * (1 - ao * 0.05), (proche ? ch * 1.12 : ch) * (1 - ao * 0.04), [liste[i], sousTitre], niveau === 1 ? i : cibleCat, proche, a, proche ? 22 : undefined);
        }
        if (flyU <= 0) {
          const cw = 206 + 30 * (1 - locked), chh = ch * 1.12 + 14 * (1 - locked), bx = CX - cw / 2 - 4, by = ys - 3 - 4 - 7 * (1 - locked);
          g.strokeStyle = A("255,255,255", 0.9 * base); g.lineWidth = 2; g.shadowColor = "#00e5ff"; g.shadowBlur = 10;
          ([[bx, by, 1, 1], [bx + cw + 8, by, -1, 1], [bx, by + chh + 8, 1, -1], [bx + cw + 8, by + chh + 8, -1, -1]] as number[][]).forEach((q) => {
            g.beginPath(); g.moveTo(q[0], q[1] + q[3] * 10); g.lineTo(q[0], q[1]); g.lineTo(q[0] + q[2] * 10, q[1]); g.stroke();
          });
          g.shadowBlur = 0;
        }
      }
    }
    const fl = cl(h / 60, 0, 1), ouvH = sm(e / 0.55);
    if (h > 6 || e > 0.01) rings(top, rxS, ryS, fl, t, 1, ouvH);
    g.globalAlpha = 1; rings(BY, RX, ry0, 1, t, -1, 0);

    if (e > 0.02) {
      const ym = top + (bas - top) * 0.5, u = cl(e / 0.5, 0, 1), demi = RX + (rxS * 0.97 - RX) * sm(u), aRayon = 0.95 * (1 - sm((e - 0.5) / 0.3));
      if (aRayon > 0.02) {  // le rayon qui traverse à mi-hauteur avant que l'écran ne s'ouvre
        g.shadowColor = "#00e5ff"; g.shadowBlur = 12; g.strokeStyle = A("200,245,255", aRayon); g.lineWidth = 1.4;
        g.beginPath(); g.moveTo(CX - demi, ym); g.lineTo(CX + demi, ym); g.stroke(); g.shadowBlur = 0;
      }
      const ouvE = sm((e - 0.45) / 0.55);
      if (ouvE > 0.02) {  // bord bas de l'écran, posé au-dessus du socle
        g.shadowColor = "#00e5ff"; g.shadowBlur = 12; g.strokeStyle = A("120,205,255", 0.9 * ouvE); g.lineWidth = 1.6;
        g.beginPath(); g.moveTo(CX - rxS, bas); g.lineTo(CX + rxS, bas); g.stroke(); g.shadowBlur = 0;
        g.strokeStyle = A("150,230,255", 0.9 * ouvE); g.lineWidth = 1.2;
        g.beginPath(); g.moveTo(CX - rxS, bas - 8); g.lineTo(CX - rxS, bas); g.lineTo(CX - rxS + 12, bas); g.moveTo(CX + rxS, bas - 8); g.lineTo(CX + rxS, bas); g.lineTo(CX + rxS - 12, bas); g.stroke();
      }
    }
    if (flyU > 0 && flyU < 1) {
      const u = sm(flyU), sx = CX, sy = y0 + 3 * gap - 3, ex = PLX + 107, ey = TOP0 + 34;
      const w2 = 206 + (215 - 206) * u, h2 = ch * 1.12 + (215 - ch * 1.12) * u, cx2 = sx + (ex - sx) * u, cy2 = sy + (ey - sy) * u;
      const tr = g.createLinearGradient(cx2, 0, sx, 0); tr.addColorStop(0, A("0,229,255", 0.35 * (1 - u))); tr.addColorStop(1, "rgba(0,229,255,0)");
      g.fillStyle = tr; g.fillRect(cx2, cy2 + h2 * 0.3, sx - cx2, h2 * 0.4 * (1 - u * 0.6));
      card(cx2, cy2, w2, h2, [CATEGORIES[cibleCat].sous[cibleSous].nom.toUpperCase(), CATEGORIES[cibleCat].nom], cibleCat, true, 1, 26);
    }
  }

  function ajuster(): void {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    largeur = window.innerWidth; hauteur = window.innerHeight;
    canvas.width = Math.round(largeur * dpr); canvas.height = Math.round(hauteur * dpr);
  }
  ajuster();
  window.addEventListener("resize", ajuster);

  function boucle(ms: number): void {
    raf = requestAnimationFrame(boucle);
    if (document.hidden || canvas.style.display === "none") return;
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, canvas.width, canvas.height);
    const baseY = hauteur * 0.74;
    const s = cl(Math.min((baseY - 130) / (HF + 50), largeur / 1000), 0.45, 1.6);
    echelle = s; origX = largeur / 2 - CX * s; origY = baseY - BY * s;
    g.setTransform(dpr * s, 0, 0, dpr * s, dpr * origX, dpr * origY);
    dessiner(ms / 1000);
  }
  raf = requestAnimationFrame(boucle);

  const maintenant = (): number => performance.now() / 1000;

  function appliquer(etat: OrbState): void {
    etatBackend = etat;
    if (rechercheForcee) return;
    const prochain: Mode = raisonsOuvert.size > 0 ? "ouvert" : (MODE_DE_ETAT[etat] ?? "veille");
    if (prochain === mode) return;
    // Réponse sans phase de réflexion (commande locale instantanée) : la recherche se joue quand même, pendant la parole
    if (prochain === "reflexion" || (prochain === "parole" && mode !== "reflexion")) tSeq = maintenant();
    mode = prochain; cible = CIBLES[prochain];
  }

  // Le retour en veille est retardé : entre la réflexion et la parole (ou entre deux phrases), le backend repasse
  // brièvement en « idle » ; sans ce délai le cylindre se refermait puis se rouvrait.
  function setState(etat: OrbState): void {
    if (tempoVeille) { clearTimeout(tempoVeille); tempoVeille = null; }
    if (etat === "idle" && mode !== "veille") { tempoVeille = setTimeout(() => { tempoVeille = null; appliquer("idle"); }, 1400); return; }
    appliquer(etat);
  }

  function noteText(texte: string): void {
    const t = sansAccent(texte);
    [cibleCat, cibleSous] = choisir(t);
  }

  return {
    setState,
    setVolume(v: number): void { volume = cl(v, 0, 1); },
    setAnalyser(a: AnalyserNode | null): void { analyser = a; analyseData = a ? new Uint8Array(a.frequencyBinCount) : null; },
    triggerDemo(): void {
      demoTimers.forEach(clearTimeout); demoTimers = [];
      const suite: [OrbState, number][] = [["listening", 0], ["thinking", 3500], ["speaking", 8500], ["idle", 14000]];
      suite.forEach(([etat, delai]) => demoTimers.push(setTimeout(() => setState(etat), delai)));
    },
    writeWord(w: string): void { mot = { texte: w.toUpperCase().slice(0, 14), fin: performance.now() + 4000 }; },
    setTheme(theme: string): void {
      const filtre = TEINTES[theme] ? `hue-rotate(${TEINTES[theme]}deg)` : "";
      canvas.style.filter = filtre;
      const paroles = document.getElementById("subtitle-hud"); if (paroles) paroles.style.filter = filtre;
    },
    noteText,
    setOuvert(raison: string, ouvert: boolean, element?: HTMLElement, centre = false): void {
      if (ouvert) raisonsOuvert.set(raison, { el: element ?? null, centre }); else raisonsOuvert.delete(raison);
      appliquer(etatBackend);
    },
    chercher(texte?: string): Promise<void> {
      return new Promise((fin) => {
        if (texte) noteText(texte);
        if (tempoVeille) { clearTimeout(tempoVeille); tempoVeille = null; }
        rechercheForcee = true; mode = "reflexion"; cible = CIBLES.reflexion; tSeq = maintenant();
        setTimeout(() => { rechercheForcee = false; fin(); }, (sequence().T + 0.7 + 0.3) * 1000);
      });
    },
    ecranOuvert(): boolean { return mode === "ouvert" && P.h > 0.97 && P.open > 0.93; },
    emplacement: emplacementCentre,
    destroy(): void { if (tempoVeille) clearTimeout(tempoVeille); cancelAnimationFrame(raf); window.removeEventListener("resize", ajuster); demoTimers.forEach(clearTimeout); },
  };
}
