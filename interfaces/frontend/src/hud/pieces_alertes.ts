// Pièces éclatées de la confirmation avant action destructrice et des notifications (voir eclate.ts, maquette validée :
// scratch/outils_test/maquette_confirmation_notifs.html).
//  - Confirmation (style « fin », css/17_fin.css) : tout l'écran bascule en rouge ; l'action demandée avec ce qui sera supprimé, un
//    hexagone à maintenir 1 s (le contour se remplit) avec « Annuler » (la réponse vocale oui / non reste interceptée par le backend),
//    le délai en 20 segments, les confirmations récentes lues dans le journal d'audit.
//    Rien n'est jamais confirmé sans le maintien (ou la voix) : un simple clic ne suffit pas.
//  - Notifications : six zones libres autour du cylindre, une forme et une couleur par priorité, barre de durée, clic = fermer.
import { wsRef } from "../ws_link";
import { fermerPieces, ouvrirPieces, type PieceDef, type Forme } from "./eclate";

const NS = "http://www.w3.org/2000/svg";
const esc = (s: string): string => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const coupe = (s: string, n: number): string => (s.length > n ? `${s.slice(0, n - 1)}…` : s);
/** Texte brut d'un contenu éventuellement en HTML (analyse inerte : rien ne s'exécute). */
const texteBrut = (s: string): string => new DOMParser().parseFromString(String(s ?? ""), "text/html").body.textContent ?? "";

// ───────────────────────────────────────── CONFIRMATION ─────────────────────────────────────────
export interface LigneConfirmation { t: string; d?: string }
type Etat = "attente" | "oui" | "non" | "delai";
interface Confirmation {
  id: string; message: string; lignes: LigneConfirmation[]; duree: number; t0: number;
  etat: Etat; tenu: number; appui: number; rafT: number; fin: number; historique?: HistoriqueConfirmation | null;
}
const RAISON = "confirmation", MAINTIEN_MS = 1000, SEGMENTS = 20, HEX = "M60 6 L108 33 L108 87 L60 114 L12 87 L12 33 Z";
let conf: Confirmation | null = null;
let voile: HTMLElement | null = null;

const dans = <T extends Element>(sel: string): T | null => document.querySelector(`#eclate-couche .ec-piece[data-raison="${RAISON}"] ${sel}`);

function leVoile(): HTMLElement {
  if (voile && voile.isConnected) return voile;
  voile = document.createElement("div");
  voile.id = "alerte-voile";
  document.body.appendChild(voile);
  return voile;
}
function ecran(classe: "" | "hud-alerte" | "hud-alerte-ok"): void {
  document.body.classList.toggle("hud-alerte", classe === "hud-alerte");
  document.body.classList.toggle("hud-alerte-ok", classe === "hud-alerte-ok");
  if (classe) leVoile();
}

export interface JourConfirmation { j: string; oui: number; non: number }
export interface HistoriqueConfirmation { jours: JourConfirmation[]; derniere?: { message: string; confirme: boolean | null; ts: string } | null }

const hhmm = (d: Date): string => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
/** « aujourd'hui », « hier » ou « il y a N jours » à partir d'un horodatage du journal d'audit (AAAA-MM-JJ hh:mm:ss). */
function quand(ts: string): string {
  const d = new Date(ts.replace(" ", "T")), n = new Date();
  if (Number.isNaN(d.getTime())) return "";
  const jours = Math.round((new Date(n.getFullYear(), n.getMonth(), n.getDate()).getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000);
  return jours <= 0 ? `aujourd'hui à ${hhmm(d)}` : jours === 1 ? "hier" : `il y a ${jours} jours`;
}

/** Quatre pièces au style « fin » : l'action demandée, le maintien de l'hexagone, le délai, les confirmations récentes (journal d'audit). */
function piecesConfirmation(c: Confirmation): PieceDef[] {
  const n = Math.min(4, c.lignes.length), tm = hhmm(new Date());
  const defs: PieceDef[] = [
    { id: "action", cote: "g", rang: 0, w: 236, h: 160 + n * 22, classe: "ec-fin", titre: "ACTION DEMANDÉE", rendre: (k) => {
      const lignes = c.lignes.slice(0, 4).map((l, i) => `<div class="fn-lgd al-it" style="margin-bottom:7px;font-size:9px;animation-delay:${0.5 + i * 0.2}s"><i style="background:#ff8a3a;box-shadow:0 0 3px #ff8a3a"></i><span style="color:#eaf9ff;white-space:normal"><b style="font-weight:400">${esc(coupe(l.t, 28))}</b>${l.d ? `<br><span class="fn-petit">${esc(coupe(l.d, 44))}</span>` : ""}</span></div>`).join("");
      k.innerHTML = `<div class="al-titre">${esc(coupe(c.message, 60))}</div><div class="fn-petit" style="margin:3px 0 10px">Demandé à ${tm}</div>${lignes}
        <div class="fn-lgd al-irr" style="font-size:9px"><i style="background:#ff5a3a;box-shadow:0 0 3px #ff5a3a"></i><span style="color:#eaf9ff">Cette action ne pourra pas être annulée.</span></div>
        <div class="fn-cap" style="margin:10px 0 3px">Niveau de risque</div><svg width="100%" height="30" viewBox="0 0 216 30"><defs><linearGradient id="al-rk" x1="0" x2="1"><stop offset="0" stop-color="#4dff9b"/><stop offset=".5" stop-color="#ffd23a"/><stop offset="1" stop-color="#ff5a3a"/></linearGradient></defs>
        <rect x="0" y="8" width="216" height="4" fill="url(#al-rk)" opacity=".8"/><g stroke="rgba(255,255,255,.5)"><path d="M0 6V14M108 6V14M216 6V14"/></g><path d="M188 2 L193 2 L190.5 8Z" fill="#fff" style="filter:drop-shadow(0 0 3px #fff)"/>
        <g fill="#ffd0d8" font-size="6.5"><text x="0" y="24">Faible</text><text x="108" y="24" text-anchor="middle">Moyen</text><text x="216" y="24" text-anchor="end">Élevé : irréversible</text></g></svg>`;
    } },
    { id: "hex", cote: "g", rang: 2, w: 236, h: 150, classe: "ec-fin", titre: "MAINTENIR POUR CONFIRMER", rendre: (k) => {
      k.innerHTML = `<div style="display:flex;gap:10px;align-items:center"><svg class="al-hex" width="100" height="100" viewBox="0 0 120 120" role="button" tabindex="0" aria-label="Maintenir pour confirmer" style="cursor:pointer;touch-action:none;outline:none;flex:none">
        <path d="${HEX}" class="al-hex-fond" pathLength="100"/><path d="${HEX}" class="al-hex-trait" pathLength="100" stroke-dasharray="100" stroke-dashoffset="100"/>
        <text class="al-hex-txt" x="60" y="68" text-anchor="middle" font-size="22" font-weight="300">0%</text></svg>
        <div style="flex:1"><div class="fn-txt">Garde le doigt ou la souris <b>appuyé 1 seconde</b> sur l'hexagone.</div><div style="margin-top:10px"><button type="button" class="fn-btn al-annuler">ANNULER</button></div></div></div>
        <div class="fn-petit" style="margin-top:8px">Tu peux aussi dire « oui » ou « non » à voix haute.</div>`;
      brancherHexagone(k.querySelector(".al-hex") as SVGElement);
      k.querySelector(".al-annuler")?.addEventListener("click", () => repondre(false));
    } },
    { id: "delai", cote: "d", rang: 0, w: 236, h: 150, classe: "ec-fin", titre: "DÉLAI AVANT ANNULATION", rendre: (k) => {
      k.innerHTML = `<div style="display:flex;align-items:baseline;gap:6px"><span class="al-gros al-dl">${Math.round(c.duree)}</span><span class="fn-txt">secondes</span></div>
        <div class="al-seg">${"<i></i>".repeat(SEGMENTS)}</div>
        <svg width="100%" height="26" viewBox="0 0 190 26" style="margin-top:10px"><g class="al-onde"></g></svg>
        <div class="fn-petit al-dl-txt" style="margin-top:6px">Sans réponse, l'action est annulée automatiquement.</div>`;
      const g = k.querySelector(".al-onde") as SVGElement;
      for (let i = 0; i < 48; i++) { const r = document.createElementNS(NS, "rect"); r.setAttribute("x", String(i * 4)); r.setAttribute("width", "2.2"); g.appendChild(r); }
    }, tick: (k, t) => {
      if (!conf) return;
      const reste = Math.max(0, conf.duree - (performance.now() - conf.t0) / 1000), lum = Math.ceil((reste / conf.duree) * SEGMENTS);
      [...k.querySelectorAll<HTMLElement>(".al-seg i")].forEach((s, i) => s.classList.toggle("off", conf!.etat !== "attente" || i >= lum));
      const dl = k.querySelector(".al-dl"), tx = k.querySelector(".al-dl-txt");
      if (dl) dl.textContent = conf.etat === "attente" ? String(Math.ceil(reste)) : conf.etat === "oui" ? "OK" : "—";
      if (tx) tx.textContent = conf.etat === "attente" ? "Sans réponse, l'action est annulée automatiquement." : conf.etat === "oui" ? "Confirmé : l'action est lancée et inscrite au journal d'audit." : conf.etat === "delai" ? "Délai écoulé : rien n'a été supprimé." : "Annulé : rien n'a été supprimé.";
      [...k.querySelectorAll(".al-onde rect")].forEach((r, i) => { const h = conf!.etat === "attente" ? 4 + 6 * Math.abs(Math.sin(t * 3 + i * 0.6)) : 2; r.setAttribute("height", h.toFixed(1)); r.setAttribute("y", (13 - h / 2).toFixed(1)); });
    } },
  ];
  const h = c.historique;
  if (h && h.jours.length) {       // le journal d'audit a répondu : les sept derniers jours
    const maxi = Math.max(3, ...h.jours.map((j) => Math.max(j.oui, j.non))), u = 40 / maxi, pas = 226 / h.jours.length, d = h.derniere;
    defs.push({ id: "recent", cote: "d", rang: 2, w: 236, h: 190, classe: "ec-fin", titre: "CONFIRMATIONS RÉCENTES", rendre: (k) => {
      const barres = h.jours.map((j, i) => `<rect x="${(i * pas + 6).toFixed(1)}" y="${(54 - j.oui * u).toFixed(1)}" width="9" height="${(j.oui * u).toFixed(1)}" fill="#4dff9b" fill-opacity=".8"/><rect x="${(i * pas + 16).toFixed(1)}" y="${(54 - j.non * u).toFixed(1)}" width="9" height="${(j.non * u).toFixed(1)}" fill="#ff8a3a" fill-opacity=".8"/><text x="${(i * pas + 16).toFixed(1)}" y="64" text-anchor="middle">${esc(j.j)}</text>`).join("");
      k.innerHTML = `<div class="fn-cap" style="margin:0 0 3px">${h.jours.length} derniers jours</div><svg width="100%" height="76" viewBox="0 0 226 76"><g fill="none" stroke="rgba(255,200,210,.16)" stroke-width=".6"><path d="M0 14H226M0 34H226"/></g><g fill="none" stroke="rgba(255,200,210,.5)" stroke-width=".7"><path d="M0 54H226"/></g>${barres}<g fill="#ffd0d8" font-size="6.5" text-anchor="middle"><text x="4" y="11" text-anchor="start" font-size="6">${maxi}</text></g></svg>
        <div style="display:flex;gap:12px;margin:6px 0"><div class="fn-lgd" style="margin:0"><i style="background:#4dff9b"></i><span>Confirmées</span></div><div class="fn-lgd" style="margin:0"><i style="background:#ff8a3a"></i><span>Annulées ou sans réponse</span></div></div>
        <div class="fn-petit">${d ? `Dernière : « ${esc(coupe(d.message, 34))} » · ${d.confirme ? "confirmée" : d.confirme === false ? "annulée" : "sans réponse"} ${esc(quand(d.ts))}` : "Aucune confirmation enregistrée."}</div>`;
    } });
  }
  return defs;
}

function majHexagone(): void {
  const trait = dans<SVGElement>(".al-hex-trait"), txt = dans<SVGElement>(".al-hex-txt");
  if (!conf || !trait) return;
  trait.setAttribute("stroke-dashoffset", String(100 - conf.tenu * 100));
  if (txt) txt.textContent = conf.etat === "oui" ? "OK" : conf.etat === "attente" ? `${Math.round(conf.tenu * 100)}%` : "—";
}

function brancherHexagone(hex: SVGElement): void {
  const debut = (): void => {
    if (!conf || conf.etat !== "attente" || conf.appui) return;
    cancelAnimationFrame(conf.rafT);
    conf.appui = 1;
    const base = performance.now() - conf.tenu * MAINTIEN_MS;
    const pas = (): void => {
      if (!conf || conf.etat !== "attente" || !conf.appui) return;
      conf.tenu = Math.min(1, (performance.now() - base) / MAINTIEN_MS);
      majHexagone();
      if (conf.tenu >= 1) { repondre(true); return; }
      conf.rafT = requestAnimationFrame(pas);
    };
    pas();
  };
  const relache = (): void => {
    if (!conf || !conf.appui) return;
    conf.appui = 0;
    cancelAnimationFrame(conf.rafT);
    const vide = (): void => {           // relâché trop tôt : le contour se vide
      if (!conf || conf.etat !== "attente" || conf.appui) return;
      conf.tenu = Math.max(0, conf.tenu - 0.05);
      majHexagone();
      if (conf.tenu > 0) conf.rafT = requestAnimationFrame(vide);
    };
    vide();
  };
  hex.addEventListener("pointerdown", (e) => { e.preventDefault(); debut(); });
  hex.addEventListener("keydown", (e) => { if ((e as KeyboardEvent).key === " " || (e as KeyboardEvent).key === "Enter") { e.preventDefault(); debut(); } });
  hex.addEventListener("keyup", relache);
  window.addEventListener("pointerup", relache);
  window.addEventListener("pointercancel", relache);
}

/** Résultat affiché (vert si confirmé, sinon l'écran redevient normal) puis les pièces s'enfoncent dans le sol. */
function terminer(etat: Exclude<Etat, "attente">): void {
  if (!conf || conf.etat !== "attente") return;
  conf.etat = etat; conf.appui = 0;
  cancelAnimationFrame(conf.rafT); window.clearTimeout(conf.fin);
  if (etat !== "oui") conf.tenu = 0;
  ecran(etat === "oui" ? "hud-alerte-ok" : "");
  majHexagone();
  const cette = conf;
  window.setTimeout(() => {
    fermerPieces(RAISON);
    ecran("");
    if (conf === cette) conf = null;
    vider();
  }, 2200);
}

function repondre(confirme: boolean): void {
  if (!conf || conf.etat !== "attente") return;
  wsRef.current?.send(JSON.stringify({ type: "confirm_response", id: conf.id, confirmed: confirme }));
  terminer(confirme ? "oui" : "non");
}

export function afficherConfirmation(id: string, message: string, lignes?: LigneConfirmation[], duree?: number, historique?: HistoriqueConfirmation | null): void {
  if (conf) { cancelAnimationFrame(conf.rafT); window.clearTimeout(conf.fin); }
  const sec = duree && duree > 0 ? duree : 20;
  conf = { id, message, lignes: lignes ?? [], duree: sec, historique, t0: performance.now(), etat: "attente", tenu: 0, appui: 0, rafT: 0, fin: 0 };
  conf.fin = window.setTimeout(() => terminer("delai"), sec * 1000 + 300);   // le backend a déjà annulé : il ferme aussi la demande
  [...fermetures.values()].forEach((f) => f());       // les notifications en cours cèdent la place
  attente.length = 0;
  ecran("hud-alerte");
  ouvrirPieces(RAISON, piecesConfirmation(conf));
}

/** Confirmation résolue ailleurs (réponse vocale, autre fenêtre, délai écoulé) : `confirme` vaut true / false / null (délai). */
export function confirmationResolue(id: string, confirme?: boolean | null): void {
  if (!conf || conf.id !== id || conf.etat !== "attente") return;
  terminer(confirme === true ? "oui" : confirme === false ? "non" : "delai");
}

export const confirmationOuverte = (): boolean => conf !== null && conf.etat === "attente";

// ───────────────────────────────────────── NOTIFICATIONS ─────────────────────────────────────────
export type Priorite = "critique" | "alarme" | "info" | "astuce";
export interface Notification { id?: string; titre: string; texte: string; priorite: Priorite; duree?: number; icone?: string }
const ZONES: { cote: "g" | "d"; rang: number; forme: Forme }[] = [
  { cote: "d", rang: 0, forme: "cut2" }, { cote: "g", rang: 0, forme: "cut" }, { cote: "d", rang: 1, forme: "rect" },
  { cote: "g", rang: 1, forme: "cut2" }, { cote: "d", rang: 2, forme: "cut" }, { cote: "g", rang: 2, forme: "rect" },
];
const PRIO: Record<Priorite, { classe: string; duree: number; tag: string }> = {
  critique: { classe: "al-crit", duree: 10000, tag: "CRITIQUE" }, alarme: { classe: "al-alarme", duree: 8000, tag: "ALARME" },
  info: { classe: "al-info", duree: 6000, tag: "INFO" }, astuce: { classe: "al-tip", duree: 12000, tag: "ASTUCE" },
};
const occupees: (string | null)[] = ZONES.map(() => null);   // raison de la notification posée dans chaque zone
const fermetures = new Map<string, () => void>();
const attente: Notification[] = [];
let numero = 0;

export const zonesLibres = (): number => (confirmationOuverte() ? 0 : occupees.filter((z) => !z).length);

function vider(): void {
  while (attente.length && zonesLibres() > 0) poser(attente.shift()!);
}

function poser(n: Notification): void {
  const z = occupees.findIndex((s) => !s);
  if (z < 0) return;
  const zone = ZONES[z], p = PRIO[n.priorite], raison = `notif-${++numero}`, duree = n.duree && n.duree > 0 ? n.duree : p.duree;
  if (n.id) fermetures.get(`id:${n.id}`)?.();
  occupees[z] = raison;
  const texte = coupe(texteBrut(n.texte), 140);
  const lignes = Math.max(1, Math.ceil(texte.length / 30));
  let ferme = false;
  const fermer = (): void => {
    if (ferme) return;
    ferme = true; fermetures.delete(raison); if (n.id) fermetures.delete(`id:${n.id}`);
    window.clearTimeout(minuteur);
    fermerPieces(raison);
    window.setTimeout(() => { if (occupees[z] === raison) { occupees[z] = null; vider(); } }, 700);
  };
  const minuteur = window.setTimeout(fermer, duree);
  fermetures.set(raison, fermer); if (n.id) fermetures.set(`id:${n.id}`, fermer);
  let t0 = 0;
  const def: PieceDef = {
    id: "n", cote: zone.cote, rang: zone.rang, w: 232, h: Math.min(150, 66 + lignes * 17), forme: zone.forme, classe: `ec-n ${p.classe}`,
    titre: `${n.icone ? `${n.icone} ` : ""}${p.tag}${texteBrut(n.titre).toUpperCase() === p.tag ? "" : ` · ${coupe(texteBrut(n.titre).toUpperCase(), 26)}`}`,
    rendre: (k) => {
      k.innerHTML = `<div class="ec-val al-texte"></div><i class="al-duree"></i>`;
      const txt = k.querySelector(".al-texte") as HTMLElement;
      txt.textContent = n.priorite === "astuce" ? "" : texte;
      (k.closest(".ec-piece") as HTMLElement | null)?.addEventListener("click", fermer);
      const barre = k.querySelector(".al-duree") as HTMLElement;
      requestAnimationFrame(() => requestAnimationFrame(() => { barre.style.transitionDuration = `${duree}ms`; barre.style.width = "0%"; }));
    },
    tick: n.priorite === "astuce" ? (k, t) => {                // l'astuce se tape, lettre après lettre
      if (!t0) t0 = t;
      const i = Math.min(texte.length, Math.floor((t - t0) * 38)), txt = k.querySelector(".al-texte");
      const v = texte.slice(0, i) + (i < texte.length ? "▌" : "");
      if (txt && txt.textContent !== v) txt.textContent = v;
    } : undefined,
  };
  ouvrirPieces(raison, [def], undefined, true);
}

export function afficherNotification(n: Notification): void {
  if (attente.length >= 12) attente.shift();
  if (zonesLibres() > 0) poser(n); else attente.push(n);
}
