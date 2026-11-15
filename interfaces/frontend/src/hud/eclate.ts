// Panneaux éclatés : un widget n'est plus une boîte posée dans l'écran du cylindre mais plusieurs « pièces » de formes variées,
// posées de part et d'autre de lui. Elles sortent du sol (même mécanique que les panneaux latéraux : plein_ecran.ts) et s'y enfoncent.
// Chaque pièce se redessine à la demande (`rafraichirPieces`) sans rejouer son apparition, et peut s'animer à chaque image (`tick`).
import { orb } from "./orb_state";
import type { ContenuCylindre } from "../orb_cylindre";
import { jouerSol, annuler } from "./plein_ecran";

export type Forme = "rect" | "cut" | "cut2" | "libre";
export interface PieceDef {
  id: string;
  cote: "g" | "d";                 // à gauche ou à droite du cylindre
  rang: number;                    // 0 = en haut, 1 = au milieu, 2 = en bas
  w: number; h: number;            // taille de conception en pixels (agrandie ensuite selon la hauteur de l'écran)
  forme?: Forme;                   // rect : coins repères ; cut / cut2 : biseauté à droite / à gauche ; libre : sans cadre
  ecart?: number;                  // décalage supplémentaire vers l'extérieur, en pixels de conception (pièces en quinconce)
  classe?: string;                 // classe CSS ajoutée à la pièce (couleur d'alerte…)
  titre?: string;                  // petit titre de la pièce (décodé à l'apparition)
  croix?: () => void;              // croix de fermeture
  rendre: (corps: HTMLElement) => void;
  tick?: (corps: HTMLElement, t: number) => void;
}
type Module = [categorie: string, sous: string | null];
interface Ouvert { els: HTMLElement[]; defs: PieceDef[]; sortis: boolean }

const ouverts = new Map<string, Ouvert>();
const centres = new Map<string, () => ContenuCylindre>();   // contenu à afficher au milieu du cylindre, par jeu (le plus récent l'emporte)
const masquants = new Set<string>();   // jeux ouverts qui occupent la zone de la fiche du module : celle-ci s'efface tant qu'il y en a
const majFiche = (): void => orb.masquerFiche(masquants.size > 0);
const jetons = new Map<string, number>();
let compteur = 0, couche: HTMLElement | null = null, raf = 0;
const MARGE = 12, ECART_CYLINDRE = 44, ESPACE_MIN = 16, ESPACE_MAX = 64, GLYPHES = "01#/<>%$";
const RANGS = [0.0, 0.43, 0.8];   // part de la hauteur du cylindre (du haut vers le sol) où commence chaque rang

function laCouche(): HTMLElement {
  if (couche && couche.isConnected) return couche;
  couche = document.createElement("div");
  couche.id = "eclate-couche";
  document.body.appendChild(couche);
  return couche;
}

const bornes = (v: number, a: number, b: number): number => Math.min(b, Math.max(a, v));

type Geo = ReturnType<typeof orb.geometrie>;

/** Taille d'une pièce à l'écran : agrandie selon la hauteur du cylindre, bornée par la place disponible entre le bord de l'écran et lui ; `f` : réduction commune d'un côté trop chargé. */
function dimensions(d: PieceDef, g: Geo, f: number): { z: number; w: number; h: number; ec: number } {
  const span = Math.max(240, g.solY - g.haut);
  const libre = d.cote === "g" ? g.cx - g.rayon - ECART_CYLINDRE - MARGE : g.largeur - (g.cx + g.rayon + ECART_CYLINDRE) - MARGE;
  const fin = !!d.classe?.includes("ec-fin");   // style fin : textes de 7 à 9 px de conception, donc agrandi davantage (proportions des maquettes)
  const zBase = fin ? bornes(span / 300, 1, 1.9) : bornes(span / 430, 0.85, 1.45);
  const z = Math.min(zBase, Math.max(0.5, libre / (d.w + (d.ecart ?? 0)))) * f;
  return { z, w: d.w * z, h: d.h * z, ec: (d.ecart ?? 0) * z };
}

/** Place une pièce à la hauteur `top` ; elle ne passe jamais sur le cylindre (côté et écart calculés depuis son bord). Renvoie son bord bas. */
function placer(el: HTMLElement, d: PieceDef, g: Geo, f: number, top: number): number {
  const { z, w, h, ec } = dimensions(d, g, f);
  const t = Math.min(top, g.hauteur - h - MARGE);
  const left = d.cote === "g" ? g.cx - g.rayon - ECART_CYLINDRE - w - ec : g.cx + g.rayon + ECART_CYLINDRE + ec;
  Object.assign(el.style, { left: `${Math.max(MARGE, left)}px`, top: `${t}px`, width: `${w}px`, height: `${h}px` });
  const dedans = el.firstElementChild as HTMLElement;
  Object.assign(dedans.style, { width: `${d.w}px`, height: `${d.h}px`, transform: `scale(${z})` });
  return t + h;
}

/**
 * Place tout un jeu. Une pièce seule d'un côté (notification) prend sa zone (rang). Plusieurs pièces d'un même côté se répartissent
 * de haut en bas avec un espace entre elles : elles ne se touchent ni ne se recouvrent jamais ; si le côté est trop chargé pour la
 * hauteur de l'écran, elles rétrécissent ensemble.
 */
function placerJeu(els: HTMLElement[], defs: PieceDef[]): void {
  const g = orb.geometrie();
  const span = Math.max(240, g.solY - g.haut), bas = Math.min(g.hauteur - MARGE, g.solY + 60), dispo = bas - g.haut;
  for (const cote of ["g", "d"] as const) {
    const idx = defs.map((_, i) => i).filter((i) => defs[i].cote === cote).sort((a, b) => defs[a].rang - defs[b].rang);
    if (!idx.length) continue;
    if (idx.length === 1) { placer(els[idx[0]], defs[idx[0]], g, 1, g.haut + span * RANGS[bornes(defs[idx[0]].rang, 0, 2)]); continue; }
    const somme = idx.reduce((s, i) => s + dimensions(defs[i], g, 1).h, 0), n = idx.length;
    const f = somme + ESPACE_MIN * (n - 1) > dispo ? Math.max(0.6, (dispo - ESPACE_MIN * (n - 1)) / somme) : 1;
    const espace = Math.min(ESPACE_MAX, Math.max(ESPACE_MIN, (dispo - somme * f) / (n - 1)));
    let top = g.haut;
    idx.forEach((i) => { top = placer(els[i], defs[i], g, f, top) + espace; });
  }
}

function creer(d: PieceDef, raison: string): HTMLElement {
  const el = document.createElement("div");
  el.className = `ec-piece ec-${d.forme ?? "rect"}${d.classe ? ` ${d.classe}` : ""}`;
  el.dataset.piece = d.id; el.dataset.raison = raison; el.dataset.cote = d.cote;
  el.style.opacity = "0";
  el.innerHTML = `<div class="ec-in"><i class="ec-lt"></i><i class="ec-sc"></i>${d.titre ? `<div class="ec-tete"><span class="ec-lab" data-d="${d.titre}">${d.titre}</span>${d.croix ? `<button type="button" class="ec-x" aria-label="Fermer">✕</button>` : ""}</div>` : ""}<div class="ec-corps"></div></div>`;
  (el.querySelector(".ec-x") as HTMLElement | null)?.addEventListener("click", (e) => { e.stopPropagation(); d.croix?.(); });
  d.rendre(corpsDe(el));
  return el;
}

const corpsDe = (el: HTMLElement): HTMLElement => el.querySelector(".ec-corps") as HTMLElement;

function boucle(): void {
  const t = performance.now() / 1000;
  const dernier = [...centres.values()].pop();
  if (dernier) orb.setContenu(dernier());
  for (const o of ouverts.values()) o.els.forEach((el, i) => { if (!el.isConnected) return; o.defs[i].tick?.(corpsDe(el), t); decoder(el, t); });
  raf = ouverts.size ? requestAnimationFrame(boucle) : 0;
}

/** Les titres se décodent à l'apparition (glyphes qui se figent de gauche à droite), comme sur la fiche du module. */
function decoder(el: HTMLElement, t: number): void {
  const lab = el.querySelector(".ec-lab[data-d]") as HTMLElement | null;
  if (!lab) return;
  const t0 = Number(el.dataset.t0 ?? 0);
  if (!t0) return;
  const p = Math.min(1, (t - t0) / 0.9), final = lab.dataset.d ?? "";
  if (p >= 1) { if (lab.textContent !== final) lab.textContent = final; return; }
  let s = "";
  for (let i = 0; i < final.length; i++) s += p * (final.length + 3) > i + 2 || final[i] === " " ? final[i] : GLYPHES[(Math.floor(t * 18) + i * 3) % GLYPHES.length];
  lab.textContent = s;
}

function replacerTout(): void { for (const o of ouverts.values()) placerJeu(o.els, o.defs); }
window.addEventListener("resize", replacerTout);

/** Ouvre le jeu de pièces : la roue cherche la fiche, puis les pièces sortent du sol l'une après l'autre. */
/** `direct` : sans attendre la recherche de la roue (alertes, notifications : elles ne doivent pas être retardées). */
export function ouvrirPieces(raison: string, defs: PieceDef[], module?: Module, direct = false, centre?: () => ContenuCylindre): void {
  retirer(raison);
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  const els = defs.map((d) => creer(d, raison));
  els.forEach((el) => laCouche().appendChild(el));
  placerJeu(els, defs);
  const o: Ouvert = { els, defs, sortis: false };
  ouverts.set(raison, o);
  if (!raf) raf = requestAnimationFrame(boucle);
  const sortir = (): void => {
    if (jetons.get(raison) !== jeton) return;
    if (!direct) { masquants.add(raison); majFiche(); }
    if (centre) centres.set(raison, centre);
    replacerTout();
    els.forEach((el, i) => window.setTimeout(() => {
      if (jetons.get(raison) !== jeton || !el.isConnected) return;
      el.style.opacity = ""; el.dataset.t0 = String(performance.now() / 1000);
      jouerSol(`${raison}#${defs[i].id}`, el, 1, () => { if (i === els.length - 1) o.sortis = true; });
    }, i * 170));
  };
  if (direct) { sortir(); return; }
  void orb.chercher(undefined, module).then(() => {
    if (jetons.get(raison) !== jeton) return;
    orb.setOuvert(raison, false);         // la recherche seule suffit : l'écran du cylindre reste fermé
    sortir();
  });
}

/** Redessine le contenu des pièces ouvertes (nouvelles données) sans rejouer leur apparition. */
export function rafraichirPieces(raison: string): void {
  const o = ouverts.get(raison);
  if (o) o.els.forEach((el, i) => o.defs[i].rendre(corpsDe(el)));
}

export const piecesOuvertes = (raison: string): boolean => ouverts.has(raison);

function retirer(raison: string): void {
  const o = ouverts.get(raison);
  if (!o) return;
  o.defs.forEach((d) => annuler(`${raison}#${d.id}`));
  o.els.forEach((el) => el.remove());
  ouverts.delete(raison);
}

/** Referme le jeu : les pièces s'enfoncent dans le sol (en ordre inverse), puis disparaissent. */
export function fermerPieces(raison: string): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  const o = ouverts.get(raison);
  centres.delete(raison); if (!centres.size) orb.setContenu(null);
  if (!o) { orb.setOuvert(raison, false); masquants.delete(raison); majFiche(); return; }
  const n = o.els.length;
  o.els.forEach((el, i) => {
    const visible = el.style.opacity !== "0";
    window.setTimeout(() => {
      if (jetons.get(raison) !== jeton) return;
      if (!visible || !el.isConnected) { el.remove(); return; }
      annuler(`${raison}#${o.defs[i].id}`);
      jouerSol(`${raison}#${o.defs[i].id}`, el, -1, () => { el.remove(); if (jetons.get(raison) === jeton && o.els.every((e) => !e.isConnected)) ouverts.delete(raison); });
    }, (n - 1 - i) * 90);
  });
  window.setTimeout(() => { if (jetons.get(raison) === jeton) { retirer(raison); orb.setOuvert(raison, false); masquants.delete(raison); majFiche(); } }, 90 * n + 900);
}
