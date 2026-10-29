// Le cylindre de l'orbe s'étire en écran tant qu'un panneau de résultat est affiché (recette, courses,
// état du système) ; les widgets météo / calendrier / musique, eux, attendent que l'écran soit ouvert puis
// s'y posent. On observe leur classe plutôt que de modifier chaque panneau : ouverture ou fermeture,
// quelle qu'en soit la cause (commande vocale, bouton, croix), le cylindre suit.
import { orb } from "./orb_state";

const jetons = new Map<string, number>();    // dernière demande d'ouverture par raison : une fermeture annule celle en cours
const attentes = new Map<string, number>();  // sondes « l'écran est-il ouvert ? »
const suiveurs = new Map<string, ResizeObserver>();  // repositionnent un widget posé dans l'écran quand sa taille change
let compteur = 0;

const reinitialiserPosition = (el: HTMLElement): void => { Object.assign(el.style, { left: "", top: "", right: "", bottom: "" }); };

/**
 * Fait apparaître un élément à la façon de JARVIS : il reste invisible pendant la recherche de la fiche (défilement,
 * arrêt sur le thème, envol à gauche), puis le cylindre s'ouvre en écran et l'élément apparaît. `centre` : l'élément
 * est posé au milieu de l'écran (widgets) ; sinon il reste où il est (panneaux déjà centrés par leur style).
 * `mot` impose le thème trouvé ; sans lui, la fiche suit la phrase prononcée.
 */
export function ouvrirEcran(raison: string, el: HTMLElement, mot = "", centre = false, module?: [categorie: string, sous: string | null]): void {
  const jeton = ++compteur;
  jetons.set(raison, jeton);
  el.style.visibility = "hidden";
  void orb.chercher(mot || undefined, module).then(() => {
    if (jetons.get(raison) !== jeton) { orb.setOuvert(raison, false); return; }  // fermé entre-temps
    orb.setOuvert(raison, true, el, centre);
    const debut = performance.now();
    const id = window.setInterval(() => {
      if (!orb.ecranOuvert() && performance.now() - debut < 3500) return;
      clearInterval(id); attentes.delete(raison);
      if (jetons.get(raison) !== jeton) return;
      if (centre) {
        const p = orb.emplacement(el);
        Object.assign(el.style, { left: `${p.left}px`, top: `${p.top}px`, right: "auto", bottom: "auto" });
      }
      el.style.visibility = "";
      el.style.animation = "none"; void el.offsetWidth; el.style.animation = "";  // rejoue l'apparition
      if (centre) {
        // La taille du widget peut changer (onglet météo, nouvelle ligne…) : l'écran du cylindre la suit, le widget reste dedans
        suiveurs.get(raison)?.disconnect();
        const suiveur = new ResizeObserver(() => {
          if (jetons.get(raison) !== jeton) return;
          const q = orb.emplacement(el);
          Object.assign(el.style, { left: `${q.left}px`, top: `${q.top}px` });
        });
        suiveur.observe(el);
        suiveurs.set(raison, suiveur);
      }
    }, 50);
    attentes.set(raison, id);
  });
}

/** Referme l'écran (ou annule l'ouverture en cours) : le cylindre reprend sa forme. */
export function fermerEcran(raison: string, el?: HTMLElement, centre = false): void {
  jetons.delete(raison);
  const id = attentes.get(raison);
  if (id !== undefined) { clearInterval(id); attentes.delete(raison); }
  suiveurs.get(raison)?.disconnect(); suiveurs.delete(raison);
  if (el) { el.style.visibility = ""; if (centre) reinitialiserPosition(el); }
  orb.setOuvert(raison, false);
}

// Éléments suivis par leur classe : ouverture ou fermeture, quelle qu'en soit la cause (voix, bouton, croix), l'écran suit.
// mot : thème imposé à la recherche ("" = celui de la phrase) ; centre : posé au milieu de l'écran.
const SURVEILLES: { raison: string; selecteur: string; visible: (el: HTMLElement) => boolean; mot: string; centre: boolean; module?: [string, string | null] }[] = [
  { raison: "widget-meteo", selecteur: "#weather-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["MÉTÉO", null] },
  { raison: "widget-calendrier", selecteur: "#calendar-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["AGENDA", "Calendrier"] },
  { raison: "widget-musique", selecteur: "#music-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["MUSIQUE", null] },
  ...([
    ["recette", "#recipe-modal"], ["courses", "#shopping-panel"], ["systeme", "#system-panel"], ["winget", "#winget-panel"],
    ["desinstallation", "#uninstaller-panel"], ["antivirus", "#av-panel"], ["coffre", "#vault-panel"],
  ] as [string, string][]).map(([raison, selecteur]) => ({
    raison, selecteur, mot: "", centre: false,
    visible: (el: HTMLElement) => el.classList.contains("visible") && !el.classList.contains("hidden"),
  })),
  { raison: "domotique", selecteur: "#ha-panel", visible: (el) => !el.classList.contains("hidden"), mot: "lumière", centre: false },
];

export function initCylindreOuvert(): void {
  for (const { raison, selecteur, visible, mot, centre, module } of SURVEILLES) {
    const el = document.querySelector(selecteur) as HTMLElement | null;
    if (!el) continue;
    let actif = false;
    const maj = (): void => {
      const v = visible(el);
      if (v && !actif) { actif = true; ouvrirEcran(raison, el, mot, centre, module); }
      else if (!v && actif) { actif = false; fermerEcran(raison, el, centre); }
    };
    new MutationObserver(maj).observe(el, { attributes: true, attributeFilter: ["class"] });
    maj();
  }
}
