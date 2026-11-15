// Les vues en grand (vues 3D, globe, salon d'agents, éditeur) sortent du cylindre : la roue trouve la fiche, l'écran du
// cylindre s'ouvre, puis la vue s'étend depuis cet écran jusqu'à sa taille ; la fermeture fait le trajet inverse.
// Le contenu est découpé par un clip-path animé (aucun changement de la vue elle-même) et un cadre lumineux suit le bord.
import { orb } from "./orb_state";

type Rect = { left: number; top: number; width: number; height: number };
type Module = [categorie: string, sous: string | null];

const jetons = new Map<string, number>();    // dernière demande par raison : une demande plus récente annule la précédente
const ouverts = new Set<string>();           // vues déjà étendues (leur fermeture se joue en retour)
const animations = new Map<string, Animation[]>();
let compteur = 0;

const DUREE_OUVERTURE = 850, DUREE_FERMETURE = 650, COURBE = "cubic-bezier(0.7, 0, 0.2, 1)";

/** clip-path « inset » qui découpe `r` dans l'élément dont la boîte est `boite`. */
const coupe = (r: Rect, boite: Rect): string =>
  `inset(${r.top - boite.top}px ${boite.left + boite.width - r.left - r.width}px ${boite.top + boite.height - r.top - r.height}px ${r.left - boite.left}px round 6px)`;
const PLEIN = "inset(0px 0px 0px 0px round 0px)";

const boiteDe = (el: HTMLElement): Rect => { const b = el.getBoundingClientRect(); return { left: b.left, top: b.top, width: b.width, height: b.height }; };

export function annuler(raison: string): void {
  for (const a of animations.get(raison) ?? []) a.cancel();
  animations.delete(raison);
}

/** Joue l'étirement du cylindre vers la vue (sens = 1) ou son retour (sens = -1) : découpe de la vue + cadre lumineux. */
function jouer(raison: string, el: HTMLElement, de: Rect, vers: Rect, sens: 1 | -1, fin: () => void): void {
  const cadre = document.createElement("div");
  Object.assign(cadre.style, {
    position: "fixed", zIndex: "100000", pointerEvents: "none", boxSizing: "border-box", borderRadius: "6px",
    border: "2px solid #8fe0ff", boxShadow: "0 0 18px rgba(0,229,255,0.8), inset 0 0 22px rgba(0,229,255,0.25)",
  });
  document.body.appendChild(cadre);
  const duree = sens > 0 ? DUREE_OUVERTURE : DUREE_FERMETURE;
  const [a, b] = sens > 0 ? [de, vers] : [vers, de];   // `de` = écran du cylindre, `vers` = vue en grand
  const pos = (r: Rect): Keyframe => ({ left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
  const aCadre = cadre.animate([{ ...pos(a), opacity: 1 }, { ...pos(b), opacity: 1, offset: 0.85 }, { ...pos(b), opacity: 0 }], { duration: duree, easing: COURBE, fill: "forwards" });
  const petit = { clipPath: coupe(de, vers) }, grand = { clipPath: PLEIN };
  const aVue = el.animate(sens > 0 ? [petit, grand] : [grand, petit], { duration: duree, easing: COURBE, fill: "forwards" });
  animations.set(raison, [aCadre, aVue]);
  aVue.onfinish = () => { cadre.remove(); animations.delete(raison); fin(); aVue.cancel(); };   // cancel : la découpe « fill » ne doit pas rester sur la vue
  aVue.oncancel = () => cadre.remove();
}

/**
 * Étend la vue `el` (déjà affichée par l'appelant) depuis l'écran du cylindre. `module` : fiche à trouver sur la roue ;
 * `apres` : appelé une fois la vue en place (par ex. masquer l'orbe qu'elle recouvre).
 */
export function ouvrirPleinEcran(raison: string, el: HTMLElement, module?: Module, apres?: () => void): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  annuler(raison);
  el.style.clipPath = "inset(50% 50% 50% 50%)"; el.style.pointerEvents = "none";
  void orb.chercher(undefined, module).then(() => {
    if (jetons.get(raison) !== jeton) return;
    orb.setOuvert(raison, true);
    const debut = performance.now();
    const id = window.setInterval(() => {
      if (jetons.get(raison) !== jeton) { clearInterval(id); return; }
      if (!orb.ecranOuvert() && performance.now() - debut < 3500) return;
      clearInterval(id);
      const cible = boiteDe(el);
      jouer(raison, el, orb.rectEcran(), cible, 1, () => {
        if (jetons.get(raison) !== jeton) return;
        el.style.clipPath = ""; el.style.pointerEvents = "";
        ouverts.add(raison);
        apres?.();
      });
    }, 50);
  });
}

/**
 * Referme la vue : l'appelant a déjà rendu l'orbe visible (`retour`), la vue se rétracte dans l'écran du cylindre, puis `fini`
 * la masque pour de bon. Si la vue n'avait pas fini de s'ouvrir, elle est simplement annulée.
 */
export function fermerPleinEcran(raison: string, el: HTMLElement, fini: () => void, retour?: () => void): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  const etendue = ouverts.delete(raison);
  annuler(raison);
  retour?.();
  if (!etendue) {
    el.style.clipPath = ""; el.style.pointerEvents = "";
    orb.setOuvert(raison, false);
    fini();
    return;
  }
  el.style.pointerEvents = "none";
  jouer(raison, el, orb.rectEcran(), boiteDe(el), -1, () => {
    if (jetons.get(raison) !== jeton) return;
    el.style.clipPath = ""; el.style.pointerEvents = "";
    orb.setOuvert(raison, false);
    fini();
  });
}

// ── Panneaux posés sur les côtés du cylindre : ils sortent du sol, comme ceux dessinés dans l'orbe (sol() de orb_cylindre.ts) ──
// Attribut data (et non style ou classe) : le panneau est observé sur ses classes et son style, et ses transitions de glissement
// latéral ne doivent pas se jouer pendant la sortie du sol. « attente » : invisible le temps de la recherche ; « anim » : en mouvement.
const ATTR_SOL = "data-sortie-sol";
const DUREE_SOL_OUVERTURE = 900, DUREE_SOL_FERMETURE = 650;
const lisse = (v: number): number => { v = Math.min(1, Math.max(0, v)); return v * v * (3 - 2 * v); };

/** Sortie (sens = 1) ou enfoncement (sens = -1) : le panneau se dresse de profil depuis une barre lumineuse au sol, ou fait l'inverse. */
export function jouerSol(raison: string, el: HTMLElement, sens: 1 | -1, fin: () => void): void {
  const b = el.getBoundingClientRect(), cx = b.left + b.width / 2, cy = b.top + b.height / 2, fy = orb.sol().y;
  const N = 24, duree = sens > 0 ? DUREE_SOL_OUVERTURE : DUREE_SOL_FERMETURE;
  const panneau: Keyframe[] = [], barre: Keyframe[] = [], ellipse: Keyframe[] = [];
  for (let i = 0; i <= N; i++) {
    const u = i / N, v = sens > 0 ? u : 1 - u, s = 1 - lisse(v), lueur = Math.sin(Math.PI * s);
    panneau.push({ offset: u, translate: `0px ${(fy - cy) * s * 0.92}px`, scale: `${1 - 0.93 * s} ${1 - 0.5 * s}`, opacity: v < 0.02 ? 0 : 1 });
    barre.push({ offset: u, transform: `scaleY(${(12 + 30 * (1 - s)) / 42})`, opacity: lueur > 0.05 ? 0.9 * lueur : 0 });
    ellipse.push({ offset: u, transform: `translate(-50%, -50%) scale(${(8 + 46 * s) / 54}, ${(2 + 9 * s) / 11})`, opacity: lueur > 0.05 ? 0.5 * lueur : 0 });
  }
  const lueurs = document.createElement("div");
  Object.assign(lueurs.style, { position: "fixed", left: `${cx}px`, top: `${fy}px`, width: "0", height: "0", zIndex: "100000", pointerEvents: "none" });
  const trait = document.createElement("div");
  Object.assign(trait.style, { position: "absolute", left: "-1.5px", top: "-42px", width: "3px", height: "42px", background: "#cfeeff", boxShadow: "0 0 14px #00e5ff", transformOrigin: "50% 100%", opacity: "0" });
  const anneau = document.createElement("div");
  Object.assign(anneau.style, { position: "absolute", left: "0", top: "0", width: "108px", height: "22px", boxSizing: "border-box", border: "1.2px solid #8fe0ff", borderRadius: "50%", opacity: "0" });
  lueurs.append(trait, anneau);
  document.body.appendChild(lueurs);
  const opts: KeyframeAnimationOptions = { duration: duree, easing: "linear", fill: "both" };
  el.setAttribute(ATTR_SOL, "anim");
  const aPanneau = el.animate(panneau, opts), aBarre = trait.animate(barre, opts), aAnneau = anneau.animate(ellipse, opts);
  animations.set(raison, [aPanneau, aBarre, aAnneau]);
  aPanneau.onfinish = () => {
    lueurs.remove(); animations.delete(raison);
    fin();
    void el.offsetWidth;                  // le changement d'état de fin se pose sans transition avant qu'elle ne soit rendue
    el.removeAttribute(ATTR_SOL); aPanneau.cancel();
  };
  aPanneau.oncancel = () => lueurs.remove();
}

/** Fait sortir du sol un panneau déjà affiché par l'appelant : invisible pendant la recherche de la fiche (le cylindre ne s'étend pas), puis il se dresse. */
export function ouvrirDuSol(raison: string, el: HTMLElement, module?: Module, apres?: () => void): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  annuler(raison);
  el.setAttribute(ATTR_SOL, "attente");
  void orb.chercher(undefined, module).then(() => {
    if (jetons.get(raison) !== jeton) return;
    orb.setOuvert(raison, false);         // rend l'orbe à son état : la recherche seule suffit, l'écran du cylindre reste fermé
    jouerSol(raison, el, 1, () => { ouverts.add(raison); apres?.(); });
  });
}

/** Enfonce le panneau dans le sol (il a été remis à l'état affiché par l'appelant), puis `fini` le masque pour de bon. */
export function fermerDansSol(raison: string, el: HTMLElement, fini: () => void): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  const sorti = ouverts.delete(raison);
  annuler(raison);
  if (!sorti) {                           // pas encore sorti (recherche en cours) : rien à rejouer
    orb.setOuvert(raison, false);
    fini();                               // l'attribut garde le panneau invisible et sans transition le temps que l'appelant le masque
    void el.offsetWidth;
    el.removeAttribute(ATTR_SOL);
    return;
  }
  jouerSol(raison, el, -1, () => { if (jetons.get(raison) === jeton) fini(); });
}

/**
 * Surveille un élément que d'autres modules affichent ou masquent à leur manière (style ou classes) : à l'affichage il sort
 * du cylindre, au masquage il y retourne avant de disparaître vraiment. `visible` : critère d'affichage (par défaut : ni
 * `display: none` ni classe « hidden ») ; `avant` : appelé juste avant la sortie (par ex. retirer ce qui était affiché) ;
 * `sol` : panneau posé sur un côté du cylindre, il sort du sol (et s'y enfonce) au lieu de s'étendre depuis le cylindre.
 */
export function surveillerPleinEcran(selecteur: string, raison: string, module: Module, opts: { visible?: (el: HTMLElement) => boolean; avant?: (el: HTMLElement) => void; sol?: boolean } = {}): void {
  const el = document.querySelector(selecteur) as HTMLElement | null;
  if (!el) return;
  const visible = opts.visible ?? ((e: HTMLElement) => getComputedStyle(e).display !== "none" && !e.classList.contains("hidden"));
  let actif = false, interne = false;
  let etat = { cls: el.className, display: el.style.display };   // dernier état « affiché » : c'est celui qu'on remet le temps du retour
  const maj = (): void => {
    if (interne) return;
    const v = visible(el);
    if (v && !actif) {
      actif = true; etat = { cls: el.className, display: el.style.display };
      opts.avant?.(el);
      (opts.sol ? ouvrirDuSol : ouvrirPleinEcran)(raison, el, module);
    } else if (v) {
      etat = { cls: el.className, display: el.style.display };
    } else if (!v && actif) {
      actif = false; interne = true;
      const masque = { cls: el.className, display: el.style.display }, anim = el.style.animation, trans = el.style.transition;
      // l'élément se remontre le temps du retour, sans transition ni animation d'apparition
      el.style.transition = "none"; el.style.animation = "none"; el.className = etat.cls; el.style.display = etat.display;
      (opts.sol ? fermerDansSol : fermerPleinEcran)(raison, el, () => {
        el.className = masque.cls; el.style.display = masque.display; el.style.animation = anim; el.style.transition = trans;
        window.setTimeout(() => { interne = false; maj(); }, 0);
      });
    }
  };
  new MutationObserver(maj).observe(el, { attributes: true, attributeFilter: ["class", "style"] });
  maj();
}
