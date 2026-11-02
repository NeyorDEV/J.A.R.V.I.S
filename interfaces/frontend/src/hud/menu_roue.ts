// Menu de JARVIS : le disque de veille s'ouvre en cylindre et les commandes y forment une roue de cartes courbes,
// dans le même style que la recherche vocale (orb_cylindre.ts) : une colonne de trois groupes ; celui qu'on ouvre
// se déroule en cascade (cartes plus étroites, décalées, qui pivotent l'une après l'autre) et repousse les suivants.
// Le menu ne contient aucune logique métier : une commande clique le bouton historique correspondant du carrousel
// (caché), dont l'action est déjà enregistrée (hud/carousel_actions.ts) ; l'état allumé se lit sur son aria-pressed.
// Même repère et même placement que l'orbe (orb_cylindre.ts) : le cylindre s'ouvre exactement sur le disque de veille.

import { orb } from "./orb_state";

const TAU = Math.PI * 2, CX = 450, BY = 452, RX = 108, HF = 345, K = 0.22, TOP0 = BY - HF;
const ry0 = RX * K;

type Icone = keyof typeof TRACES;
interface Entree { id: string; titre: string; sous: string; ic: Icone; module?: [string, string | null] }   // module : fiche à chercher avant d'agir (commandes sans écran)
interface Groupe { titre: string; sous: string; ic: Icone; entrees: Entree[] }

const TRACES = {
  oeil: ["M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z", [12, 12, 3]],
  texte: ["M4 5h16v11H9l-5 4z"],
  main: ["M8 12V5a1.5 1.5 0 0 1 3 0v6M11 11V3.5a1.5 1.5 0 0 1 3 0V11M14 11V5a1.5 1.5 0 0 1 3 0v8c0 4-2.5 7-6 7-2.5 0-4-1.3-5.4-3.4L3 13a1.5 1.5 0 0 1 2.5-1.6L8 14"],
  corbeille: ["M4 7h16M10 11v6M14 11v6M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2l1-12M9 7V4h6v3"],
  rafraichir: ["M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"],
  bouclier: ["M12 3 5 6v5c0 4.5 3 8.3 7 10 4-1.7 7-5.5 7-10V6l-7-3z"],
  maison: ["M4 11 12 4l8 7v8a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1v-8z"],
  pouls: ["M3 12h4l2-6 4 12 2-6h6"],
  liste: ["M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"],
  cle: ["M12 12h9M18 12v3", [8, 12, 4]],
  reglages: ["M12 9v6M9 12h6", [12, 12, 3]],
} as const;

const GROUPES: Groupe[] = [
  { titre: "IA", sous: "VISION · TEXTE · GESTES", ic: "oeil", entrees: [
    { id: "vision-button", titre: "VISION", sous: "CAMÉRA DE JARVIS", ic: "oeil", module: ["SYSTÈME", "Capture d'écran"] },
    { id: "subtitle-toggle", titre: "HUD TEXT", sous: "SOUS-TITRES", ic: "texte", module: ["JARVIS", "Sous-titres"] },
    { id: "gestures-toggle", titre: "MODE AR", sous: "GESTES DES MAINS", ic: "main", module: ["JEUX ET 3D", "Gestes"] },
  ] },
  { titre: "OUTILS", sous: "LOGICIELS · SÉCURITÉ", ic: "bouclier", entrees: [
    { id: "carousel-uninstaller-btn", titre: "UNINSTALL", sous: "DÉSINSTALLER UNE APPLI", ic: "corbeille" },
    { id: "carousel-winget-btn", titre: "WINGET", sous: "MISES À JOUR", ic: "rafraichir" },
    { id: "carousel-av-scan-btn", titre: "ANTIVIRUS", sous: "SCAN RAPIDE", ic: "bouclier" },
    { id: "carousel-ha-btn", titre: "DOMOTIQUE", sous: "HOME ASSISTANT", ic: "maison" },
  ] },
  { titre: "SYSTÈME", sous: "ÉTAT · COMMANDES · RÉGLAGES", ic: "reglages", entrees: [
    { id: "carousel-system-btn", titre: "ÉTAT", sous: "MOTEURS ET SERVICES", ic: "pouls" },
    { id: "carousel-commands-btn", titre: "COMMANDES", sous: "LISTE VOCALE", ic: "liste" },
    { id: "carousel-api-btn", titre: "API KEYS", sous: "CLÉS D'ACCÈS", ic: "cle" },
    { id: "clear-cache-btn", titre: "CACHE", sous: "VIDER ET RELANCER", ic: "rafraichir", module: ["JARVIS", "Paramètres"] },
    { id: "settings-button", titre: "PARAMS", sous: "RÉGLAGES GLOBAUX", ic: "reglages" },
  ] },
];

const cl = (v: number, a: number, b: number): number => (v < a ? a : v > b ? b : v);
const sm = (v: number): number => { v = cl(v, 0, 1); return v * v * (3 - 2 * v); };
const A = (c: string, a: number): string => `rgba(${c},${a})`;

interface Zone { id: number; x0: number; x1: number; y0: number; y1: number; c: number }

export function initMenuRoue(): void {
  const orbCanvas = document.getElementById("orb-canvas") as HTMLCanvasElement | null;
  if (!orbCanvas) return;
  const cv = document.createElement("canvas");
  cv.id = "menu-canvas";
  document.body.appendChild(cv);
  const g = cv.getContext("2d") as CanvasRenderingContext2D;
  const disque = document.createElement("div");
  disque.id = "menu-disque";
  document.body.appendChild(disque);

  const icones = Object.fromEntries(Object.entries(TRACES).map(([nom, def]) => {
    const p = new Path2D(def[0]);
    const c = (def as readonly unknown[])[1] as number[] | undefined;
    if (c) { p.moveTo(c[0] + c[2], c[1]); p.arc(c[0], c[1], c[2], 0, TAU); }
    return [nom, p];
  })) as Record<Icone, Path2D>;

  let ouvert = false, masque = false, groupe = -1, expand = 0, expandCible = 0, sel = 0, tNiv = 0, tExp = 0;
  let largeur = 0, hauteur = 0, dpr = 1, s = 1, origX = 0, origY = 0, boucle = 0;
  let sx = -1, sy = -1;       // souris, dans le repère de l'orbe
  let zones: Zone[] = [];

  const ajuster = (): void => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    largeur = window.innerWidth; hauteur = window.innerHeight;
    cv.width = Math.round(largeur * dpr); cv.height = Math.round(hauteur * dpr);
    const baseY = hauteur * 0.74;
    s = cl(Math.min((baseY - 130) / (HF + 50), largeur / 1000), 0.45, 1.6);
    origX = largeur / 2 - CX * s; origY = baseY - BY * s;
    const w = 2 * RX * s * 1.25, h = 2 * ry0 * s * 2.4;
    Object.assign(disque.style, { left: `${largeur / 2 - w / 2}px`, top: `${baseY - h / 2}px`, width: `${w}px`, height: `${h}px` });
  };
  ajuster();
  window.addEventListener("resize", ajuster);

  // Lignes affichées de haut en bas : les groupes, avec les commandes du groupe déplié insérées sous lui (si = -1 : carte du groupe)
  const lignes = (): { gi: number; si: number }[] => GROUPES.flatMap((gr, gi) => [{ gi, si: -1 }, ...(gi === groupe ? gr.entrees.map((_, si) => ({ gi, si })) : [])]);

  const etatBouton = (id: string): { allume: boolean; badge: string } => {
    const b = document.getElementById(id);
    const allume = !!b && (b.getAttribute("aria-pressed") === "true" || b.classList.contains("is-toggled-on"));
    let badge = "";
    if (id === "carousel-winget-btn") {
      const n = document.getElementById("winget-count-badge");
      if (n && !n.classList.contains("hidden") && n.textContent && n.textContent.trim() !== "0") badge = `${n.textContent.trim()} MISE(S) À JOUR`;
    }
    return { allume, badge };
  };

  // ── Dessin d'une carte en bande qui épouse le cylindre (même construction que la recherche vocale) ──
  function bande(th: number, y: number, h: number, a: number, demi: number, selection: number, titre: string, sous: string, ic: Icone, id: number, fs: number): void {
    const R = RX * 0.9, dep = 0, c = Math.cos(th), avant = c >= 0, N = 14, phiL = th - demi;
    const al = a * (avant ? 0.4 + 0.6 * Math.pow(c, 0.55) : 0.5);
    if (al < 0.012) return;
    const pt = (phi: number): [number, number] => [CX + R * Math.sin(phi), dep * (Math.cos(phi) - c)];
    const haut: [number, number][] = [], bas: [number, number][] = [];
    for (let j = 0; j <= N; j++) { const [x, dy] = pt(phiL + (j / N) * 2 * demi); haut.push([x, y + dy]); bas.push([x, y + h + dy]); }
    g.save(); g.globalAlpha = al;
    g.beginPath(); g.moveTo(haut[0][0], haut[0][1] + 5); g.lineTo(haut[0][0] + (haut[1][0] > haut[0][0] ? 3 : -3), haut[0][1]);
    for (let j = 1; j <= N; j++) g.lineTo(haut[j][0], haut[j][1]);
    g.lineTo(bas[N][0], bas[N][1] - 5); g.lineTo(bas[N][0] - (bas[N][0] > bas[N - 1][0] ? 3 : -3), bas[N][1]);
    for (let j = N - 1; j >= 0; j--) g.lineTo(bas[j][0], bas[j][1]);
    g.closePath();
    const xa = Math.min(haut[0][0], haut[N][0]), xb = Math.max(haut[0][0], haut[N][0]), fg = g.createLinearGradient(xa, 0, Math.max(xb, xa + 1), 0), q = selection;
    if (avant) {
      fg.addColorStop(0, A(`${10 + 16 * q},${40 + 60 * q},${150 + 105 * q}`, 0.5 + 0.28 * q)); fg.addColorStop(1, A(`${4 + 4 * q},${18 + 28 * q},${80 + 110 * q}`, 0.34 + 0.26 * q));
    } else { fg.addColorStop(0, "rgba(8,26,100,.7)"); fg.addColorStop(1, "rgba(4,14,66,.55)"); }
    g.fillStyle = fg; g.fill();
    g.strokeStyle = avant ? A(`${70 + 146 * q},${165 + 83 * q},255`, 0.8 + 0.2 * q) : "rgba(60,140,255,.55)"; g.lineWidth = 0.7 + 0.5 * q;
    if (q > 0.5) { g.shadowColor = "#00e5ff"; g.shadowBlur = 14 * q; }
    g.stroke(); g.shadowBlur = 0;
    if (avant) {
      g.strokeStyle = q > 0.5 ? "#fff" : "rgba(130,215,255,.95)"; g.lineWidth = 1;
      g.beginPath(); g.moveTo(haut[0][0] + 4, haut[0][1]); for (let j = 1; j <= Math.floor(N * 0.55); j++) g.lineTo(haut[j][0], haut[j][1]); g.stroke();
      g.strokeStyle = "rgba(0,229,255,.9)"; g.lineWidth = 1.2; g.beginPath(); g.moveTo(haut[N][0] - 3, haut[N][1] + 5); g.lineTo(bas[N][0] - 3, bas[N][1] - 6); g.stroke();
      if (c > 0.15) {
        // texte et icône : à plat, resserrés selon l'angle de la carte
        const largeurTexte = 2 * R * Math.sin(demi) * 0.9;
        g.save(); g.translate(CX + R * Math.sin(th), y + h / 2 + dep * 0); g.scale(Math.max(0.2, c), 1); g.globalAlpha = a * Math.min(1, c * 1.4);
        const couleur = q > 0.5 ? "#ffffff" : "#bfeaff", is = Math.min(16, h * 0.46);
        g.save(); g.translate(-largeurTexte / 2 + 4, -is / 2); g.scale(is / 24, is / 24); g.lineWidth = 1.5; g.lineCap = "round"; g.lineJoin = "round"; g.strokeStyle = couleur; g.stroke(icones[ic]); g.restore();
        g.textBaseline = "middle"; g.textAlign = "left";
        const ls = g as unknown as { letterSpacing: string };
        ls.letterSpacing = "1px"; g.fillStyle = "#fff"; g.font = `600 ${q > 0.5 ? fs + 1 : fs}px Orbitron,Consolas,monospace`; g.fillText(titre, -largeurTexte / 2 + 4 + is + 6, -h * 0.13);
        ls.letterSpacing = "0.6px"; g.fillStyle = "rgba(130,225,255,.9)"; g.font = "5.5px Consolas,monospace"; g.fillText(sous, -largeurTexte / 2 + 4 + is + 6, h * 0.25);
        ls.letterSpacing = "0px";
        g.restore();
      }
    }
    g.restore();
    if (avant && c > 0.5) {
      const xs = haut.map((p) => p[0]);
      zones.push({ id, x0: Math.min(...xs), x1: Math.max(...xs), y0: y, y1: y + h, c });
    }
  }

  function dessiner(t: number): void {
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height);
    g.setTransform(dpr * s, 0, 0, dpr * s, dpr * origX, dpr * origY);
    zones = [];
    const aff = sm((orb.cylindreOuvert() - 0.88) / 0.12);   // les cartes se posent quand le cylindre de l'orbe est dressé
    if (aff <= 0.005) return;
    // Géométrie de la recherche vocale : mêmes hauteur de carte, pas et départ de colonne
    const ch = 28, hb = ch - 3, gap = (HF - 2 * ry0 - 46 - ch) / 7;
    const clipHaut = TOP0 + ry0 * 0.6 + 4, clipBas = BY - ry0 - 12;
    g.save(); g.beginPath(); g.rect(CX - RX - 6, clipHaut, 2 * RX + 12, clipBas - clipHaut); g.clip();
    const R = RX * 0.9, TH_COL = 0, OFFSET_SOUS = 0;   // cartes centrées et droites : la recherche les courbe et les décale, pas le menu
    const pivot = (x: number): number => 1 - Math.pow(1 - cl(x / 0.38, 0, 1), 3);
    const nSous = groupe >= 0 ? GROUPES[groupe].entrees.length : 0;
    const y0 = TOP0 + ry0 + 22 + ((8 - (GROUPES.length + nSous * expand)) * gap) / 2;   // colonne centrée tant qu'elle n'est pas pleine
    const lg = lignes();
    const elements: { z: number; f: () => void }[] = [];
    GROUPES.forEach((gr, gi) => {
      const ligne = lg.findIndex((l) => l.gi === gi && l.si === -1);
      const y = y0 + (gi + (groupe >= 0 && gi > groupe ? nSous * expand : 0)) * gap;
      const p = pivot(t - tNiv - 0.1 - gi * 0.09);
      if (p <= 0) return;
      const th = TH_COL - (1 - p) * (Math.PI / 2), a = aff * cl(p * 3, 0, 1);
      elements.push({ z: Math.cos(th), f: () => bande(th, y, hb, a, 0.8, ligne === sel ? 1 : 0, gr.titre, gr.sous, gr.ic, ligne, 9.5) });
    });
    if (groupe >= 0 && expand > 0.01) GROUPES[groupe].entrees.forEach((en, si) => {
      const ligne = lg.findIndex((l) => l.gi === groupe && l.si === si);
      const y = y0 + (groupe + (si + 1) * expand) * gap, etat = etatBouton(en.id);
      const p = expandCible ? pivot(t - tExp - 0.1 - si * 0.09) : 1;
      if (p <= 0) return;
      const th = TH_COL + OFFSET_SOUS - (1 - p) * (Math.PI / 2), a = aff * cl(p * 3, 0, 1) * Math.min(1, expand * 3);
      elements.push({ z: Math.cos(th), f: () => bande(th, y, hb - 2, a, 0.66, ligne === sel ? 1 : etat.allume ? 0.5 : 0, en.titre, etat.badge || en.sous, en.ic, ligne, 8.5) });
    });
    elements.sort((u, v) => u.z - v.z).forEach((e) => e.f());
    g.restore();
  }

  function image(ms: number): void {
    boucle = requestAnimationFrame(image);
    expand += (expandCible - expand) * 0.18;
    if (expandCible === 0 && expand < 0.02) { expand = 0; groupe = -1; }
    if (ouvert && orb.modeActuel() !== "menu") fermer(false);   // la voix ou un panneau reprend la main
    if (ouvert && sx >= 0) {
      const z = zones.filter((q) => sx >= q.x0 && sx <= q.x1 && sy >= q.y0 && sy <= q.y1).sort((u, v) => v.c - u.c)[0];
      if (z) sel = z.id;
    }
    dessiner(ms / 1000);
    if (!ouvert && orb.cylindreOuvert() < 0.02) { cancelAnimationFrame(boucle); boucle = 0; }
  }

  function ouvrir(): void {
    if (ouvert || masque) return;
    ouvert = true; groupe = -1; expand = 0; expandCible = 0; sel = 0; tNiv = performance.now() / 1000 + 0.6;
    cv.style.pointerEvents = "auto"; disque.style.display = "none"; orb.setMenu(true);
    if (!boucle) boucle = requestAnimationFrame(image);
  }

  function fermer(retour = true): void {
    if (!ouvert) return;
    ouvert = false; cv.style.pointerEvents = "none"; orb.setMenu(false);
    if (retour) disque.style.display = "block";
  }

  function retour(): void { if (groupe >= 0 && expandCible === 1) { sel = groupe; expandCible = 0; sx = -1; } else fermer(); }

  function executer(id: string): void {
    const bouton = document.getElementById(id);
    const module = GROUPES.flatMap((gr) => gr.entrees).find((en) => en.id === id)?.module;
    fermer();
    // Une commande sans écran passe d'abord par la recherche de la roue ; celles qui ouvrent un panneau la jouent déjà elles-mêmes
    if (module) window.setTimeout(() => { void orb.chercher(undefined, module).then(() => bouton?.click()); }, 320);
    else window.setTimeout(() => bouton?.click(), 320);
  }

  /** Déplie (ou replie) un groupe ; ouvrir un autre groupe replie d'abord le précédent. */
  function deplier(gi: number): void {
    sx = -1;
    if (gi === groupe && expandCible === 1) { expandCible = 0; sel = gi; return; }
    groupe = gi; expand = 0; expandCible = 1; tExp = performance.now() / 1000; sel = gi + 1;
  }
  function activer(ligne: number): void {
    const l = lignes()[ligne];
    if (!l) return;
    if (l.si < 0) deplier(l.gi); else executer(GROUPES[l.gi].entrees[l.si].id);
  }

  const pointer = (e: MouseEvent): void => { sx = (e.clientX - origX) / s; sy = (e.clientY - origY) / s; };
  cv.addEventListener("mousemove", pointer);
  cv.addEventListener("mouseleave", () => { sx = -1; });
  cv.addEventListener("click", (e) => {
    pointer(e);
    const z = zones.filter((q) => sx >= q.x0 && sx <= q.x1 && sy >= q.y0 && sy <= q.y1).sort((u, v) => v.c - u.c)[0];
    if (!z) { retour(); return; }
    activer(z.id);
  });
  cv.addEventListener("contextmenu", (e) => { e.preventDefault(); retour(); });
  cv.addEventListener("wheel", (e) => {
    e.preventDefault();
    const n = lignes().length; sel = (sel + (e.deltaY > 0 ? 1 : -1) + n) % n;
  }, { passive: false });
  document.addEventListener("keydown", (e) => {
    if (!ouvert) return;
    if (e.key === "Escape") { retour(); e.preventDefault(); }
    else if (e.key === "ArrowUp" || e.key === "ArrowDown") { const n = lignes().length; sel = (sel + (e.key === "ArrowDown" ? 1 : n - 1)) % n; e.preventDefault(); }
    else if (e.key === "Enter") { activer(sel); e.preventDefault(); }
  });
  disque.addEventListener("click", ouvrir);

  // Le disque n'est cliquable que lorsque l'orbe est au repos et que le HUD est affiché
  window.setInterval(() => {
    const visible = !ouvert && !masque && orb.modeActuel() === "veille" && !document.body.classList.contains("loading");
    disque.style.display = visible ? "block" : "none";
  }, 250);

  (window as unknown as { _menuRoue?: { masquer: (m: boolean) => void } })._menuRoue = {
    masquer(m: boolean): void { masque = m; if (m) fermer(false); },
  };
}

/** Cache (ou rend) le menu : vues 3D plein écran, etc. */
export function masquerMenuRoue(m: boolean): void {
  (window as unknown as { _menuRoue?: { masquer: (m: boolean) => void } })._menuRoue?.masquer(m);
}
