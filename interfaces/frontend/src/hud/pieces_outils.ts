// Pièces éclatées des outils : aide (palette de commandes), minuteurs, maison, réglages (voir eclate.ts, pieces_widgets.ts).
// Les anciens éléments (#help-overlay, #timer-hud, #ha-panel, #settings-modal) restent dans le DOM et portent l'état affiché / masqué
// (plus la logique : sauvegarde, WebSocket) ; leurs pièces lisent les données reçues (donnees_outils.ts, timer_clock.ts, ha_dashboard.ts).
// Rien n'est inventé : sans donnée, la pièce l'écrit.
import { nomJour, t } from "../i18n/i18n";
import type { PieceDef } from "./eclate";
import { piecesOuvertes, rafraichirPieces } from "./eclate";
import { donneesOutils } from "./donnees_outils";
import { commandesAide, type CommandeAide } from "./aide_commandes";
import { hideHelpHUD, showHelpHUD } from "./help_hud";
import { addTimer, lireMinuteurs, resteMinuteur, stopTimer } from "./timer_clock";
import { closeSettingsModal, ouvrirReglagesClassique } from "./settings";
import { orb } from "./orb_state";
import { CATEGORIES } from "../orb_themes";
import { esc } from "../panels/pm_utils";
import { wsRef } from "../ws_link";
import { DEVICES, ROOMS } from "../domotic_map";
import { appelerServiceHA, entitesHA, type EntiteHA } from "../ha_dashboard";

const sansAccent = (t: string): string => [...t.toLowerCase()].map((ch) => ch.normalize("NFD").replace(/[̀-ͯ]/g, "")).join("");
const bornes = (v: number, a: number, b: number): number => Math.min(b, Math.max(a, v));
const brut = (id: string): HTMLElement | null => document.getElementById(id);
const envoyerWs = (obj: Record<string, unknown>): boolean => {
  const ws = wsRef.current;
  if (!ws || ws.readyState !== WebSocket.OPEN) return false;
  ws.send(JSON.stringify(obj));
  return true;
};
/** Fait défiler `zone` juste assez pour montrer `el` (sans toucher aux ancêtres, contrairement à scrollIntoView). */
function voir(zone: HTMLElement, el: HTMLElement | null): void {
  if (!el) return;
  if (el.offsetTop < zone.scrollTop) zone.scrollTop = el.offsetTop;
  else if (el.offsetTop + el.offsetHeight > zone.scrollTop + zone.clientHeight) zone.scrollTop = el.offsetTop + el.offsetHeight - zone.clientHeight;
}
/** Branche une seule fois un clic délégué sur le corps d'une pièce (le contenu est redessiné, pas le corps). */
function surClic(c: HTMLElement, f: (cible: HTMLElement, e: MouseEvent) => void): void {
  if (c.dataset.ecoute) return;
  c.dataset.ecoute = "1";
  c.addEventListener("click", (e) => f(e.target as HTMLElement, e));
}
const segments = (allumes: number, n = 24): string => `<div class="ec-seg">${Array.from({ length: n }, (_, k) => `<i${k < allumes ? "" : ' class="off"'}></i>`).join("")}</div>`;
const tg = (cle: string, on: boolean): string => `<div class="ec-tg${on ? " on" : ""}" data-tg="${cle}" role="switch" aria-checked="${on}"><i></i></div>`;
const bouton = (attr: string, texte: string, extra = ""): string => `<span class="ec-bt${extra ? ` ${extra}` : ""}" ${attr} role="button">${texte}</span>`;

// ═════════════════════════════════════════ AIDE : PALETTE DE COMMANDES ═════════════════════════════════════════
interface EtatAide { q: string; cat: string; sel: number; msg: string }
let aide: EtatAide = { q: "", cat: "TOUT", sel: 0, msg: "" };
const majAide = (): void => rafraichirPieces("aide");

function resultatsAide(): CommandeAide[] {
  const s = sansAccent(aide.q.trim());
  return commandesAide().filter((c) => (aide.cat === "TOUT" || c.cat === aide.cat) && (!s || sansAccent(`${t(c.texte)} ${c.texte} ${c.cat} ${c.sous}`).includes(s)));
}

/** Surligne le texte trouvé (sans tenir compte des accents ni de la casse). */
function surligner(texte: string): string {
  const s = sansAccent(aide.q.trim());
  if (!s) return esc(texte);
  const plat = sansAccent(texte), i = plat.indexOf(s);
  if (i < 0 || plat.length !== texte.length) return esc(texte);
  return `${esc(texte.slice(0, i))}<mark>${esc(texte.slice(i, i + s.length))}</mark>${esc(texte.slice(i + s.length))}`;
}

function lancerCommande(c: CommandeAide | undefined): void {
  if (!c) return;
  if (!envoyerWs({ type: "user_input", text: c.texte })) { aide.msg = "JARVIS N'EST PAS CONNECTÉ"; majAide(); return; }
  orb.noteText(c.texte);
  aide.msg = `ENVOYÉE : ${c.texte.toUpperCase()}`;
  majAide();
  window.setTimeout(hideHelpHUD, 700);
}

function rendreCategories(c: HTMLElement): void {
  const tout = commandesAide(), noms = ["TOUT", ...CATEGORIES.map((k) => k.nom).filter((n) => tout.some((x) => x.cat === n))];
  const zone = c.querySelector(".ec-defile") as HTMLElement | null, haut = zone?.scrollTop ?? 0;
  c.innerHTML = `<div class="ec-defile" style="max-height:168px">${noms.map((n) => `<div class="ec-li${n === aide.cat ? " on" : ""}" data-cat="${esc(n)}" role="button"><span>${esc(n)}</span><span>${n === "TOUT" ? tout.length : tout.filter((x) => x.cat === n).length}</span></div>`).join("")}</div>`;
  const z = c.querySelector(".ec-defile") as HTMLElement;
  z.scrollTop = haut;
  voir(z, z.querySelector(".ec-li.on"));
  surClic(c, (cible) => {
    const l = cible.closest("[data-cat]") as HTMLElement | null;
    if (l?.dataset.cat) { aide.cat = l.dataset.cat; aide.sel = 0; aide.msg = ""; majAide(); }
  });
}

function rendreRecherche(c: HTMLElement): void {
  const n = resultatsAide().length, texte = `${n} RÉSULTAT${n > 1 ? "S" : ""} · ↑ ↓ CHOISIR · ⏎ LANCER`;
  let champ = c.querySelector("input") as HTMLInputElement | null;
  if (!champ) {
    c.innerHTML = `<input class="ec-q" type="text" placeholder="cherche une commande…" autocomplete="off" spellcheck="false" aria-label="Rechercher une commande"><div class="ec-sub ec-nb" style="margin-top:9px"></div>`;
    champ = c.querySelector("input") as HTMLInputElement;
    champ.addEventListener("input", () => { aide.q = champ!.value; aide.sel = 0; aide.msg = ""; majAide(); });
    champ.addEventListener("keydown", (e) => {
      const l = resultatsAide();
      if (e.key === "ArrowDown") { aide.sel = Math.min(l.length - 1, aide.sel + 1); majAide(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { aide.sel = Math.max(0, aide.sel - 1); majAide(); e.preventDefault(); }
      else if (e.key === "Enter") { lancerCommande(l[aide.sel]); e.preventDefault(); }
      else if (e.key === "Escape") { hideHelpHUD(); e.preventDefault(); }
      if (!e.ctrlKey && !e.metaKey) e.stopPropagation();   // les raccourcis du HUD ne doivent pas réagir à la frappe (sauf Ctrl+K)
    });
  }
  if (champ.value !== aide.q) champ.value = aide.q;
  (c.querySelector(".ec-nb") as HTMLElement).textContent = texte;
}
/** Le champ prend le focus dès que la pièce est sortie du sol. */
function tickRecherche(c: HTMLElement): void {
  if (c.dataset.foc) return;
  const piece = c.closest(".ec-piece") as HTMLElement | null, champ = c.querySelector("input") as HTMLInputElement | null;
  if (piece && champ && piece.style.opacity !== "0") { c.dataset.foc = "1"; champ.focus({ preventScroll: true }); }
}

function rendreListe(c: HTMLElement): void {
  const l = resultatsAide();
  if (aide.sel >= l.length) aide.sel = Math.max(0, l.length - 1);
  const zone = c.querySelector(".ec-defile") as HTMLElement | null, haut = zone?.scrollTop ?? 0;
  c.innerHTML = `<div class="ec-defile" style="max-height:150px">${l.length ? l.map((x, i) => `<div class="ec-cmd${i === aide.sel ? " on" : ""}" data-i="${i}" role="button">${surligner(t(x.texte))}</div>`).join("") : `<div class="ec-sub" style="padding:8px 4px;line-height:1.5">Aucune commande.<br>Essaie « musique ».</div>`}</div>`;
  const z = c.querySelector(".ec-defile") as HTMLElement;
  z.scrollTop = haut;
  voir(z, z.querySelector(".ec-cmd.on"));
  surClic(c, (cible) => {
    const r = cible.closest("[data-i]") as HTMLElement | null;
    if (r) { aide.sel = Number(r.dataset.i); aide.msg = ""; majAide(); }
  });
}

function rendreDetail(c: HTMLElement): void {
  const x = resultatsAide()[aide.sel];
  c.innerHTML = x
    ? `<div class="ec-lab" style="color:#7fdcff">${esc(x.cat)}${x.sous ? ` · ${esc(x.sous.toUpperCase())}` : ""}</div><div class="ec-val" style="font-size:12.5px;margin:9px 0 4px;line-height:1.4;letter-spacing:.3px">« ${esc(t(x.texte))} »</div><div class="ec-sub">PHRASE D'EXEMPLE</div><div style="margin-top:10px">${bouton('data-go="1"', "LANCER", "fort")}</div>`
    : `<div class="ec-sub" style="margin-top:6px">Rien de sélectionné.</div>`;
  surClic(c, (cible) => { if (cible.closest("[data-go]")) lancerCommande(resultatsAide()[aide.sel]); });
}

function rendreMessageAide(c: HTMLElement): void {
  c.innerHTML = `<div class="ec-val" style="font-size:10px;line-height:1.35;color:${aide.msg ? "#9dff8a" : "#7fdcff"}">${esc(aide.msg || `${commandesAide().length} COMMANDES · CTRL+K`)}</div>`;
}

export const piecesAide = (): PieceDef[] => {
  aide = { q: "", cat: "TOUT", sel: 0, msg: "" };
  return [
    { id: "cats", cote: "g", rang: 0, w: 200, h: 250, titre: "CATÉGORIES", croix: hideHelpHUD, rendre: rendreCategories },
    { id: "recherche", cote: "g", rang: 1, w: 236, h: 110, forme: "cut", titre: "RECHERCHE", rendre: rendreRecherche, tick: tickRecherche },
    { id: "liste", cote: "d", rang: 0, w: 250, h: 210, titre: "COMMANDES", rendre: rendreListe },
    { id: "detail", cote: "d", rang: 1, w: 236, h: 172, forme: "cut2", titre: "DÉTAIL", rendre: rendreDetail },
    { id: "msg", cote: "d", rang: 2, w: 200, h: 54, forme: "cut", ecart: 24, rendre: rendreMessageAide },
  ];
};

// ═════════════════════════════════════════ MINUTEURS ═════════════════════════════════════════
const hms = (s: number): string => { const n = Math.max(0, Math.floor(s)), h = Math.floor(n / 3600), m = Math.floor((n % 3600) / 60); return h ? `${h}:${String(m).padStart(2, "0")}:${String(n % 60).padStart(2, "0")}` : `${m}:${String(n % 60).padStart(2, "0")}`; };
const plusProche = () => lireMinuteurs().filter((m) => !m.termine).sort((a, b) => a.fin - b.fin)[0] ?? null;
const masquerMinuteurs = (): void => { document.getElementById("timer-hud")?.classList.add("hidden"); };

function rendreListeMinuteurs(c: HTMLElement): void {
  const l = lireMinuteurs();
  c.innerHTML = l.length
    ? l.slice(0, 4).map((m) => `<div style="margin-bottom:11px"><div class="ec-ligne"><span>${esc(m.nom)}</span><span class="ec-val mv" data-id="${m.id}" style="font-size:12px"></span></div><div class="sg" data-id="${m.id}">${segments(24)}</div></div>`).join("") + (l.length > 4 ? `<div class="ec-sub">+ ${l.length - 4} AUTRE${l.length - 4 > 1 ? "S" : ""}</div>` : "")
    : `<div class="ec-sub" style="padding:14px 0">Aucun minuteur en cours.</div>`;
}
function tickListeMinuteurs(c: HTMLElement): void {
  for (const m of lireMinuteurs()) {
    const v = c.querySelector<HTMLElement>(`.mv[data-id="${m.id}"]`);
    if (!v) continue;
    const reste = resteMinuteur(m), txt = m.termine ? "FIN" : hms(reste);
    if (v.textContent !== txt) v.textContent = txt;
    const allumes = m.termine ? 0 : Math.ceil((reste / m.total) * 24);
    c.querySelectorAll<HTMLElement>(`.sg[data-id="${m.id}"] i`).forEach((s, k) => s.classList.toggle("off", k >= allumes));
  }
}

function rendreCommandesMinuteur(c: HTMLElement): void {
  c.innerHTML = `<div style="margin-top:2px">${bouton('data-mn="1"', "+1 MIN")}${bouton('data-mn="5"', "+5 MIN")}${bouton('data-mn="n"', "NOUVEAU 3 MIN")}${bouton('data-mn="x"', "ARRÊTER", "danger")}</div>`;
  surClic(c, (cible) => {
    const b = cible.closest("[data-mn]") as HTMLElement | null;
    if (!b) return;
    const a = b.dataset.mn;
    if (a === "x") { envoyerWs({ type: "user_input", text: "annule le minuteur" }); stopTimer(); }       // le backend annule ses minuteurs, le HUD aussi
    else if (a === "n") envoyerWs({ type: "user_input", text: "mets un minuteur de 3 minutes" });          // le backend le crée, puis il arrive par timer_start
    else addTimer(Number(a) * 60, true);                                                                   // rallonge l'affichage de tous les minuteurs
  });
}

function quand(iso: string): string {
  const d = new Date(iso), a = new Date(), demain = new Date(a.getFullYear(), a.getMonth(), a.getDate() + 1);
  const h = `${d.getHours()}H${String(d.getMinutes()).padStart(2, "0")}`;
  if (d.toDateString() === a.toDateString()) return `AUJ. ${h}`;
  if (d.toDateString() === demain.toDateString()) return `DEM. ${h}`;
  return `${nomJour(d.getDay(), true)} ${d.getDate()}/${String(d.getMonth() + 1).padStart(2, "0")} ${h}`;
}
function rendreAlarmes(c: HTMLElement): void {
  const l = donneesOutils.alarmes;
  if (!l) { c.innerHTML = `<div class="ec-sub" style="padding:8px 0">En attente du backend…</div>`; return; }
  const alarmes = l.filter((a) => !/^minuteur/i.test(a.label)).slice(0, 4), couleurs = ["#ffd23a", "#00e5ff", "#39ff88", "#7fdcff"];
  c.innerHTML = alarmes.length
    ? alarmes.map((a, i) => `<div class="ec-ligne" style="align-items:center;margin-bottom:9px;gap:10px"><i class="ec-pt" style="background:${couleurs[i]};box-shadow:0 0 6px ${couleurs[i]}"></i><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(a.label)}</span><span class="ec-sub" style="font-size:9.5px">${quand(a.heure)}</span></div>`).join("")
    : `<div class="ec-sub" style="padding:8px 0">Aucune alarme programmée.</div>`;
}

function rendreGrand(c: HTMLElement): void {
  c.innerHTML = `<div class="ec-gr gt" style="font-size:30px;margin-top:8px"></div><div class="ec-sub gn" style="margin-top:6px"></div>`;
}
function tickGrand(c: HTMLElement): void {
  const m = plusProche(), t = c.querySelector(".gt"), n = c.querySelector(".gn");
  if (t) t.textContent = m ? hms(resteMinuteur(m)) : "—";
  if (n) n.textContent = m ? m.nom : lireMinuteurs().length ? "FIN" : "AUCUN MINUTEUR ACTIF";
}

function rendreActifs(c: HTMLElement): void {
  const n = lireMinuteurs().filter((m) => !m.termine).length;
  c.innerHTML = `<div class="ec-val" style="font-size:15px">${n} MINUTEUR${n > 1 ? "S" : ""}</div>`;
}

export const piecesMinuteurs = (): PieceDef[] => {
  envoyerWs({ type: "get_alarmes" });   // alarmes et rappels du backend (réponse : alarmes_liste)
  return [
    { id: "liste", cote: "g", rang: 0, w: 200, h: 236, titre: "MINUTEURS", croix: masquerMinuteurs, rendre: rendreListeMinuteurs, tick: tickListeMinuteurs },
    { id: "commandes", cote: "g", rang: 1, w: 236, h: 118, forme: "cut", titre: "COMMANDES", rendre: rendreCommandesMinuteur },
    { id: "alarmes", cote: "d", rang: 0, w: 250, h: 150, titre: "PROCHAINES ALARMES", rendre: rendreAlarmes },
    { id: "grand", cote: "d", rang: 1, w: 216, h: 110, forme: "cut2", titre: "LE PLUS PROCHE", rendre: rendreGrand, tick: tickGrand },
    { id: "actifs", cote: "d", rang: 2, w: 190, h: 54, forme: "cut", ecart: 24, titre: "ACTIFS", rendre: rendreActifs },
  ];
};

// ═════════════════════════════════════════ MAISON ═════════════════════════════════════════
// Le plan vient de domotic_map.ts (ROOMS : emplacement et taille de chaque pièce, DEVICES : lumières par pièce) : il n'est décrit qu'une fois.
// Températures et humidités : capteurs Home Assistant reconnus par leur classe d'appareil et leur nom ; sans capteur, la pièce écrit « — ».
const MOTS_PIECE: Record<string, string[]> = {
  salon: ["salon", "sejour"], cuisine: ["cuisine"], parents: ["parent"], veranda: ["veranda"], garage: ["garage"], couloir: ["couloir"],
  chambre_1: ["ma chambre", "chambre_1", "chambre 1"], chambre_2: ["chambre_2", "chambre 2"], sdb: ["sdb", "salle de bain", "salle_de_bain"], toilettes: ["wc", "toilette"],
};
const NIVEAUX: [number, string][] = [[1, "ÉT. 2"], [0, "ÉT. 1"], [-1, "RDC"]];
let maison = { niveau: 0, piece: "salon" };

const nomHA = (e: EntiteHA): string => sansAccent(`${e.entity_id} ${e.attributes.friendly_name ?? ""}`);
const valide = (e: EntiteHA): boolean => e.state !== "unavailable" && e.state !== "unknown" && !Number.isNaN(parseFloat(e.state));
const dansPiece = (e: EntiteHA, id: string): boolean => (MOTS_PIECE[id] ?? [id]).some((m) => nomHA(e).includes(m));

function capteur(id: string, grandeur: "temperature" | "humidity"): number | null {
  const e = entitesHA().find((x) => x.entity_id.startsWith("sensor.") && valide(x) && dansPiece(x, id)
    && (x.attributes.device_class === grandeur || (grandeur === "temperature" ? x.attributes.unit_of_measurement === "°C" : nomHA(x).includes("humi"))));
  return e ? parseFloat(e.state) : null;
}
const lumieresPiece = (id: string): EntiteHA[] => DEVICES.filter((d) => d.type === "light" && d.room === id)
  .map((d) => entitesHA().find((e) => e.entity_id === d.id)).filter((e): e is EntiteHA => !!e && e.state !== "unavailable");
const climatPiece = (id: string): EntiteHA | undefined => entitesHA().find((e) => e.entity_id.startsWith("climate.") && dansPiece(e, id));
const degres = (v: number | null): string => (v === null ? "—" : `${v.toFixed(1).replace(".", ",")}°`);

function rendrePlan(c: HTMLElement): void {
  const salles = ROOMS.filter((r) => r.level === maison.niveau);
  const parAire = [...salles].sort((p, q) => q.size.x * q.size.z - p.size.x * p.size.z);   // la cuisine est dans le séjour : les grandes pièces sont dessinées d'abord, les petites restent cliquables dessus
  const x0 = Math.min(...salles.map((r) => r.pos.x - r.size.x / 2)), x1 = Math.max(...salles.map((r) => r.pos.x + r.size.x / 2));
  const z0 = Math.min(...salles.map((r) => r.pos.z - r.size.z / 2)), z1 = Math.max(...salles.map((r) => r.pos.z + r.size.z / 2));
  const W = 176, H = 136, k = Math.min(W / (x1 - x0), H / (z1 - z0)), dx = (W - (x1 - x0) * k) / 2, dz = (H - (z1 - z0) * k) / 2;
  const plan = parAire.map((r) => {
    const x = dx + (r.pos.x - r.size.x / 2 - x0) * k, y = dz + (r.pos.z - r.size.z / 2 - z0) * k, w = r.size.x * k, h = r.size.z * k;
    const sel = r.id === maison.piece, ls = lumieresPiece(r.id), allumee = ls.some((l) => l.state === "on");
    const contient = salles.some((q) => q !== r && q.pos.x - q.size.x / 2 >= r.pos.x - r.size.x / 2 && q.pos.x + q.size.x / 2 <= r.pos.x + r.size.x / 2 && q.pos.z - q.size.z / 2 >= r.pos.z - r.size.z / 2 && q.pos.z + q.size.z / 2 <= r.pos.z + r.size.z / 2);
    const yNom = contient ? y + h - 17 : y + 10, yTemp = contient ? y + h - 5 : y + 24;   // le séjour contient la cuisine : ses étiquettes passent en bas
    return `<g class="room" data-r="${r.id}" role="button"><rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${h.toFixed(1)}" fill="rgba(0,229,255,${allumee ? 0.15 : 0.04})" stroke="${sel ? "#fff" : "#00e5ff"}" stroke-opacity="${sel ? 1 : 0.6}" stroke-width="${sel ? 1.8 : 1}" ${sel ? 'style="filter:drop-shadow(0 0 5px #fff)"' : ""}/>
      <text x="${(x + 4).toFixed(1)}" y="${yNom.toFixed(1)}" font-size="${bornes(w / 9, 5, 7)}" fill="#bff3ff" letter-spacing=".6">${esc(r.name.length > Math.floor(w / 4.2) ? r.name.slice(0, Math.max(3, Math.floor(w / 4.2))) : r.name)}</text>
      <text x="${(x + 4).toFixed(1)}" y="${yTemp.toFixed(1)}" font-size="9.5" fill="#fff">${degres(capteur(r.id, "temperature"))}</text>
      <circle cx="${(x + w - 7).toFixed(1)}" cy="${(y + 7).toFixed(1)}" r="3" fill="${ls.length ? (allumee ? "#ffe27a" : "#355") : "none"}" stroke="${ls.length ? "none" : "rgba(0,229,255,.3)"}" ${allumee ? 'style="filter:drop-shadow(0 0 5px #ffe27a)"' : ""}/></g>`;
  }).join("");
  const onglets = NIVEAUX.filter(([n]) => ROOMS.some((r) => r.level === n)).map(([n, nom]) => bouton(`data-niv="${n}"`, nom, `pt${n === maison.niveau ? " on" : ""}`)).join("");
  c.innerHTML = `<div style="margin-bottom:4px">${onglets}</div><svg width="176" height="136" viewBox="0 0 176 136" style="display:block">${plan}</svg>`;
  surClic(c, (cible) => {
    const r = cible.closest("[data-r]") as HTMLElement | null, n = cible.closest("[data-niv]") as HTMLElement | null;
    if (r?.dataset.r) { maison.piece = r.dataset.r; rafraichirPieces("domotique"); }
    else if (n?.dataset.niv) {
      maison.niveau = Number(n.dataset.niv);
      if (!ROOMS.some((q) => q.id === maison.piece && q.level === maison.niveau)) maison.piece = ROOMS.find((q) => q.level === maison.niveau)?.id ?? maison.piece;
      rafraichirPieces("domotique");
    }
  });
}

function rendrePieceChoisie(c: HTMLElement): void {
  const r = ROOMS.find((q) => q.id === maison.piece) ?? ROOMS[0], t = capteur(r.id, "temperature"), h = capteur(r.id, "humidity");
  const ls = lumieresPiece(r.id), on = ls.filter((l) => l.state === "on").length, cl = climatPiece(r.id);
  const consigne = cl && typeof cl.attributes.temperature === "number" ? (cl.attributes.temperature as number) : null;
  c.innerHTML = `<div class="ec-lab" style="color:#e8fbff;margin-bottom:4px">${esc(r.name)}</div>
    <div class="ec-ligne" style="align-items:flex-end"><div class="ec-gr" style="font-size:26px">${degres(t)}</div><div class="ec-sub">${h === null ? "HUMIDITÉ —" : `HUMIDITÉ ${Math.round(h)} %`}</div></div>
    <div style="margin-top:9px">${ls.length ? bouton('data-lum="1"', `LUMIÈRE${ls.length > 1 ? "S" : ""} ${on ? "OFF" : "ON"}`) : `<span class="ec-sub">AUCUNE LUMIÈRE</span>`}</div>
    ${consigne !== null ? `<div class="ec-ligne" style="align-items:center;margin-top:2px"><span class="ec-lab">CONSIGNE</span><span>${bouton('data-cs="-"', "−", "pt")}<span class="ec-val" style="font-size:12px;margin:0 6px">${degres(consigne)}</span>${bouton('data-cs="+"', "+", "pt")}</span></div>` : ""}`;
  surClic(c, (cible) => {
    const sel = ROOMS.find((q) => q.id === maison.piece);
    if (!sel) return;
    if (cible.closest("[data-lum]")) {
      const l = lumieresPiece(sel.id), allumee = l.some((x) => x.state === "on");
      for (const e of l) appelerServiceHA("light", allumee ? "turn_off" : "turn_on", e.entity_id);
    } else {
      const b = cible.closest("[data-cs]") as HTMLElement | null, cli = climatPiece(sel.id);
      if (!b || !cli || typeof cli.attributes.temperature !== "number") return;
      const pas = typeof cli.attributes.target_temp_step === "number" ? (cli.attributes.target_temp_step as number) : 0.5;
      appelerServiceHA("climate", "set_temperature", cli.entity_id, { temperature: (cli.attributes.temperature as number) + (b.dataset.cs === "+" ? pas : -pas) });
    }
  });
}

function barresPieces(c: HTMLElement, grandeur: "temperature" | "humidity"): void {
  const lignes = ROOMS.map((r) => ({ r, v: capteur(r.id, grandeur) })).filter((x) => x.v !== null) as { r: typeof ROOMS[number]; v: number }[];
  if (!lignes.length) { c.innerHTML = `<div class="ec-sub" style="padding:8px 0">${entitesHA().length ? "Aucun capteur reconnu." : "En attente de Home Assistant…"}</div>`; return; }
  c.innerHTML = lignes.slice(0, 5).map(({ r, v }) => `<div class="ec-ligne" style="align-items:center;gap:8px;margin-bottom:7px"><span style="width:70px;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.name)}</span><div class="ec-fil"><i style="width:${bornes(grandeur === "temperature" ? ((v - 10) / 20) * 100 : v, 3, 100)}%"></i></div><span style="width:38px;text-align:right;font-size:10px">${grandeur === "temperature" ? degres(v) : `${Math.round(v)}%`}</span></div>`).join("");
}
const rendreTemperatures = (c: HTMLElement): void => barresPieces(c, "temperature");
const rendreHumidites = (c: HTMLElement): void => barresPieces(c, "humidity");

function rendreLumieres(c: HTMLElement): void {
  const l = entitesHA().filter((e) => e.entity_id.startsWith("light.") && e.state !== "unavailable"), on = l.filter((e) => e.state === "on").length;
  c.innerHTML = l.length ? `<div class="ec-val" style="font-size:15px">${on} / ${l.length} ALLUMÉE${on > 1 ? "S" : ""}</div>` : `<div class="ec-sub">${entitesHA().length ? "AUCUNE LUMIÈRE" : "EN ATTENTE…"}</div>`;
}

const fermerMaison = (): void => { brut("ha-panel-close-btn")?.click(); };
export const piecesMaison = (): PieceDef[] => {
  if (!entitesHA().length) envoyerWs({ type: "ha_get_states" });
  maison = { niveau: ROOMS.find((r) => r.id === maison.piece)?.level ?? 0, piece: maison.piece };
  return [
    { id: "plan", cote: "g", rang: 0, w: 200, h: 236, titre: "PLAN", croix: fermerMaison, rendre: rendrePlan },
    { id: "piece", cote: "g", rang: 1, w: 236, h: 148, forme: "cut", titre: "PIÈCE", rendre: rendrePieceChoisie },
    { id: "temp", cote: "d", rang: 0, w: 240, h: 160, titre: "TEMPÉRATURES", rendre: rendreTemperatures },
    { id: "humi", cote: "d", rang: 1, w: 216, h: 140, forme: "cut2", titre: "HUMIDITÉ", rendre: rendreHumidites },
    { id: "lum", cote: "d", rang: 2, w: 200, h: 54, forme: "cut", ecart: 24, titre: "LUMIÈRES", rendre: rendreLumieres },
  ];
};

// ═════════════════════════════════════════ RÉGLAGES ═════════════════════════════════════════
// Chaque contrôle agit sur le vrai champ de #settings-modal (même gestionnaires : aperçu immédiat, sauvegarde, update_settings).
const ACCENTS: [valeur: string, nom: string, couleur: string][] = [["cyan", "CYAN", "#00e5ff"], ["emerald", "ÉMERAUDE", "#10d89a"], ["amber", "AMBRE", "#ffb020"], ["red", "ROUGE", "#ff4d6d"], ["gold", "OR", "#e6c86e"], ["anneaux", "VIOLET", "#9b6bff"]];
const ECO: [string, string][] = [["auto", "AUTO"], ["1", "ON"], ["0", "OFF"]];
const champ = (id: string): HTMLInputElement | HTMLSelectElement | null => brut(id) as HTMLInputElement | HTMLSelectElement | null;
function poser(id: string, valeur: string): void {
  const c = champ(id);
  if (!c) return;
  c.value = valeur;
  c.dispatchEvent(new Event("change", { bubbles: true }));
}
const majReglages = (): void => rafraichirPieces("parametres");

function rendreApparence(c: HTMLElement): void {
  const accent = champ("settings-orb-style")?.value || "cyan", eco = champ("settings-orb-eco")?.value || "auto";
  const cur = ACCENTS.find((a) => a[0] === accent) ?? ACCENTS[0];
  c.innerHTML = `<div class="ec-lab" style="margin-bottom:8px">COULEUR</div><div>${ACCENTS.map(([v, nom, col]) => `<span class="ec-sw${v === accent ? " on" : ""}" data-sw="${v}" title="${nom}" role="button" style="background:${col};--col:${col}"></span>`).join("")}</div>
    <div style="height:3px;margin:10px 0 6px;background:linear-gradient(90deg,${cur[2]},transparent)"></div><div class="ec-sub">ACCENT ${cur[1]}</div>
    <div class="ec-lab" style="margin:14px 0 6px">MODE ÉCONOME</div><div>${ECO.map(([v, nom]) => bouton(`data-eco="${v}"`, nom, v === eco ? "on" : "")).join("")}</div><div class="ec-sub" style="font-size:8.5px">ON : 30 images/s en permanence</div>`;
  surClic(c, (cible) => {
    const s = cible.closest("[data-sw]") as HTMLElement | null, e = cible.closest("[data-eco]") as HTMLElement | null;
    if (s?.dataset.sw) poser("settings-orb-style", s.dataset.sw);
    else if (e?.dataset.eco) poser("settings-orb-eco", e.dataset.eco);
    else return;
    majReglages();
  });
}

function rendreProfil(c: HTMLElement): void {
  const mic = champ("settings-mic") as HTMLSelectElement | null, micNom = mic?.selectedOptions[0]?.textContent?.replace(/^\[INDEX \d+\]\s*/, "") ?? "—";
  if (!c.querySelector("input")) {
    c.innerHTML = `<div class="ec-ligne" style="gap:10px"><div style="flex:1"><div class="ec-lab">PRÉNOM</div><input class="ec-q ec-nom" type="text" autocomplete="off" spellcheck="false"></div></div>
      <div class="ec-lab" style="margin-top:9px">MICRO</div><div class="ec-sub ec-mic" style="margin-top:3px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"></div><div style="margin-top:8px">${bouton('data-save="1"', "SAUVEGARDER", "fort")}</div>`;
    for (const [classe, id] of [[".ec-nom", "settings-name"]] as const) {
      const i = c.querySelector(classe) as HTMLInputElement;
      i.addEventListener("input", () => { const r = champ(id); if (r) r.value = i.value; });
      i.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSettingsModal(); e.stopPropagation(); });
    }
    surClic(c, (cible) => { if (cible.closest("[data-save]")) brut("settings-save-btn")?.click(); });
  }
  for (const [classe, id] of [[".ec-nom", "settings-name"]] as const) {
    const i = c.querySelector(classe) as HTMLInputElement, r = champ(id);
    if (r && i !== document.activeElement && i.value !== r.value) i.value = r.value;
  }
  (c.querySelector(".ec-mic") as HTMLElement).textContent = micNom;
}

function rendreAvance(c: HTMLElement): void {
  c.innerHTML = `<div>${[["api", "CLÉS API"], ["apps", "APPLICATIONS"], ["musique", "MUSIQUE"], ["discord", "DISCORD"]].map(([t, nom]) => bouton(`data-tab="${t}"`, nom, "pt")).join("")}</div>`;
  surClic(c, (cible) => { const b = cible.closest("[data-tab]") as HTMLElement | null; if (b?.dataset.tab) ouvrirReglagesClassique(b.dataset.tab); });
}

function rendreVoix(c: HTMLElement): void {
  const r = donneesOutils.reglages, voix = r.voix === "homme" ? "HOMME · HENRI" : r.voix === "femme" ? "FEMME · DENISE" : r.voix ? r.voix.toUpperCase() : "—";
  c.innerHTML = `<div class="ec-lab">VOIX DE JARVIS</div><div class="ec-val" style="font-size:12px;margin:4px 0 12px">${esc(voix)}</div><div class="ec-lab">MOT D'ÉVEIL</div><div class="ec-val" style="font-size:12px;margin-top:4px">${r.motEveil ? `« ${esc(r.motEveil.toUpperCase())} »` : "—"}</div>
    <div class="ec-sub" style="margin-top:10px;font-size:9px">Se change à la voix : « prends la voix de femme ».</div>`;
}

function rendreProfils(c: HTMLElement): void {
  const p = donneesOutils.reglages.profils;
  if (!p) { c.innerHTML = `<div class="ec-sub" style="padding:8px 0">En attente du backend…</div>`; return; }
  c.innerHTML = p.length ? p.map((x) => `<div style="margin-bottom:10px"><div class="ec-ligne"><span>${esc(x.nom.toUpperCase())}</span><span class="ec-sub" style="font-size:9px">${x.echantillons} ÉCHANTILLON${x.echantillons > 1 ? "S" : ""}</span></div>${segments(Math.min(10, x.echantillons), 10)}</div>`).join("") : `<div class="ec-sub" style="padding:8px 0">Aucun profil enregistré.</div>`;
}

function rendreSecurite(c: HTMLElement): void {
  const av = (champ("settings-av-live") as HTMLInputElement | null)?.checked === true, ver = brut("maj-version")?.textContent?.replace(/^Version\s*/i, "").trim() || "—";
  c.innerHTML = `<div class="ec-ligne" style="align-items:center"><span>Antivirus live</span>${tg("av", av)}</div><div class="ec-sub" style="margin-top:6px;font-size:9px">VERSION ${esc(ver)}</div>`;
  surClic(c, (cible) => { if (cible.closest("[data-tg]")) { (champ("settings-av-live") as HTMLInputElement | null)?.click(); majReglages(); } });
}

export const piecesReglages = (): PieceDef[] => {
  envoyerWs({ type: "get_settings" });   // (déjà demandé par openSettingsModal : cette ligne ne sert que si l'ouverture vient d'ailleurs)
  return [
    { id: "apparence", cote: "g", rang: 0, w: 200, h: 236, titre: "APPARENCE", croix: closeSettingsModal, rendre: rendreApparence },
    { id: "profil", cote: "g", rang: 1, w: 236, h: 152, forme: "cut", titre: "PROFIL", rendre: rendreProfil },
    { id: "avance", cote: "g", rang: 2, w: 236, h: 104, forme: "cut", ecart: 0, titre: "PLUS DE RÉGLAGES", rendre: rendreAvance },
    { id: "voix", cote: "d", rang: 0, w: 240, h: 150, titre: "VOIX ET ÉVEIL", rendre: rendreVoix },
    { id: "profils", cote: "d", rang: 1, w: 216, h: 118, forme: "cut2", titre: "PROFILS VOCAUX", rendre: rendreProfils },
    { id: "securite", cote: "d", rang: 2, w: 200, h: 74, forme: "cut", ecart: 24, titre: "SÉCURITÉ", rendre: rendreSecurite },
  ];
};

// ═════════════════════════════════════════ BRANCHEMENT ═════════════════════════════════════════
const RAISON_DE: Record<string, string> = { alarmes: "minuteur", minuteurs: "minuteur", reglages: "parametres", ha: "domotique" };

export function initOutilsEclates(): void {
  // Un changement de donnée redessine les pièces ouvertes (sans rejouer leur sortie du sol)
  window.addEventListener("outils-maj", (e) => {
    const raison = RAISON_DE[(e as CustomEvent<string>).detail];
    if (raison && piecesOuvertes(raison)) rafraichirPieces(raison);
  });
  document.addEventListener("keydown", (e) => {
    const t = e.target as HTMLElement | null;
    if ((e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (brut("help-overlay")?.classList.contains("visible")) hideHelpHUD(); else showHelpHUD();
    } else if (e.key === "Escape" && !(t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) {
      if (brut("help-overlay")?.classList.contains("visible")) hideHelpHUD();
      else if (brut("settings-modal")?.classList.contains("visible") && !document.body.classList.contains("reglages-classique")) closeSettingsModal();
    }
  });
}
