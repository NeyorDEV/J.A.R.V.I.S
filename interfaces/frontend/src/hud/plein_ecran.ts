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

function annuler(raison: string): void {
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

/**
 * Surveille un élément que d'autres modules affichent ou masquent à leur manière (style ou classes) : à l'affichage il sort
 * du cylindre, au masquage il y retourne avant de disparaître vraiment. `visible` : critère d'affichage (par défaut : ni
 * `display: none` ni classe « hidden ») ; `avant` : appelé juste avant la sortie (par ex. retirer ce qui était affiché).
 */
export function surveillerPleinEcran(selecteur: string, raison: string, module: Module, opts: { visible?: (el: HTMLElement) => boolean; avant?: (el: HTMLElement) => void } = {}): void {
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
      ouvrirPleinEcran(raison, el, module);
    } else if (v) {
      etat = { cls: el.className, display: el.style.display };
    } else if (!v && actif) {
      actif = false; interne = true;
      const masque = { cls: el.className, display: el.style.display }, anim = el.style.animation, trans = el.style.transition;
      // l'élément se remontre le temps du retour, sans transition ni animation d'apparition
      el.style.transition = "none"; el.style.animation = "none"; el.className = etat.cls; el.style.display = etat.display;
      fermerPleinEcran(raison, el, () => {
        el.className = masque.cls; el.style.display = masque.display; el.style.animation = anim; el.style.transition = trans;
        window.setTimeout(() => { interne = false; maj(); }, 0);
      });
    }
  };
  new MutationObserver(maj).observe(el, { attributes: true, attributeFilter: ["class", "style"] });
  maj();
}
