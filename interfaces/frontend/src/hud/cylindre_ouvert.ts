// Le cylindre de l'orbe s'étire en écran tant qu'un panneau de résultat est affiché (recette, courses,
// état du système) ; les widgets météo / calendrier / musique, eux, attendent que l'écran soit ouvert puis
// s'y posent. On observe leur classe plutôt que de modifier chaque panneau : ouverture ou fermeture,
// quelle qu'en soit la cause (commande vocale, bouton, croix), le cylindre suit.
import { orb } from "./orb_state";
import { surveillerPleinEcran } from "./plein_ecran";
import { fermerPieces, ouvrirPieces, type PieceDef } from "./eclate";
import type { ContenuCylindre } from "../orb_cylindre";
import { centreAgenda, centreMeteo, centreMusique, piecesAgenda, piecesMeteo, piecesMusique } from "./pieces_widgets";
import { initOutilsEclates, piecesAide, piecesMaison, piecesMinuteurs, piecesReglages } from "./pieces_outils";
import { piecesAntivirus, piecesDesinstall, piecesLogiciels, piecesSysteme } from "./pieces_tableaux";

const DUREE_ENFONCEMENT = 500;               // animation widget-sink (widgets.css, 0,45 s) + marge
const jetons = new Map<string, number>();    // dernière demande d'ouverture par raison : une fermeture annule celle en cours
const attentes = new Map<string, number>();  // sondes « l'écran est-il ouvert ? »
const suiveurs = new Map<string, ResizeObserver>();  // repositionnent un widget posé dans l'écran quand sa taille change
let compteur = 0;

const reinitialiserPosition = (el: HTMLElement): void => { Object.assign(el.style, { left: "", top: "", right: "", bottom: "", transform: "", zIndex: "", position: "" }); };

/** Une nouvelle demande remplace l'affichage précédent : les autres widgets / panneaux ouverts se retirent. */
function fermerAutres(raison: string, el: HTMLElement): void {
  for (const s of SURVEILLES) {
    const autre = s.raison === raison ? null : document.querySelector(s.selecteur) as HTMLElement | null;
    if (!autre || autre === el || !s.visible(autre)) continue;
    if (s.centre) {
      autre.classList.remove("hud-revealed"); autre.classList.add("hud-sinking");
      window.setTimeout(() => autre.classList.remove("hud-sinking"), 480);
    } else { autre.classList.remove("visible"); autre.classList.add("hidden"); }
  }
}

/**
 * Fait apparaître un élément à la façon de JARVIS : il reste invisible pendant la recherche de la fiche (défilement,
 * arrêt sur le thème, envol à gauche), puis le cylindre s'ouvre en écran et l'élément apparaît. `centre` : l'élément
 * est posé au milieu de l'écran (widgets) ; sinon il reste où il est (panneaux déjà centrés par leur style).
 * `mot` impose le thème trouvé ; sans lui, la fiche suit la phrase prononcée.
 */
export function ouvrirEcran(raison: string, el: HTMLElement, mot = "", centre = false, module?: [categorie: string, sous: string | null]): void {
  fermerAutres(raison, el);
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
  if (el) {
    el.style.visibility = "";
    // un widget qui s'enfonce dans le sol le fait là où il est : sa position n'est rendue qu'à la fin de l'animation
    // (widgets comme panneaux déplacés à la main : ils retrouvent leur place d'origine, donc le bas du cylindre, à la prochaine ouverture)
    if (el.classList.contains("hud-sinking")) window.setTimeout(() => { if (!el.classList.contains("hud-revealed")) reinitialiserPosition(el); }, 500);
    else window.setTimeout(() => { if (!jetons.has(raison)) reinitialiserPosition(el); }, centre ? 0 : 450);
  }
  // Un widget posé dans l'écran s'enfonce d'abord (0,45 s) : le cylindre garde son écran jusque-là, sinon il se replierait sous lui
  if (centre && el) window.setTimeout(() => { if (!jetons.has(raison)) orb.setOuvert(raison, false); }, DUREE_ENFONCEMENT);
  else orb.setOuvert(raison, false);
}

// Éléments suivis par leur classe : ouverture ou fermeture, quelle qu'en soit la cause (voix, bouton, croix), l'écran suit.
// mot : thème imposé à la recherche ("" = celui de la phrase) ; centre : posé au milieu de l'écran.
// Les widgets (centre) se posent dans l'écran du cylindre ; les panneaux, eux, sortent du cylindre et s'étendent à leur taille (plein_ecran.ts).
const PIECES_TABLEAUX: Record<string, () => PieceDef[]> = { systeme: piecesSysteme, winget: piecesLogiciels, antivirus: piecesAntivirus, desinstallation: piecesDesinstall };
const SURVEILLES: { raison: string; selecteur: string; visible: (el: HTMLElement) => boolean; mot: string; centre: boolean; module?: [string, string | null]; pieces?: () => PieceDef[]; contenu?: () => ContenuCylindre }[] = [
  { raison: "widget-meteo", selecteur: "#weather-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["MÉTÉO", null], pieces: piecesMeteo, contenu: centreMeteo },
  { raison: "widget-calendrier", selecteur: "#calendar-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["AGENDA", "Calendrier"], pieces: piecesAgenda, contenu: centreAgenda },
  { raison: "widget-musique", selecteur: "#music-hud", visible: (el) => el.classList.contains("hud-revealed"), mot: "", centre: true, module: ["MUSIQUE", null], pieces: piecesMusique, contenu: centreMusique },
  ...([
    ["recette", "#recipe-modal", "CUISINE", "Recettes"], ["courses", "#shopping-panel", "CUISINE", "Liste de courses"], ["systeme", "#system-panel", "SYSTÈME", null],
    ["winget", "#winget-panel", "LOGICIELS", "Mises à jour"], ["desinstallation", "#uninstaller-panel", "LOGICIELS", "Désinstaller"],
    ["antivirus", "#av-panel", "SÉCURITÉ", "Antivirus"], ["coffre", "#vault-panel", "SÉCURITÉ", "Coffre-fort"],
  ] as [string, string, string, string | null][]).map(([raison, selecteur, cat, sous]) => ({
    raison, selecteur, mot: "", centre: false, module: [cat, sous] as [string, string | null], pieces: PIECES_TABLEAUX[raison],
    visible: (el: HTMLElement) => el.classList.contains("visible") && !el.classList.contains("hidden"),
  })),
  { raison: "domotique", selecteur: "#ha-panel", visible: (el) => !el.classList.contains("hidden"), mot: "", centre: false, module: ["MAISON", "Lumières"], pieces: piecesMaison },
  // Aide, minuteurs et réglages : pièces éclatées aussi (hud/pieces_outils.ts). Les anciens éléments restent dans le DOM pour porter l'état.
  { raison: "aide", selecteur: "#help-overlay", visible: (el) => el.classList.contains("visible"), mot: "", centre: false, module: ["JARVIS", "Aide"], pieces: piecesAide },
  { raison: "minuteur", selecteur: "#timer-hud", visible: (el) => el.style.display !== "none" && !el.classList.contains("hidden"), mot: "", centre: false, module: ["ALARMES", "Minuteur"], pieces: piecesMinuteurs },
  // La page complète des réglages (« reglages-classique ») garde l'ancienne sortie du cylindre
  { raison: "parametres", selecteur: "#settings-modal", visible: (el) => el.classList.contains("visible") && !document.body.classList.contains("reglages-classique"), mot: "", centre: false, module: ["JARVIS", "Paramètres"], pieces: piecesReglages },
];

export function initCylindreOuvert(): void {
  document.body.classList.add("hud-eclate");   // les anciennes boîtes des widgets centraux se masquent : leurs pièces éclatées les remplacent (eclate.ts)
  for (const { raison, selecteur, visible, mot, centre, module, pieces, contenu } of SURVEILLES) {
    const el = document.querySelector(selecteur) as HTMLElement | null;
    if (!el) continue;
    if (!centre && module && !pieces) { surveillerPleinEcran(selecteur, raison, module, { visible, avant: (e) => fermerAutres(raison, e) }); continue; }
    let actif = false;
    const maj = (): void => {
      const v = visible(el);
      if (v && !actif) { actif = true; if (pieces) { fermerAutres(raison, el); ouvrirPieces(raison, pieces(), module, false, contenu); } else ouvrirEcran(raison, el, mot, centre, module); }
      else if (!v && actif) { actif = false; if (pieces) fermerPieces(raison); else fermerEcran(raison, el, centre); }
    };
    new MutationObserver(maj).observe(el, { attributes: true, attributeFilter: ["class", "style"] });
    if (raison === "parametres") new MutationObserver(maj).observe(document.body, { attributes: true, attributeFilter: ["class"] });   // bascule vers la page complète
    maj();
  }
  initOutilsEclates();
  // La page complète des réglages (clés API…) sort encore du cylindre, comme avant
  surveillerPleinEcran("#settings-modal", "parametres-classique", ["JARVIS", "Paramètres"], { visible: (el) => el.classList.contains("visible") && document.body.classList.contains("reglages-classique") });
  // Salon d'agents et éditeur de code : fenêtres affichées par d'autres modules, elles sortent aussi du cylindre
  surveillerPleinEcran("#swarm-lounge-hud", "salon-agents", ["CRÉATION", "Projet"]);
  surveillerPleinEcran("#code-editor-modal", "editeur-code", ["CRÉATION", "Éditeur"]);
  // Aide (liste des commandes), minuteur, créateur de site, atelier de projets : même chose. Les panneaux latéraux météo et capteurs,
  // posés sur les côtés du cylindre, sortent du sol (comme les panneaux de l'orbe) et s'y enfoncent : le cylindre ne s'étend pas pour eux.
  surveillerPleinEcran("#website-builder-hud", "createur-site", ["CRÉATION", "Site web"]);
  surveillerPleinEcran("#dev-swarm-hud", "atelier-projet", ["CRÉATION", "Projet"]);
  surveillerPleinEcran("#weather-panel", "panneau-meteo", ["MÉTÉO", null], { visible: (el) => el.classList.contains("wp-visible"), sol: true });
  surveillerPleinEcran("#temp-panel", "panneau-capteurs", ["MAISON", "Capteurs"], { visible: (el) => el.classList.contains("tp-visible"), sol: true });
}
