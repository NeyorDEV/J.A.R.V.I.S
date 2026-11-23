/**
 * Langue du HUD (français / anglais).
 *
 * Les textes de l'interface sont écrits en français dans le code et dans index.html. En anglais, ce module les traduit à l'affichage :
 * texte des nœuds, title / placeholder / aria-label / alt, observés en continu (MutationObserver) pour couvrir aussi les panneaux créés plus tard.
 * Le dictionnaire (en.json, fait par tools/i18n_extraire.py + tools/i18n_traduire.py) est indexé par le texte français, nombres remplacés par {0}, {1}…
 * Un texte absent du dictionnaire reste en français. Le français est restauré à l'identique en changeant de langue.
 * `t("texte")` sert aux textes dessinés hors DOM (canvas) ou assemblés en code.
 */
import dictionnaire from "./en.json";
import { wsRef } from "../ws_link";

export type Langue = "fr" | "en";

const EN = dictionnaire as Record<string, string>;
const CLE_STOCKAGE = "jarvis-langue";
const ATTRIBUTS = ["title", "placeholder", "aria-label", "alt"];
const NOMBRE = /\d+(?:[.,]\d+)?/g;
const IGNORES = new Set(["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"]);

let langue: Langue = "fr";
let observateur: MutationObserver | null = null;
const textes = new WeakMap<Node, { fr: string; en: string }>();
const attributs = new WeakMap<Element, Record<string, { fr: string; en: string }>>();
const ecouteurs = new Set<(l: Langue) => void>();

export function langueActuelle(): Langue {
  return langue;
}

/** Locale pour les dates et les nombres (toLocaleString…). */
export function locale(): string {
  return langue === "en" ? "en-GB" : "fr-FR";
}

/** Nom du jour (0 = dimanche) ou du mois (0 = janvier) en MAJUSCULES dans la langue courante, long ou abrégé (« JEUDI » / « JEU. », « NOVEMBRE » / « NOV. »). */
export function nomJour(i: number, court = false): string {
  return new Intl.DateTimeFormat(locale(), { weekday: court ? "short" : "long" }).format(new Date(2024, 0, 7 + i)).toUpperCase();
}
export function nomMois(i: number, court = false): string {
  return new Intl.DateTimeFormat(locale(), { month: court ? "short" : "long" }).format(new Date(2024, i, 15)).toUpperCase();
}

/** Appelé à chaque changement de langue (pour redessiner ce qui n'est pas dans le DOM). */
export function surChangementLangue(fn: (l: Langue) => void): void {
  ecouteurs.add(fn);
}

/** Index « clé en MAJUSCULES → clé » : les textes dessinés sur canvas sont souvent mis en majuscules par le code (« ENTRÉE AUDIO · MICRO »). */
let majuscules: Map<string, string> | null = null;
function cleDepuisMajuscules(maj: string): string | undefined {
  if (!majuscules) {
    majuscules = new Map();
    for (const cle of Object.keys(EN)) majuscules.set(cle.toUpperCase(), cle);
  }
  return majuscules.get(maj);
}

/**
 * Modèles du dictionnaire (clés avec {0}, {1}… : « Désinstaller {0} ? », « {0} moteur{1} disponible{2} ») : un texte assemblé avec un nom ou un pluriel ne correspond à aucune clé exacte
 * (seuls les nombres sont remplacés), mais correspond à un modèle ; les morceaux variables (nom, « s ») sont repris tels quels, ou traduits s'ils sont eux-mêmes dans le dictionnaire.
 */
interface Modele { re: RegExp; en: string; indices: number[]; poids: number }
let modeles: Modele[] | null = null;
const reponsesModeles = new Map<string, string | null>();

function chargerModeles(): Modele[] {
  if (modeles) return modeles;
  modeles = [];
  for (const [cle, en] of Object.entries(EN)) {
    if (!/\{\d+\}/.test(cle)) continue;
    const fixe = cle.replace(/\{\d+\}/g, "");
    if (fixe.replace(/[^A-Za-zÀ-ÿ]/g, "").length < 4) continue; // « {0} {1} » : trop vague
    const indices: number[] = [];
    const motif = cle
      .split(/(\{\d+\})/)
      .map((morceau) => {
        const m = morceau.match(/^\{(\d+)\}$/);
        if (m) { indices.push(Number(m[1])); return "(.*?)"; }
        return morceau.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      })
      .join("");
    modeles.push({ re: new RegExp(`^${motif}$`, "s"), en, indices, poids: fixe.length });
  }
  modeles.sort((a, b) => b.poids - a.poids); // le plus précis d'abord
  return modeles;
}

const MOTS_FR = new Set("le la les un une des du de au aux et ou je vous votre vos ce cette est sont pour avec dans sur pas plus mon ma mes aucun aucune toute tous trois deux quatre cinq jours jour heures heure minutes".split(" "));
function resteFrancais(texte: string): boolean {
  return /[àâçéèêëîïôùûüœ]/i.test(texte) || (texte.toLowerCase().match(/[a-zà-ÿ]+/g) ?? []).some((m) => MOTS_FR.has(m));
}

function parModele(brut: string): string | null {
  if (reponsesModeles.has(brut)) return reponsesModeles.get(brut) ?? null;
  let sortie: string | null = null;
  for (const m of chargerModeles()) {
    const r = m.re.exec(brut);
    if (!r) continue;
    const valeurs: string[] = [];
    m.indices.forEach((idx, i) => { const v = r[i + 1] ?? ""; valeurs[idx] = chercher(v) ?? v; });
    sortie = m.en.replace(/\{(\d+)\}/g, (_, i) => valeurs[Number(i)] ?? "");
    if (resteFrancais(sortie)) sortie = null; // un morceau variable resté français (« in trois days à 9 h 30 ») : mieux vaut tout laisser en français, ou le faire traduire en entier par le serveur
    break;
  }
  if (reponsesModeles.size > 5000) reponsesModeles.clear();
  reponsesModeles.set(brut, sortie);
  return sortie;
}

/** Traduit un texte français (avec ses nombres) ; renvoie null s'il n'est pas dans le dictionnaire. */
function chercher(fr: string): string | null {
  const brut = fr.replace(/\s+/g, " ").trim();
  if (!brut) return null;
  const nombres: string[] = [];
  const cle = brut.replace(NOMBRE, (n) => `{${nombres.push(n) - 1}}`);
  let en = EN[cle];
  if (en === undefined && cle === cle.toUpperCase()) {
    const origine = cleDepuisMajuscules(cle);
    if (origine !== undefined) en = EN[origine].toUpperCase();
  }
  if (en === undefined && cle.includes(" · ")) {   // « Voix · Profil vocal » : chaque morceau est traduit à part
    const morceaux = cle.split(" · ").map((m) => EN[m] ?? (m === m.toUpperCase() && cleDepuisMajuscules(m) !== undefined ? EN[cleDepuisMajuscules(m)!].toUpperCase() : undefined));
    if (morceaux.some((m) => m !== undefined)) en = cle.split(" · ").map((m, i) => morceaux[i] ?? m).join(" · ");
  }
  if (en === undefined) {
    const modele = parModele(brut);
    if (modele === null) return null;
    return (fr.match(/^\s*/)?.[0] ?? "") + modele + (fr.match(/\s*$/)?.[0] ?? "");
  }
  const rendu = en.replace(/\{(\d+)\}/g, (_, i) => nombres[Number(i)] ?? "");
  const debut = fr.match(/^\s*/)?.[0] ?? "";
  const fin = fr.match(/\s*$/)?.[0] ?? "";
  return debut + rendu + fin;
}

/** Texte français → texte dans la langue courante (inchangé en français ou si non traduit). */
export function t(fr: string): string {
  return langue === "en" ? (chercher(fr) ?? fr) : fr;
}

function traiterTexte(n: Text): void {
  const v = n.nodeValue ?? "";
  const m = textes.get(n);
  if (langue === "en") {
    const fr = m && v === m.en ? m.fr : v;
    const en = chercher(fr);
    if (en !== null && en !== v) {
      textes.set(n, { fr, en });
      n.nodeValue = en;
    } else if (m && v !== m.en) {
      textes.delete(n); // le code de l'appli a réécrit le texte : nouvelle valeur d'origine
    }
  } else if (m) {
    if (v === m.en) n.nodeValue = m.fr;
    textes.delete(n);
  }
}

function traiterAttributs(el: Element): void {
  for (const nom of ATTRIBUTS) {
    const v = el.getAttribute(nom);
    if (v === null) continue;
    const memo = attributs.get(el) ?? {};
    const m = memo[nom];
    if (langue === "en") {
      const fr = m && v === m.en ? m.fr : v;
      const en = chercher(fr);
      if (en !== null && en !== v) {
        memo[nom] = { fr, en };
        attributs.set(el, memo);
        el.setAttribute(nom, en);
      }
    } else if (m) {
      if (v === m.en) el.setAttribute(nom, m.fr);
      delete memo[nom];
    }
  }
}

function ignore(n: Node): boolean {
  const parent = n.nodeType === Node.TEXT_NODE ? n.parentElement : (n as Element);
  return !parent || IGNORES.has(parent.tagName) || parent.closest("[data-i18n-skip]") !== null || (parent as HTMLElement).isContentEditable;
}

function parcourir(racine: Node): void {
  if (racine.nodeType === Node.TEXT_NODE) {
    if (!ignore(racine)) traiterTexte(racine as Text);
    return;
  }
  if (racine.nodeType !== Node.ELEMENT_NODE || ignore(racine)) return;
  const el = racine as Element;
  traiterAttributs(el);
  for (const e of el.querySelectorAll("*")) traiterAttributs(e);
  const marcheur = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  for (let n = marcheur.nextNode(); n; n = marcheur.nextNode()) if (!ignore(n)) traiterTexte(n as Text);
}

function surMutations(liste: MutationRecord[]): void {
  if (langue !== "en") return;
  for (const m of liste) {
    if (m.type === "childList") m.addedNodes.forEach((n) => parcourir(n));
    else if (m.type === "characterData") {
      if (!ignore(m.target)) traiterTexte(m.target as Text);
    } else if (m.type === "attributes" && m.target.nodeType === Node.ELEMENT_NODE) traiterAttributs(m.target as Element);
  }
}

function appliquer(): void {
  document.documentElement.lang = langue;
  parcourir(document.body);
  if (langue === "en") {
    const titre = chercher(document.title);
    if (titre) document.title = titre;
  }
  ecouteurs.forEach((fn) => fn(langue));
}

/** Change la langue du HUD (mémorisée dans ce navigateur). `diffuser: false` quand le changement vient du backend. */
export function definirLangue(l: Langue): void {
  if (l !== "fr" && l !== "en") return;
  const change = l !== langue;
  langue = l;
  try {
    localStorage.setItem(CLE_STOCKAGE, l);
  } catch {
    /* stockage indisponible : la langue reste valable pour cette session */
  }
  if (change) appliquer();
}

/** Les textes dessinés sur canvas (cylindre, panneaux latéraux, horloge) passent aussi par le dictionnaire ; mémorisé car appelé à chaque image. */
function traduireCanvas(): void {
  const original = CanvasRenderingContext2D.prototype.fillText;
  const memo = new Map<string, string>();
  CanvasRenderingContext2D.prototype.fillText = function (this: CanvasRenderingContext2D, texte: string, x: number, y: number, max?: number) {
    if (langue === "en" && typeof texte === "string" && texte.length > 1 && texte.length < 200) {
      let en = memo.get(texte);
      if (en === undefined) {
        en = chercher(texte) ?? texte;
        if (memo.size > 3000) memo.clear();
        memo.set(texte, en);
      }
      texte = en;
    }
    return max === undefined ? original.call(this, texte, x, y) : original.call(this, texte, x, y, max);
  };
  surChangementLangue(() => memo.clear());
}

/** À appeler une fois au démarrage, avant les panneaux : lit la langue mémorisée et observe le DOM. */
export function initI18n(): void {
  try {
    const v = localStorage.getItem(CLE_STOCKAGE);
    if (v === "en" || v === "fr") langue = v;
  } catch {
    /* stockage indisponible */
  }
  traduireCanvas();
  observateur = new MutationObserver(surMutations);
  observateur.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRIBUTS });
  if (langue === "en") appliquer();
}

// ── Textes dynamiques venus du serveur (cartes, confirmations, écrans de module) ─────────────────────────────────
// Écrits en français côté Python : le dictionnaire du HUD d'abord, sinon le serveur les traduit (Gemini, cache) ; au bout de 4 s ou sans connexion, le texte reste en français.

const attente = new Map<string, (textes: string[]) => void>();
let compteur = 0;

export function recevoirTraduction(m: { id?: string; textes?: string[] }): void {
  if (!m.id) return;
  attente.get(m.id)?.(m.textes ?? []);
  attente.delete(m.id);
}

async function traduireTextes(textes: string[]): Promise<string[]> {
  const sortie = textes.map((s) => chercher(s) ?? s);
  const manquants = textes.map((s, i) => i).filter((i) => sortie[i] === textes[i] && /[A-Za-zÀ-ÿ]{3}/.test(textes[i]) && resteFrancais(textes[i]));   // une phrase déjà anglaise ne fait pas d'aller-retour
  const ws = wsRef.current;
  if (!manquants.length || !ws || ws.readyState !== WebSocket.OPEN) return sortie;
  const id = `tr${++compteur}`;
  const reponse = await new Promise<string[] | null>((resolve) => {
    attente.set(id, (r) => resolve(r));
    window.setTimeout(() => { if (attente.delete(id)) resolve(null); }, 4000);
    ws.send(JSON.stringify({ type: "traduire", id, textes: manquants.map((i) => textes[i]) }));
  });
  if (reponse && reponse.length === manquants.length) manquants.forEach((i, k) => { sortie[i] = reponse[k] || textes[i]; });
  return sortie;
}

/** Champs texte (title, text, message, lignes…) d'un message du serveur, traduits en anglais avant l'affichage. Autres messages : inchangés, sans attente. */
export async function traduireMessage<T extends object>(msg: T): Promise<T> {
  if (langue !== "en") return msg;
  const m = msg as Record<string, any>;
  const cibles: { o: Record<string, any>; k: string }[] = [];
  const ajouter = (o: any, ...cles: string[]) => { if (o && typeof o === "object") for (const k of cles) if (typeof o[k] === "string" && o[k]) cibles.push({ o, k }); };
  if (m.action === "ctx_card") ajouter(m, "title", "text");
  else if (m.type === "confirm_request") {
    ajouter(m, "message");
    if (Array.isArray(m.details)) m.details.forEach((d: any, i: number) => { if (typeof d === "string") cibles.push({ o: m.details, k: String(i) }); else ajouter(d, "label", "texte", "text", "valeur"); });
  } else if (m.action === "module_ecran") {
    ajouter(m, "titre", "sous_titre", "pied");
    if (Array.isArray(m.lignes)) m.lignes.forEach((l: any) => ajouter(l, "t", "d"));
  }
  if (!cibles.length) return msg;
  const traduits = await traduireTextes(cibles.map((c) => c.o[c.k] as string));
  cibles.forEach((c, i) => { c.o[c.k] = traduits[i]; });
  return msg;
}
