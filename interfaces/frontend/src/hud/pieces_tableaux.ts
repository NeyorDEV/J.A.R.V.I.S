// Pièces éclatées des 4 tableaux de gestion (style « fin et riche », css/17_fin.css + css/18_tableaux_fin.css) : système, mises à jour des
// logiciels, antivirus, désinstallateur. Les anciens panneaux restent dans le DOM : ils reçoivent les messages du serveur, portent l'état
// affiché / masqué et exposent leur état (lireEtat…) et leurs actions. Rien n'est inventé : une donnée absente est écrite comme telle.
import { locale } from "../i18n/i18n";
import { rafraichirPieces, type PieceDef } from "./eclate";
import { AX, AX2, COUL, bornes, courbe, donut, ticks } from "./fin_graph";
import { esc, formatDate, formatTaille } from "../panels/pm_utils";
import { lireEtatSysteme } from "../panels/system_panel";
import { actualiserWinget, lancerMajWinget, lancerMajWingetTout, lireEtatWinget } from "../panels/winget_panel";
import { annulerOuRelancerAnalyse, avDebut, avEnCours, avEtat, avMenaces, avProtectionTempsReel, basculerProtectionTempsReel } from "../panels/antivirus_panel";
import { desinstallerProgramme, garderTraces, lireEtatDesinstall, nettoyerTraces, type Programme } from "../panels/uninstaller_panel";

const cliquer = (id: string): void => { (document.getElementById(id) as HTMLElement | null)?.click(); };
const bouton = (act: string, texte: string, extra = ""): string => `<span class="fn-btn ${extra}" data-act="${act}">${texte}</span>`;
const vide = (texte: string): string => `<div class="fn-txt tf-vide">${texte}</div>`;
const nombre = (n: number): string => Math.round(n).toLocaleString(locale());
const virgule = (n: number, d = 1): string => n.toFixed(d).replace(".", ",");
const mmss = (s: number): string => { const n = Math.max(0, Math.floor(s)); return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`; };
const cap = (t: string): string => `<div class="fn-cap">${t}</div>`;
const lgd = (c: string, nom: string, val: string): string => `<div class="fn-lgd"><i style="background:${c};box-shadow:0 0 3px ${c}"></i><span>${esc(nom)}</span><em>${val}</em></div>`;
const ecoute = (c: HTMLElement, f: (act: HTMLElement) => void): void => {
  if (c.dataset.ecoute) return;
  c.dataset.ecoute = "1";
  c.addEventListener("click", (e) => { const b = (e.target as HTMLElement).closest("[data-act]") as HTMLElement | null; if (b && !b.classList.contains("off")) f(b); });
};
const couleurNiveau = (v: number): string => (v > 90 ? COUL.rouge : v > 75 ? COUL.jaune : COUL.cyan);
/** Une pièce du style fin : forme rectangulaire à coins coupés (css/17_fin.css), titre en majuscules. */
const piece = (id: string, cote: "g" | "d", rang: number, w: number, h: number, titre: string, rendre: PieceDef["rendre"], tick?: PieceDef["tick"], croix?: () => void): PieceDef =>
  ({ id, cote, rang, w, h, forme: "rect", classe: "ec-fin", titre, croix, rendre, tick });
/** Rendu d'une pièce animée : la structure n'est construite qu'une fois (les valeurs vivantes sont posées par `tick`). */
const unefois = (c: HTMLElement, construire: () => string): boolean => { if (c.dataset.pret) return false; c.dataset.pret = "1"; c.innerHTML = construire(); return true; };

/** Frise d'étapes : trois ronds sur un trait ; `etat` 0 = rien de fait, 1..3 = étape atteinte ; `echec` colore en rouge. */
function frise(libelles: [string, string, string], etat: number, pct: number, echec = false): string {
  const coul = echec ? COUL.rouge : etat >= 3 ? COUL.vert : COUL.cyan, xs = [10, 113, 216];
  const ronds = xs.map((x, k) => `<circle cx="${x}" cy="8" r="3.5" fill="${etat > k ? (k === 2 && !echec ? COUL.vert : coul) : "#04124c"}" stroke="${etat >= k && etat > 0 ? "#bff3ff" : "rgba(127,220,255,.4)"}" stroke-width=".8"/>
    <text x="${x}" y="20" text-anchor="${k === 0 ? "start" : k === 2 ? "end" : "middle"}" font-size="6" fill="#9fdcff">${libelles[k]}</text>`).join("");
  return `<svg width="216" height="22" viewBox="0 0 226 22"><path d="M10 8H216" stroke="rgba(127,220,255,.2)"/><path d="M10 8H${10 + 206 * bornes(pct, 0, 1)}" stroke="${coul}" style="filter:drop-shadow(0 0 2px ${coul})"/>${ronds}</svg>`;
}

/** Barre horizontale graduée (0 %, 50 %, 100 %) : valeur `v` de 0 à 100, `w` pixels de large. */
function barre(w: number, v: number | null, coul: string): string {
  const g = [0, 0.25, 0.5, 0.75, 1].map((f) => `<path d="M${(f * (w - 0.5)).toFixed(1)} 0V${f % 0.5 ? 3 : 6}"/>`).join("");
  return `<svg width="${w}" height="8" viewBox="0 0 ${w} 8"><rect x="0" y="3" width="${w}" height="2" fill="rgba(127,220,255,.14)"/>${v === null ? "" : `<rect x="0" y="3" width="${(bornes(v, 0, 100) / 100) * w}" height="2" fill="${coul}" style="filter:drop-shadow(0 0 2px ${coul})"/>`}<g stroke="rgba(127,220,255,.5)" stroke-width=".6">${g}</g></svg>`;
}

// ───────────────────────────────────────── SYSTÈME ─────────────────────────────────────────
const sys = { hist: [] as number[], tDonnee: 0, tRecu: 0, cpu: 0, barres: [0, 0, 0] };
const etatSys = () => lireEtatSysteme().etat;
const ressources = (): Record<string, any> | null => etatSys()?.ressources ?? null;
const ATTENTE = vide("En attente de l'état du système…");

/** Un échantillon de charge du processeur par état reçu (toutes les 2 s tant que le panneau est ouvert). */
function noterCharge(): void {
  const e = etatSys();
  if (!e || e.t === sys.tDonnee) return;
  sys.tDonnee = e.t; sys.tRecu = performance.now() / 1000;
  if (typeof e.ressources?.cpu === "number") { sys.hist.push(e.ressources.cpu); if (sys.hist.length > 30) sys.hist.shift(); }
}

const BARRES: [string, string][] = [["Mémoire (RAM)", "ram"], ["Carte graphique", "gpu"], ["Disque système", "disque"]];
function rendreProcesseur(c: HTMLElement): void {
  noterCharge();
  if (!etatSys()) { c.innerHTML = ATTENTE; delete c.dataset.pret; return; }
  unefois(c, () => `<div style="display:flex;gap:10px;align-items:center"><svg width="86" height="86" viewBox="0 0 86 86">${ticks(43, 43, 36, 48)}<circle cx="43" cy="43" r="32" fill="none" stroke="rgba(127,220,255,.14)" stroke-width="4"/>
      <circle class="cr" cx="43" cy="43" r="32" fill="none" stroke="#2fd8ff" stroke-width="4" stroke-dasharray="0 201" transform="rotate(-90 43 43)" style="filter:drop-shadow(0 0 3px #2fd8ff)"/>
      <text class="cv" x="43" y="48" text-anchor="middle" font-size="17" font-weight="300" fill="#fff">—</text><text x="43" y="60" text-anchor="middle" font-size="6" fill="#7fb8dc">processeur</text></svg>
    <div style="flex:1">${BARRES.map(([n, k], i) => `<div style="margin-bottom:${i < 2 ? 7 : 0}px"><div style="display:flex;justify-content:space-between" class="fn-cap"><span>${n}</span><b class="bv" data-k="${k}">—</b></div>
      <svg width="116" height="8" viewBox="0 0 116 8"><rect x="0" y="3" width="116" height="2" fill="rgba(127,220,255,.14)"/><rect class="bf" data-k="${k}" x="0" y="3" width="0" height="2" fill="#2fd8ff"/><g stroke="rgba(127,220,255,.5)" stroke-width=".6">${[0, 0.5, 1].map((f) => `<path d="M${f * 115.5} 0V6"/>`).join("")}</g></svg></div>`).join("")}</div></div>
    ${cap("Charge du processeur sur les 60 dernières secondes")}
    <svg width="216" height="66" viewBox="0 0 216 66" style="display:block;background:rgba(2,12,50,.5);border:1px solid rgba(127,220,255,.18)"><g ${AX}><path d="M0 16H216M0 33H216M0 50H216M54 0V66M108 0V66M162 0V66"/></g>
      <path class="za" fill="rgba(47,216,255,.1)"/><path class="zl" fill="none" stroke="#2fd8ff" style="filter:drop-shadow(0 0 2px #2fd8ff)"/><g fill="#9fdcff" font-size="6"><text x="3" y="9">100 %</text><text x="3" y="38">50 %</text><text x="3" y="63">−60 s</text><text x="213" y="63" text-anchor="end">maintenant</text></g></svg>
    <div class="fn-petit" style="margin-top:4px">Détail par cœur : non fourni par JARVIS.</div>`);
}
function tickProcesseur(c: HTMLElement, t: number): void {
  const r = ressources(); if (!r) return;
  const cpu = typeof r.cpu === "number" ? bornes(r.cpu, 0, 100) : 0;
  sys.cpu += (cpu - sys.cpu) * 0.1;
  const cr = c.querySelector(".cr"), cv = c.querySelector(".cv"), co = couleurNiveau(sys.cpu);
  cr?.setAttribute("stroke-dasharray", `${(201 * sys.cpu) / 100} 201`); cr?.setAttribute("stroke", co);
  if (cv) cv.textContent = typeof r.cpu === "number" ? `${Math.round(sys.cpu)} %` : "—";
  BARRES.forEach(([, k], i) => {
    const v = typeof r[k] === "number" ? bornes(r[k], 0, 100) : null;
    sys.barres[i] += ((v ?? 0) - sys.barres[i]) * 0.1;
    const f = c.querySelector(`.bf[data-k="${k}"]`), tv = c.querySelector(`.bv[data-k="${k}"]`);
    f?.setAttribute("width", String((sys.barres[i] / 100) * 116)); f?.setAttribute("fill", couleurNiveau(sys.barres[i]));
    const txt = v === null ? "non fourni" : `${Math.round(v)} %`;
    if (tv && tv.textContent !== txt) tv.textContent = txt;
  });
  const n = sys.hist.length, l = c.querySelector(".zl"), a = c.querySelector(".za");
  if (!l || !a || !n) return;
  const pas = 216 / 29, dec = bornes((t - sys.tRecu) / 2, 0, 1);
  const pts = sys.hist.map((h, i) => `${(216 - (n - 1 - i) * pas - dec * pas).toFixed(1)},${(66 - (bornes(h, 0, 100) / 100) * 62).toFixed(1)}`);
  const y = (66 - (bornes(sys.hist[n - 1], 0, 100) / 100) * 62).toFixed(1), d = `M${pts.join(" L")} L216,${y}`;
  l.setAttribute("d", d); a.setAttribute("d", `${d} L216,66 L0,66Z`);
}

function rendreGourmands(c: HTMLElement): void {
  if (!etatSys()) { c.innerHTML = ATTENTE; return; }
  const p: { nom: string; mo: number }[] | undefined = ressources()?.processus;
  const duree = `<div class="fn-sep"><div class="fn-cap">En marche depuis</div><div class="fn-big dm" style="font-size:16px">…</div></div>`;
  if (!p?.length) { c.innerHTML = vide("Liste des programmes indisponible.") + duree; return; }
  const tot = p.reduce((s, x) => s + x.mo, 0) || 1, coul = [COUL.cyan, COUL.vert, COUL.jaune];
  const go = (mo: number): string => (mo >= 1024 ? `${virgule(mo / 1024)} Go` : `${mo} Mo`);
  c.innerHTML = `${cap("Mémoire utilisée par les trois programmes les plus lourds")}<div style="display:flex;gap:10px;align-items:center"><svg width="92" height="92" viewBox="0 0 92 92">${donut(46, 46, 34, p.map((x, i) => ({ f: x.mo / tot, c: coul[i] })), 7)}
      <text x="46" y="45" text-anchor="middle" font-size="14" font-weight="300" fill="#fff">${tot >= 1024 ? virgule(tot / 1024) : tot}</text><text x="46" y="56" text-anchor="middle" font-size="6.5" fill="#7fb8dc">${tot >= 1024 ? "Go" : "Mo"} en tout</text></svg>
    <div style="flex:1">${p.map((x, i) => lgd(coul[i], x.nom.replace(/\.exe$/i, ""), go(x.mo))).join("")}</div></div>${duree}`;
}
function tickGourmands(c: HTMLElement, t: number): void {
  const dm = c.querySelector(".dm"), u = etatSys()?.ressources?.uptime_s;
  if (!dm) return;
  if (typeof u !== "number") { dm.textContent = "non fournie"; return; }
  const s = Math.floor(u + (sys.tRecu ? t - sys.tRecu : 0)), j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  dm.textContent = `${j ? `${j} j ` : ""}${h} h ${String(m).padStart(2, "0")} min`;
}

function rendreTemperatures(c: HTMLElement): void {
  const r = ressources();
  if (!r) { c.innerHTML = ATTENTE; return; }
  const tp = r.temperature;
  const haut = typeof tp === "number"
    ? `<div class="fn-big" style="color:${tp > 80 ? COUL.rouge : "#2fd8ff"}">${tp} °C</div><div class="fn-cap" style="margin-bottom:5px">Température la plus haute relevée · limite : 80 °C</div>
       <svg width="226" height="30" viewBox="0 0 226 30"><defs><linearGradient id="tfg" x1="0" x2="1"><stop offset="0" stop-color="${COUL.cyan}"/><stop offset=".6" stop-color="${COUL.jaune}"/><stop offset="1" stop-color="${COUL.rouge}"/></linearGradient></defs>
       <rect x="0" y="6" width="226" height="5" fill="url(#tfg)" fill-opacity=".8"/><path d="M${((tp - 30) / 70) * 226} 2V15" stroke="#fff" stroke-width="2"/><path d="M${(50 / 70) * 226} 4V13" stroke="#fff" stroke-opacity=".6" stroke-dasharray="2 2"/>
       <g fill="#9fdcff" font-size="6"><text x="0" y="24">30 °C</text><text x="${(50 / 70) * 226}" y="24" text-anchor="middle">80 °C</text><text x="226" y="24" text-anchor="end">100 °C</text></g></svg>`
    : vide("Les températures du processeur, de la carte graphique et du disque ne sont pas fournies par Windows à JARVIS sur cette machine.");
  const vram = typeof r.vram === "number" ? bornes(r.vram, 0, 100) : null, gpu = typeof r.gpu === "number" ? bornes(r.gpu, 0, 100) : null;
  c.innerHTML = `${haut}<div class="fn-sep">${cap("Carte graphique")}
    <div style="display:flex;justify-content:space-between" class="fn-txt"><span>Utilisation</span><span><b>${gpu === null ? "non fournie" : `${Math.round(gpu)} %`}</b></span></div>${barre(226, gpu, couleurNiveau(gpu ?? 0))}
    <div style="display:flex;justify-content:space-between;margin-top:7px" class="fn-txt"><span>Mémoire vidéo</span><span><b>${vram === null ? "non fournie" : `${Math.round(vram)} %`}</b></span></div>${barre(226, vram, couleurNiveau(vram ?? 0))}</div>`;
}

const VOYANT: Record<string, string> = { actif: COUL.vert, pret: COUL.vert, libre: COUL.vert, pause: COUL.jaune, absent: COUL.gris };
const LIBELLE: Record<string, string> = { actif: "actif", pret: "prêt", libre: "libre", pause: "en pause", absent: "clé manquante" };
function rendreMoteurs(c: HTMLElement): void {
  const e = etatSys();
  if (!e) { c.innerHTML = ATTENTE; return; }
  const m: any[] = e.moteurs ?? [], tests = lireEtatSysteme().tests, ok = m.filter((x) => x.etat === "actif" || x.etat === "pret" || x.etat === "libre").length;
  c.innerHTML = `<div style="display:flex;gap:10px;align-items:center"><svg width="66" height="66" viewBox="0 0 66 66">${donut(33, 33, 25, [{ f: m.length ? ok / m.length : 0, c: COUL.vert }], 5)}<text x="33" y="37" text-anchor="middle" font-size="13" font-weight="300" fill="#fff">${ok}/${m.length}</text></svg>
    <div class="fn-txt"><b>${ok} moteur${ok > 1 ? "s" : ""} disponible${ok > 1 ? "s" : ""}</b><br><span class="fn-petit">dans l'ordre d'essai</span></div></div>
    <div style="margin-top:6px">${m.slice(0, 6).map((x) => { const t = tests[x.id], coul = t ? (t.ok ? COUL.vert : COUL.rouge) : VOYANT[x.etat] ?? COUL.gris;
      return `<div class="fn-lgd"><i style="background:${coul};box-shadow:0 0 3px ${coul}"></i><span style="color:#eaf9ff">${esc(x.nom)}</span><em>${t ? (t.ok ? `test ok · ${String(t.duree).replace(".", ",")} s` : "échec du test") : LIBELLE[x.etat] ?? esc(x.etat)}</em></div>`; }).join("")}${m.length > 6 ? `<div class="fn-petit">+ ${m.length - 6} autre(s)</div>` : ""}</div>
    <div style="margin-top:8px">${bouton("tout", "TOUT TESTER")}</div>`;
  ecoute(c, () => cliquer("system-test-all"));
}

export const piecesSysteme = (): PieceDef[] => [
  piece("processeur", "g", 0, 238, 238, "PROCESSEUR ET MÉMOIRE", rendreProcesseur, tickProcesseur, () => cliquer("system-fermer")),
  piece("gourmands", "g", 1, 238, 190, "PROGRAMMES GOURMANDS", rendreGourmands, tickGourmands),
  piece("temperatures", "d", 0, 248, 224, "TEMPÉRATURES", rendreTemperatures),
  piece("moteurs", "d", 1, 248, 228, "MOTEURS D'IA", rendreMoteurs),
];

// ───────────────────────────────────────── LOGICIELS (winget) ─────────────────────────────────────────
const maj = { sel: new Set<string>(), connus: new Set<string>() };
/** Les mises à jour nouvellement listées sont cochées d'office (comme dans l'ancien panneau). */
function syncSelection(): void {
  const { liste } = lireEtatWinget();
  for (const i of liste) if (!maj.connus.has(i.id)) { maj.connus.add(i.id); maj.sel.add(i.id); }
  for (const id of [...maj.sel]) if (!liste.some((i) => i.id === id)) maj.sel.delete(id);
}

function rendreListeMaj(c: HTMLElement): void {
  syncSelection();
  const { liste, etats, recherche } = lireEtatWinget(), defil = (c.querySelector(".fn-liste") as HTMLElement | null)?.scrollTop ?? 0;
  if (recherche && !liste.length) { c.innerHTML = vide("Recherche des mises à jour en cours…"); return; }
  if (!liste.length) { c.innerHTML = vide("Tous vos logiciels sont à jour.") + `<div class="fn-petit">Aucune mise à jour trouvée par winget.</div>`; return; }
  c.innerHTML = `${cap("Cliquez pour cocher ou décocher un logiciel")}<div class="fn-liste" style="max-height:176px">${liste.map((i) => {
    const e = etats.get(i.id);
    return `<div class="fn-li" data-act="coche" data-id="${esc(i.id)}" style="display:block;padding:5px 3px"><div style="display:flex;align-items:center;gap:6px"><i class="fn-cb ${maj.sel.has(i.id) ? "on" : ""}"></i><span style="flex:1;color:#fff;font-size:9.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.name)}</span></div>
      <div class="fn-petit" style="margin:2px 0 0 14px">${e ? (e.etat === "ok" ? "mis à jour" : e.etat === "echec" ? "échec de la mise à jour" : e.etat === "cours" ? "installation en cours" : "en attente") : `${esc(i.version)} → <span style="color:${COUL.vert}">${esc(i.available)}</span>`}</div></div>`;
  }).join("")}</div>`;
  (c.querySelector(".fn-liste") as HTMLElement).scrollTop = defil;
  ecoute(c, (b) => { if (b.dataset.act === "coche" && b.dataset.id) { if (maj.sel.has(b.dataset.id)) maj.sel.delete(b.dataset.id); else maj.sel.add(b.dataset.id); rafraichirPieces("winget"); } });
}

function rendreAvancement(c: HTMLElement): void {
  syncSelection();
  const { liste, etats, occupe } = lireEtatWinget(), suivis = liste.filter((i) => etats.has(i.id));
  const faits = suivis.filter((i) => etats.get(i.id)!.etat === "ok").length, f = suivis.length ? faits / suivis.length : 0, n = maj.sel.size;
  c.innerHTML = `<div style="display:flex;gap:10px;align-items:center"><svg width="74" height="74" viewBox="0 0 74 74">${ticks(37, 37, 31, 40)}${donut(37, 37, 26, [{ f: Math.max(0.0001, f), c: COUL.vert }], 4)}<text x="37" y="40" text-anchor="middle" font-size="14" font-weight="300" fill="#fff">${Math.round(f * 100)}%</text></svg>
    <div style="flex:1"><div class="fn-big" style="font-size:20px">${n}</div><div class="fn-txt">logiciel${n > 1 ? "s" : ""} coché${n > 1 ? "s" : ""} sur ${liste.length}</div></div></div>
    <div class="fn-petit" style="margin-top:8px">Vitesse de téléchargement : non communiquée par winget.</div>
    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">${bouton("lancer", occupe ? "INSTALLATION…" : "METTRE À JOUR", occupe || !n ? "off" : "")}${bouton("tout", "TOUT", occupe || !liste.length ? "off" : "")}${bouton("actu", "ACTUALISER", occupe ? "off" : "")}</div>`;
  ecoute(c, (b) => {
    const { occupe: o, liste: l } = lireEtatWinget();
    if (o) return;
    if (b.dataset.act === "lancer") lancerMajWinget(l.map((i) => i.id).filter((id) => maj.sel.has(id)));
    else if (b.dataset.act === "tout") lancerMajWingetTout();
    else if (b.dataset.act === "actu") actualiserWinget();
  });
}

function rendreFile(c: HTMLElement): void {
  const { liste, etats } = lireEtatWinget(), file = liste.filter((i) => etats.has(i.id));
  if (!file.length) { c.innerHTML = vide("Aucune installation en cours.<br>Cochez des logiciels puis « Mettre à jour »."); return; }
  c.innerHTML = cap("Chaque logiciel passe par trois étapes") + file.slice(0, 5).map((i) => {
    const e = etats.get(i.id)!, niv = e.etat === "ok" ? 3 : e.etat === "cours" ? 2 : e.etat === "echec" ? 3 : 1, pct = e.etat === "ok" || e.etat === "echec" ? 1 : e.etat === "cours" ? 0.5 + (e.pct ?? 0) / 200 : 0;
    return `<div style="margin-bottom:9px"><div style="display:flex;justify-content:space-between" class="fn-txt"><b>${esc(i.name.slice(0, 26))}</b><span class="fn-petit">${e.etat === "ok" ? "terminé" : e.etat === "echec" ? "échec" : e.etat === "cours" ? (e.pct === undefined ? "en cours" : `${e.pct} %`) : "en attente"}</span></div>${frise(["Attente", "Installation", e.etat === "echec" ? "Échec" : "Terminé"], niv, pct, e.etat === "echec")}</div>`;
  }).join("") + (file.length > 5 ? `<div class="fn-petit">+ ${file.length - 5} autre(s)</div>` : "");
}

function rendreBilanMaj(c: HTMLElement): void {
  const { liste, etats, recherche } = lireEtatWinget();
  if (recherche && !liste.length) { c.innerHTML = vide("Recherche en cours…"); return; }
  const ok = [...etats.values()].filter((e) => e.etat === "ok").length, ko = [...etats.values()].filter((e) => e.etat === "echec").length, reste = Math.max(0, liste.length - ok - ko), tot = Math.max(1, liste.length);
  c.innerHTML = `${cap("Où en sont les mises à jour")}<div style="display:flex;gap:10px;align-items:center"><svg width="92" height="92" viewBox="0 0 92 92">${donut(46, 46, 34, [{ f: reste / tot, c: COUL.cyan }, { f: ok / tot, c: COUL.vert }, { f: ko / tot, c: COUL.rouge }], 7)}
      <text x="46" y="48" text-anchor="middle" font-size="18" font-weight="300" fill="#fff">${reste}</text><text x="46" y="59" text-anchor="middle" font-size="6.5" fill="#7fb8dc">à faire</text></svg>
    <div style="flex:1">${lgd(COUL.cyan, "Restantes", String(reste))}${lgd(COUL.vert, "Réussies", String(ok))}${lgd(COUL.rouge, "Échecs", String(ko))}</div></div>
    <div class="fn-sep fn-petit">Historique des installations et liste des logiciels déjà à jour : non fournis par winget.</div>`;
}

export const piecesLogiciels = (): PieceDef[] => {
  maj.sel.clear(); maj.connus.clear();
  return [
    piece("liste", "g", 0, 238, 238, "MISES À JOUR DISPONIBLES", rendreListeMaj, undefined, () => cliquer("winget-panel-close-btn")),
    piece("avancement", "g", 1, 238, 196, "AVANCEMENT", rendreAvancement),
    piece("file", "d", 0, 248, 224, "FILE D'INSTALLATION", rendreFile),
    piece("bilan", "d", 1, 248, 190, "BILAN DES MISES À JOUR", rendreBilanMaj),
  ];
};

// ───────────────────────────────────────── ANTIVIRUS ─────────────────────────────────────────
const av = { duree: 0, derFich: 0, derT: 0, taux: Array(50).fill(0) as number[], niveau: 0 };
const CHEMIN = "M80 12 L142 34 V92 C142 132 114 160 80 176 C46 160 18 132 18 92 V34 Z";
const couleurAv = (): string => (avEtat.menaces > 0 ? COUL.jaune : avEtat.classe === "etat-sain" ? COUL.vert : COUL.cyan);

function rendreBouclier(c: HTMLElement): void {
  const sus = avEtat.menaces, ok = avEtat.classe === "etat-sain";
  unefois(c, () => `<div style="display:flex;gap:9px;align-items:center"><svg width="104" height="124" viewBox="0 0 160 190"><defs><clipPath id="ecav"><path d="${CHEMIN}"/></clipPath></defs>
    <circle class="ro" cx="80" cy="96" r="84" fill="none" stroke="rgba(127,220,255,.35)" stroke-dasharray="3 7" style="transform-origin:80px 96px"/>
    <path d="${CHEMIN}" fill="rgba(0,229,255,.05)"/><g clip-path="url(#ecav)"><path class="lq" fill="#2fd8ff" fill-opacity=".38"/><path class="lq2" fill="#2fd8ff" fill-opacity=".22"/></g>
    <path class="bd" d="${CHEMIN}" fill="none" stroke="#2fd8ff" stroke-width="2" style="filter:drop-shadow(0 0 5px #2fd8ff)"/><text class="bp" x="80" y="108" text-anchor="middle" font-size="36" font-weight="300" fill="#e8fbff">0%</text></svg>
    <div style="flex:1;min-width:0"><div class="fn-txt"><b class="bt">—</b></div><div class="fn-big nf" style="font-size:16px;margin:6px 0 1px">0</div><div class="fn-petit">fichiers analysés</div><div class="fn-petit ms" style="margin:8px 0"></div><div class="bb"></div></div></div>
    ${cap("Le bouclier se remplit au fil de l'analyse")}`);
  const ms = c.querySelector(".ms") as HTMLElement | null, bb = c.querySelector(".bb") as HTMLElement | null;
  if (ms) { ms.textContent = sus ? `${sus} fichier${sus > 1 ? "s" : ""} suspect${sus > 1 ? "s" : ""}` : ok ? "aucune menace" : avEnCours() ? "aucune menace pour l'instant" : "pas encore d'analyse"; ms.style.color = sus ? COUL.jaune : ""; }
  if (bb) bb.innerHTML = bouton("scan", avEnCours() ? "ANNULER L'ANALYSE" : "LANCER L'ANALYSE", avEnCours() ? "r" : "");
  ecoute(c, (b) => { if (b.dataset.act === "scan") annulerOuRelancerAnalyse(); });
}
function tickBouclier(c: HTMLElement, t: number): void {
  av.niveau += (avEtat.pct - av.niveau) * 0.12;
  const niv = 176 - (av.niveau / 100) * 164, coul = couleurAv();
  const vague = (ph: number, a: number): string => { let d = `M0,190 L0,${niv.toFixed(1)}`; for (let x = 0; x <= 160; x += 8) d += ` L${x},${(niv + a * Math.sin(x / 12 + t * 3 + ph)).toFixed(1)}`; return `${d} L160,190Z`; };
  c.querySelector(".lq")?.setAttribute("d", vague(0, 3)); c.querySelector(".lq2")?.setAttribute("d", vague(2, 2.2));
  c.querySelectorAll(".lq,.lq2").forEach((q) => q.setAttribute("fill", coul)); c.querySelector(".bd")?.setAttribute("stroke", coul);
  (c.querySelector(".ro") as SVGElement | null)?.style.setProperty("transform", `rotate(${t * 20}deg)`);
  const bp = c.querySelector(".bp"), bt = c.querySelector(".bt"), nf = c.querySelector(".nf");
  const txt = `${Math.round(av.niveau)}%`; if (bp && bp.textContent !== txt) bp.textContent = txt;
  const etat = avEtat.texte || (avEnCours() ? "Analyse en cours" : "Prêt à analyser"); if (bt && bt.textContent !== etat) bt.textContent = etat;
  const n = nombre(avEtat.fichiers); if (nf && nf.textContent !== n) nf.textContent = n;
}

function derniereCible(): string {
  for (let i = avEtat.lignes.length - 1; i >= 0; i--) { const l = avEtat.lignes[i].t; if (l.startsWith("[FICHIER]")) return l.replace(/^\[FICHIER\]\s*/, ""); }
  return "";
}
function rendreDirect(c: HTMLElement): void {
  const cible = derniereCible(), ligne = avEtat.lignes.slice(-3);
  unefois(c, () => `${cap("Fichiers examinés par seconde")}<svg width="216" height="62" viewBox="0 0 216 62" style="display:block;background:rgba(2,12,50,.5);border:1px solid rgba(127,220,255,.18)"><g ${AX}><path d="M0 16H216M0 31H216M0 46H216"/></g>
    <path class="za" fill="rgba(47,216,255,.1)"/><path class="zl" fill="none" stroke="#2fd8ff" style="filter:drop-shadow(0 0 2px #2fd8ff)"/><g fill="#9fdcff" font-size="6"><text class="zm" x="3" y="9">— / s</text><text x="3" y="59">0</text><text x="213" y="59" text-anchor="end">maintenant</text></g></svg>
    ${cap("Fichier en cours d'examen")}<div class="fn-txt tf-cible" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;border-left:1px solid #2fd8ff;padding-left:6px"></div>
    ${cap("Journal")}<div class="tf-journal"></div>`);
  const ci = c.querySelector(".tf-cible"), jo = c.querySelector(".tf-journal");
  if (ci) ci.textContent = cible || (avEnCours() ? "en attente du premier fichier" : "aucune analyse en cours");
  if (jo) jo.innerHTML = ligne.length ? ligne.map((x) => `<div class="fn-petit tf-lig ${x.c}" title="${esc(x.t)}">${esc(x.t)}</div>`).join("") : `<div class="fn-petit">Aucune analyse lancée.</div>`;
}
function tickDirect(c: HTMLElement, t: number): void {
  if (t - av.derT >= 1) { av.taux.push(avEnCours() ? Math.max(0, avEtat.fichiers - av.derFich) : 0); av.taux.shift(); av.derFich = avEtat.fichiers; av.derT = t; }
  const mx = Math.max(10, ...av.taux), l = c.querySelector(".zl"), a = c.querySelector(".za"), zm = c.querySelector(".zm");
  if (l && a) { l.setAttribute("d", courbe(av.taux, 216, 58, mx)); a.setAttribute("d", courbe(av.taux, 216, 58, mx, true)); l.setAttribute("transform", "translate(0 2)"); a.setAttribute("transform", "translate(0 2)"); }
  if (zm) zm.textContent = `${nombre(mx)} / s`;
}

const ACTIONS_MENACE: [string, string][] = [["allow", "AUTORISER"], ["clean", "NETTOYER"], ["quarantine", "QUARANTAINE"], ["delete", "SUPPRIMER"]];
function rendreResultats(c: HTMLElement): void {
  const m = avMenaces(), sus = Math.max(m.length, avEtat.menaces), sains = Math.max(0, avEtat.fichiers - sus), pct = avEtat.pct / 100;
  const menace = m.length ? (() => {
    const x = m[0], ligne = document.getElementById("av-threat-0"), fait = !!ligne?.classList.contains("resolved");
    return `<div class="fn-sep"><div class="fn-txt"><b style="color:${COUL.jaune}">${esc(x.name)}</b> <span class="fn-petit">${esc(x.class)} · ${esc(String(x.type || "").toLowerCase())}</span></div>
      <div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:5px">${fait ? `<span class="fn-petit" style="color:${COUL.vert}">menace traitée</span>` : ligne ? ACTIONS_MENACE.map(([a, n]) => bouton(`m:${a}`, n, a === "delete" ? "r tf-pt" : "tf-pt")).join("") : `<span class="fn-petit">actions disponibles à la fin de l'analyse</span>`}</div>${m.length > 1 ? `<div class="fn-petit" style="margin-top:3px">+ ${m.length - 1} autre(s) menace(s) : voir le journal</div>` : ""}</div>`;
  })() : "";
  c.innerHTML = `${cap("Fichiers analysés et menaces")}<div style="display:flex;gap:10px;align-items:center"><svg width="96" height="96" viewBox="0 0 96 96">${donut(48, 48, 36, [{ f: Math.max(0.001, pct * (sains / Math.max(1, avEtat.fichiers))), c: COUL.vert }, { f: sus ? 0.04 : 0, c: COUL.jaune }, { f: Math.max(0.001, 1 - pct), c: "rgba(127,220,255,.25)" }], 7)}
      <text x="48" y="48" text-anchor="middle" font-size="18" font-weight="300" fill="${sus ? COUL.jaune : "#fff"}">${sus}</text><text x="48" y="60" text-anchor="middle" font-size="6.5" fill="#7fb8dc">menace${sus > 1 ? "s" : ""}</text></svg>
    <div style="flex:1">${lgd(COUL.vert, "Fichiers sains", nombre(sains))}${lgd(COUL.jaune, "Suspects", String(sus))}${lgd("rgba(127,220,255,.4)", "Reste à analyser", `${Math.max(0, 100 - avEtat.pct)} %`)}</div></div>${menace}`;
  ecoute(c, (b) => { const [k, a] = (b.dataset.act ?? "").split(":"); if (k === "m") (document.querySelector(`#av-threat-0 button[data-action="${a}"]`) as HTMLElement | null)?.click(); });
}

function etapeAv(cle: string): number {
  const ordre = ["registry", "processes", "files"], i = ordre.indexOf(cle), cur = ordre.indexOf(avEtat.etape);
  if (avEtat.pct >= 100 || cur > i) return 2;
  return cur === i && avEnCours() ? 1 : 0;
}
function rendreProtections(c: HTMLElement): void {
  const live = avProtectionTempsReel();
  const voy = (act: string, couleur: string, nom: string, det: string): string => `<div class="fn-lgd ${act ? "tf-clic" : ""}" ${act ? `data-act="${act}"` : ""} style="gap:7px;margin-bottom:7px"><svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="2.6" fill="${couleur}" style="filter:drop-shadow(0 0 3px ${couleur})"/><circle class="fn-pulse" cx="7" cy="7" r="5" fill="none" stroke="${couleur}" stroke-width=".7"/></svg><span class="fn-txt" style="flex:1"><b>${nom}</b></span><em class="fn-petit">${det}</em></div>`;
  const ET = ["en attente", "en cours", "terminé"], CO = [COUL.gris, COUL.jaune, COUL.vert];
  const e1 = etapeAv("registry"), e2 = etapeAv("processes"), e3 = etapeAv("files"), fait = [e1, e2, e3].filter((x) => x === 2).length;
  c.innerHTML = `${voy("live", live ? COUL.vert : COUL.gris, "Temps réel", live ? "active" : "coupée")}
    <div class="fn-cap">Cliquez sur « Temps réel » pour activer ou couper la protection.</div><div class="fn-sep">${cap("Étapes de l'analyse")}${voy("", CO[e1], "Registre de démarrage", ET[e1])}${voy("", CO[e2], "Processus actifs", ET[e2])}${voy("", CO[e3], "Fichiers du disque", ET[e3])}</div>
    <div class="fn-sep">${frise(["Registre", "Processus", "Fichiers"], fait, avEtat.pct / 100)}<div class="fn-petit" style="margin-top:3px">${avEnCours() ? `analyse en cours · durée <span class="du">0:00</span>` : avEtat.pct >= 100 ? `analyse terminée · durée ${mmss(av.duree)}` : "aucune analyse en cours"}</div></div>`;
  ecoute(c, (b) => { if (b.dataset.act === "live") basculerProtectionTempsReel(); });
}
function tickProtections(c: HTMLElement): void {
  if (avEnCours() && avDebut()) av.duree = (Date.now() - avDebut()) / 1000;
  const d = c.querySelector(".du"), txt = mmss(av.duree);
  if (d && d.textContent !== txt) d.textContent = txt;
}

export const piecesAntivirus = (): PieceDef[] => [
  piece("bouclier", "g", 0, 238, 238, "BOUCLIER", rendreBouclier, tickBouclier, () => cliquer("av-panel-close-btn")),
  piece("direct", "g", 1, 238, 210, "ANALYSE EN DIRECT", rendreDirect, tickDirect),
  piece("resultats", "d", 0, 248, 224, "RÉSULTATS", rendreResultats),
  piece("protections", "d", 1, 248, 228, "PROTECTIONS ET ÉTAPES", rendreProtections, tickProtections),
];

// ───────────────────────────────────────── DÉSINSTALLATEUR ─────────────────────────────────────────
const des = { sel: "" };
const cle = (p: Programme): string => `${p.subkey}|${p.name}`;
const PALETTE = [COUL.cyan, "#2a74ff", COUL.vert, COUL.jaune, COUL.orange, COUL.violet, "#1fa3ff", "#7fdcff"];
interface Tuile { x: number; y: number; w: number; h: number; p: Programme }

/** Treemap « squarified » : la surface d'une tuile est proportionnelle à la taille du programme. */
function treemap(items: { p: Programme; v: number }[], W: number, H: number): Tuile[] {
  const total = items.reduce((s, i) => s + i.v, 0), res: Tuile[] = [];
  if (!total) return res;
  const l = items.map((i) => ({ p: i.p, a: (i.v / total) * W * H }));
  let x = 0, y = 0, w = W, h = H, rangee: typeof l = [];
  const pire = (r: typeof l, cote: number): number => { const s = r.reduce((q, i) => q + i.a, 0), mx = Math.max(...r.map((i) => i.a)), mn = Math.min(...r.map((i) => i.a)); return Math.max((cote * cote * mx) / (s * s), (s * s) / (cote * cote * mn)); };
  const poser = (r: typeof l): void => {
    const s = r.reduce((q, i) => q + i.a, 0);
    if (w >= h) { const lw = s / h; let yy = y; r.forEach((i) => { const hh = i.a / lw; res.push({ x, y: yy, w: lw, h: hh, p: i.p }); yy += hh; }); x += lw; w -= lw; }
    else { const lh = s / w; let xx = x; r.forEach((i) => { const ww = i.a / lh; res.push({ x: xx, y, w: ww, h: lh, p: i.p }); xx += ww; }); y += lh; h -= lh; }
  };
  for (const it of l) {
    const cote = Math.min(w, h);
    if (rangee.length && pire([...rangee, it], cote) > pire(rangee, cote)) { poser(rangee); rangee = []; }
    rangee.push(it);
  }
  if (rangee.length) poser(rangee);
  return res;
}

const tailles = (): Programme[] => lireEtatDesinstall().programmes.filter((p) => (p.size_kb || 0) > 0).sort((a, b) => (b.size_kb || 0) - (a.size_kb || 0));
const choisi = (): Programme | undefined => lireEtatDesinstall().programmes.find((p) => cle(p) === des.sel);
const ko = (p: Programme): number => p.size_kb || 0;

function rendreCarte(c: HTMLElement): void {
  const { programmes } = lireEtatDesinstall(), top = tailles().slice(0, 24);
  if (!programmes.length) { c.innerHTML = vide("Chargement de la liste des logiciels…"); return; }
  if (!top.length) { c.innerHTML = vide("Windows ne renseigne pas la taille des programmes installés."); return; }
  const tuiles = treemap(top.map((p) => ({ p, v: ko(p) })), 216, 150);
  c.innerHTML = `${cap("Plus le bloc est grand, plus le programme pèse lourd · cliquez pour le choisir")}<div style="position:relative;width:216px;height:150px">${tuiles.map((t, i) => {
    const grand = t.w > 44 && t.h > 24;
    return `<div class="fn-tm ${cle(t.p) === des.sel ? "sel" : ""}" data-act="tuile" data-k="${esc(cle(t.p))}" title="${esc(t.p.name)} · ${formatTaille(ko(t.p))}" style="left:${t.x.toFixed(1)}px;top:${t.y.toFixed(1)}px;width:${Math.max(0, t.w - 2).toFixed(1)}px;height:${Math.max(0, t.h - 2).toFixed(1)}px;background:${PALETTE[i % PALETTE.length]}33">${grand ? `${esc(t.p.name.slice(0, Math.floor(t.w / 4.2)))}<br><span style="color:#bfe6ff">${formatTaille(ko(t.p))}</span>` : ""}</div>`;
  }).join("")}</div><div class="fn-petit" style="margin-top:5px">${top.length} plus gros programmes sur ${programmes.length} installés.</div>`;
  ecoute(c, (b) => { if (b.dataset.act === "tuile") { des.sel = b.dataset.k ?? ""; rafraichirPieces("desinstallation"); } });
}

function rendreChoisi(c: HTMLElement): void {
  const e = lireEtatDesinstall(), p = choisi(), total = e.programmes.reduce((s, x) => s + ko(x), 0);
  if (!p) { c.innerHTML = vide("Cliquez un bloc de la carte pour choisir un programme.") + `<div style="margin-top:10px">${bouton("des", "DÉSINSTALLER", "r off")}</div>`; return; }
  const part = total ? ko(p) / total : 0, date = formatDate(p.install_date || "");
  c.innerHTML = `<div style="display:flex;gap:10px;align-items:center"><svg width="82" height="82" viewBox="0 0 82 82">${ticks(41, 41, 34, 40)}${donut(41, 41, 28, [{ f: Math.max(0.002, part), c: COUL.cyan }], 5)}<text x="41" y="40" text-anchor="middle" font-size="12" font-weight="300" fill="#fff">${Math.round(part * 100)}%</text><text x="41" y="51" text-anchor="middle" font-size="6" fill="#7fb8dc">du total</text></svg>
    <div style="flex:1;min-width:0"><div class="fn-txt" style="font-size:11px;color:#fff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</div><div class="fn-big" style="font-size:17px;margin-top:2px">${esc(formatTaille(ko(p)) || "—")}</div>
    <div class="fn-petit" style="margin-top:3px">${esc(p.publisher || "Éditeur inconnu")}${p.version ? ` · version ${esc(p.version)}` : ""}${date ? ` · installé le ${date}` : ""}</div></div></div>
    <div class="fn-petit" style="margin-top:6px">Place libérable : <b style="color:#fff;font-weight:400">${esc(formatTaille(ko(p)) || "inconnue")}</b></div>
    <div style="margin:10px 0 6px">${bouton("des", e.enCours ? "EN COURS…" : "DÉSINSTALLER", `r ${e.enCours ? "off" : ""}`)}</div><div class="fn-petit">Une confirmation vocale et à l'écran sera demandée avant toute suppression.</div>`;
  ecoute(c, (b) => { if (b.dataset.act === "des") { const q = choisi(); if (q && !lireEtatDesinstall().enCours) desinstallerProgramme(q); } });
}

function rendreClassement(c: HTMLElement): void {
  const top = tailles().slice(0, 7);
  if (!top.length) { c.innerHTML = vide(lireEtatDesinstall().programmes.length ? "Tailles non renseignées." : "Chargement de la liste…"); return; }
  const mx = ko(top[0]), W = 126;
  c.innerHTML = `${cap("Les sept programmes les plus volumineux")}<svg width="226" height="${top.length * 20 + 18}" viewBox="0 0 226 ${top.length * 20 + 18}"><g ${AX}>${[0.25, 0.5, 0.75, 1].map((f) => `<path d="M${68 + f * W} 0V${top.length * 20}"/>`).join("")}</g><g ${AX2}><path d="M68 0V${top.length * 20}"/></g>
    ${top.map((p, i) => `<text x="64" y="${i * 20 + 12}" text-anchor="end" font-size="7" fill="${cle(p) === des.sel ? "#fff" : "#bfe6ff"}">${esc(p.name.slice(0, 13))}</text><rect x="68" y="${i * 20 + 5}" width="${Math.max(2, (ko(p) / mx) * W)}" height="9" fill="${PALETTE[i % PALETTE.length]}" fill-opacity=".8" style="filter:drop-shadow(0 0 2px ${PALETTE[i % PALETTE.length]})"/>
      <text x="${72 + (ko(p) / mx) * W}" y="${i * 20 + 12.5}" font-size="6.5" fill="#fff">${esc(formatTaille(ko(p)))}</text>`).join("")}
    <g fill="#9fdcff" font-size="6"><text x="68" y="${top.length * 20 + 10}">0</text><text x="${68 + W}" y="${top.length * 20 + 10}" text-anchor="end">${esc(formatTaille(mx))}</text></g></svg>`;
}

function rendreOperation(c: HTMLElement): void {
  const e = lireEtatDesinstall();
  if (!e.enCours) { c.innerHTML = vide("Aucune désinstallation en cours.") + `<div class="fn-petit">Choisissez un programme, puis « Désinstaller » : JARVIS demande toujours confirmation.</div>`; return; }
  const niv = e.etapes.filter((x) => x === "faite").length, echec = e.etapes.includes("echec");
  const total = e.traces.length;
  c.innerHTML = `<div class="fn-txt" style="min-height:24px">${esc(e.statut.slice(0, 90))}</div><div style="margin-top:8px">${frise(["Programme", "Traces", "Nettoyage"], echec ? 1 : bornes(niv + 1, 1, 3), bornes((niv + 0.5) / 3, 0, 1), echec)}</div>
    ${e.voletTraces ? `<div class="fn-sep"><div class="fn-txt">${total ? `<b>${total}</b> trace${total > 1 ? "s" : ""} résiduelle${total > 1 ? "s" : ""} trouvée${total > 1 ? "s" : ""}` : "Aucune trace résiduelle"}</div>
      <div style="margin-top:6px;display:flex;gap:6px">${total ? bouton("net", "NETTOYER", e.nettoyable ? "" : "off") : ""}${bouton("garder", total ? "GARDER" : "FERMER")}</div></div>` : ""}`;
  ecoute(c, (b) => { if (b.dataset.act === "net") nettoyerTraces(); else if (b.dataset.act === "garder") garderTraces(); });
}

export const piecesDesinstall = (): PieceDef[] => {
  des.sel = "";
  return [
    piece("carte", "g", 0, 238, 238, "TAILLE DES PROGRAMMES", rendreCarte, undefined, () => cliquer("uninstaller-panel-close-btn")),
    piece("choisi", "g", 1, 238, 210, "PROGRAMME CHOISI", rendreChoisi),
    piece("classement", "d", 0, 248, 224, "CLASSEMENT PAR TAILLE", rendreClassement),
    piece("operation", "d", 1, 248, 190, "DÉSINSTALLATION EN COURS", rendreOperation),
  ];
};
