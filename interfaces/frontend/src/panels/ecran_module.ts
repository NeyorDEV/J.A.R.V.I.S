// ── Écran de contenu d'une catégorie du cylindre (agenda, mail, maison, journal, télé) ──
// Le backend envoie `module_ecran` (voir core/module_ecrans.py) : le cylindre cherche la catégorie, s'ouvre en écran, et la fiche
// y apparaît. Se referme par la croix, ou toute seule après un délai.
import { fermerEcran, ouvrirEcran } from "../hud/cylindre_ouvert";
import { esc } from "./pm_utils";

interface LigneEcran { t: string; d?: string | null; v?: string | null; etat?: "on" | "off" | "alerte" | null }
interface DonneesEcran { categorie?: string; sous?: string | null; titre?: string; sous_titre?: string; lignes?: LigneEcran[]; pied?: string | null }

const RAISON = "ecran-module";
const DELAI_FERMETURE_MS = 30_000;
let fermeture: number | null = null;
let ouvert = false;

function element(): HTMLElement {
  let el = document.getElementById("module-ecran");
  if (el) return el;
  el = document.createElement("div");
  el.id = "module-ecran";
  el.className = "hud-widget module-ecran";
  el.style.display = "none";
  document.body.appendChild(el);
  return el;
}

function fermer(): void {
  const el = element();
  if (fermeture !== null) { clearTimeout(fermeture); fermeture = null; }
  if (!ouvert) return;
  ouvert = false;
  fermerEcran(RAISON, el, true);
  el.style.display = "none";
}

function remplir(el: HTMLElement, d: DonneesEcran): void {
  const lignes = (d.lignes ?? []).map((l) => `
    <div class="me-ligne${l.etat ? ` me-${l.etat}` : ""}">
      <span class="me-pastille"></span>
      <span class="me-texte"><b>${esc(l.t)}</b>${l.d ? `<i>${esc(l.d)}</i>` : ""}</span>
      ${l.v ? `<span class="me-valeur">${esc(l.v)}</span>` : ""}
    </div>`).join("");
  el.innerHTML = `
    <div class="me-entete"><span>${esc(d.titre ?? "")}${d.sous_titre ? ` · ${esc(d.sous_titre)}` : ""}</span><button class="widget-close-btn" title="Fermer">✕</button></div>
    <div class="me-corps">${lignes}</div>
    ${d.pied ? `<div class="me-pied">${esc(d.pied)}</div>` : ""}`;
  el.querySelector(".widget-close-btn")?.addEventListener("click", fermer);
}

export function afficherEcranModule(d: DonneesEcran): void {
  const el = element();
  remplir(el, d);
  if (fermeture !== null) clearTimeout(fermeture);
  fermeture = window.setTimeout(fermer, DELAI_FERMETURE_MS);
  if (ouvert) return;   // déjà à l'écran : le contenu est simplement mis à jour
  ouvert = true;
  el.style.display = "flex";
  ouvrirEcran(RAISON, el, "", true, d.categorie ? [d.categorie, d.sous ?? null] : undefined);
}
