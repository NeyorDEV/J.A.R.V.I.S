// ── ÉTAT DU SYSTÈME : moteurs d'IA, voix, services, ressources (style verre : css/13 et css/14) ──
// Le backend (core/ws_etat_systeme.py) répond à « get_system_status » et exécute « system_test ».
import { makePanelDraggable } from "../ui/draggable";
import { wsRef } from "../ws_link";
import { esc, icone } from "./pm_utils";

const ETATS: Record<string, [string, string]> = {
  actif: ["ok", "actif"], pret: ["ok", "prêt"], libre: ["ok", "libre"],
  pause: ["warn", "pause"], absent: ["", "absent"],
};

let minuteur: number | undefined;
let resultats: Record<string, { ok: boolean; detail: string; duree: number }> = {};
let dernier: any = null;

function envoyer(msg: object): void {
  const ws = wsRef.current;
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function pastille(classe: string, texte: string): string {
  return `<span class="sys-pastille ${classe}">${esc(texte)}</span>`;
}

function anneau(valeur: number | null, couleur: string, etiquette: string, sous = ""): string {
  const v = valeur == null ? 0 : Math.max(0, Math.min(100, valeur));
  const circ = 2 * Math.PI * 32;
  return `<div class="sys-jauge"><svg viewBox="0 0 80 80" aria-hidden="true">
      <circle cx="40" cy="40" r="32" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="6"/>
      <circle cx="40" cy="40" r="32" fill="none" stroke="${couleur}" stroke-width="6" stroke-linecap="round"
        stroke-dasharray="${(circ * v / 100).toFixed(1)} ${circ.toFixed(1)}" transform="rotate(-90 40 40)"
        style="filter:drop-shadow(0 0 5px ${couleur})"/></svg>
      <div class="sys-jauge-v">${valeur == null ? "—" : Math.round(v) + "%"}</div>
      <div class="sys-jauge-e">${esc(etiquette)}</div>${sous ? `<div class="sys-jauge-s">${esc(sous)}</div>` : ""}</div>`;
}

function ligneMoteur(m: any): string {
  const [classe, libelle] = ETATS[m.etat] || ["", m.etat];
  const test = resultats[m.id];
  let detail = m.detail || "";
  if (m.etat === "pause") detail = `quota · ${m.pause} s`;
  else if (m.etat === "absent") detail = "clé manquante";
  if (test) detail = test.ok ? `test ok · ${String(test.duree).replace(".", ",")} s` : `échec · ${test.detail}`;
  const bouton = m.etat === "absent" ? "" :
    `<button class="pm-icone-bouton sys-test" data-test="${esc(m.id)}" title="Tester ${esc(m.nom)}">${icone("lecture")}</button>`;
  const echec = !!test && !test.ok;
  return `<div class="sys-ligne"><span>${pastille(echec ? "ko" : classe, echec ? "échec" : libelle)}</span>
    <span class="sys-nom">${esc(m.nom)}</span><span class="sys-det">${esc(detail)}</span>${bouton}</div>`;
}

function dessiner(d: any): void {
  const corps = document.getElementById("system-corps");
  if (!corps || !d) return;
  dernier = d;
  const v = d.voix, s = d.services, r = d.ressources;
  const pb = pastille;
  const etatsVoix: Record<string, string> = {
    veille: "micro en veille", ecoute: "à l'écoute", parle: "JARVIS parle", reflechit: "réflexion", muet: "micro coupé",
  };
  const moteursOk = d.moteurs.filter((m: any) => m.etat === "actif" || m.etat === "pret").length;
  const global = document.getElementById("system-global");
  if (global) {
    const probleme = moteursOk === 0 || v.muet;
    global.className = "sys-pastille " + (probleme ? "ko" : "ok");
    global.textContent = probleme ? "à vérifier" : "tout fonctionne";
  }
  const sous = document.getElementById("system-sous");
  if (sous) {
    sous.textContent = `${moteursOk} moteur${moteursOk > 1 ? "s" : ""} disponible${moteursOk > 1 ? "s" : ""} · mis à jour à ${new Date(d.t * 1000).toLocaleTimeString("fr-FR")}`;
  }

  const resMicro = resultats["micro"];
  const kv = (k: string, val: string) => `<div class="sys-kv"><span>${esc(k)}</span><b>${esc(val)}</b></div>`;
  const score = v.locuteur ? String(Number(v.locuteur.score).toFixed(2)).replace(".", ",") : "";
  corps.innerHTML = `
    <div class="sys-grille">
      <div class="sys-carte"><h4>MOTEURS D'IA <small>ordre d'essai</small></h4>${d.moteurs.map(ligneMoteur).join("")}</div>
      <div class="sys-carte"><h4>VOIX <small>${esc(etatsVoix[v.etat] || v.etat)}</small></h4>
        ${kv("Micro", v.micro || "—")}
        <div class="sys-niveau"><i style="width:${Math.round(Math.min(1, v.niveau) * 100)}%"></i></div>
        ${kv("Locuteur reconnu", v.locuteur ? `${v.locuteur.nom} · ${score}` : "—")}
        ${kv("Mot d'éveil", `« ${v.mot_eveil} »`)}
        ${kv("Synthèse vocale", v.synthese)}
        <div class="sys-actions">
          <button class="pm-bouton petit" id="system-test-micro">${icone("micro")} Tester le micro</button>
          <button class="pm-bouton petit" id="system-ecouter">${icone("haut_parleur")} Écouter</button>
        </div>
        ${resMicro ? `<div class="sys-resultat ${resMicro.ok ? "ok" : "ko"}">${esc(resMicro.detail)}</div>` : ""}
      </div>
      <div class="sys-carte"><h4>SERVICES</h4>
        <div class="sys-ligne">${pb("ok", "ok")}<span class="sys-nom">Interfaces connectées</span><span class="sys-det">${s.interfaces}</span></div>
        <div class="sys-ligne">${pb(s.souvenirs == null ? "" : "ok", s.souvenirs == null ? "inconnu" : "ok")}<span class="sys-nom">Mémoire vectorielle</span><span class="sys-det">${s.souvenirs == null ? "—" : s.souvenirs + " souvenirs"}</span></div>
        <div class="sys-ligne">${pb(s.home_assistant ? "ok" : "ko", s.home_assistant ? "ok" : "hors ligne")}<span class="sys-nom">Home Assistant</span><span class="sys-det">${s.home_assistant ? "configuré" : "non configuré"}</span></div>
        <div class="sys-ligne">${pb(s.antivirus ? "ok" : "", s.antivirus ? "actif" : "inactif")}<span class="sys-nom">Antivirus temps réel</span><span class="sys-det">${s.antivirus ? "protection active" : "désactivé"}</span></div>
        <div class="sys-ligne">${pb(s.musique === "Playing" ? "ok" : "", s.musique === "Playing" ? "lecture" : s.musique === "Paused" ? "pause" : "arrêt")}<span class="sys-nom">Musique</span><span class="sys-det">${esc(s.musique === "Playing" ? "en cours" : s.musique === "Paused" ? "en pause" : "aucune lecture")}</span></div>
        <div class="sys-ligne">${pb(s.alarme ? "warn" : "", s.alarme ? "prévue" : "aucune")}<span class="sys-nom">Prochaine alarme</span><span class="sys-det">${esc(s.alarme || "—")}</span></div>
      </div>
      <div class="sys-carte"><h4>RESSOURCES</h4>
        <div class="sys-jauges">${anneau(r.cpu, "#00e5ff", "CPU")}${anneau(r.ram, "#b388ff", "RAM")}${anneau(r.gpu, "#3ddc97", "GPU", r.vram != null ? `VRAM ${Math.round(r.vram)} %` : "")}</div>
      </div>
    </div>`;
}

function demander(): void {
  envoyer({ type: "get_system_status" });
}

function ouvrir(panel: HTMLElement): void {
  panel.classList.remove("hidden");
  panel.classList.add("visible");
  demander();
  window.clearInterval(minuteur);
  minuteur = window.setInterval(demander, 2000);
}

function fermer(panel: HTMLElement): void {
  panel.classList.remove("visible");
  panel.classList.add("hidden");
  window.clearInterval(minuteur);
  minuteur = undefined;
}

export function handleSystemPanelMessage(data: any): boolean {
  if (data.type === "system_status") {
    dessiner(data);
    return true;
  }
  if (data.type === "system_test_result") {
    if (data.id === "fin") {
      const b = document.getElementById("system-test-all") as HTMLButtonElement | null;
      if (b) {
        b.disabled = false;
        b.innerHTML = `${icone("lecture")} Tout tester`;
      }
    } else {
      resultats[data.id] = { ok: !!data.ok, detail: String(data.detail || ""), duree: Number(data.duree) || 0 };
      if (dernier) dessiner(dernier);
    }
    return true;
  }
  return false;
}

export function initSystemPanel(): void {
  const panel = document.getElementById("system-panel");
  if (!panel) return;
  const tete = document.getElementById("system-tete");
  if (tete) makePanelDraggable(panel as HTMLDivElement, tete as HTMLDivElement);
  document.getElementById("system-fermer")?.addEventListener("click", () => fermer(panel));
  document.getElementById("carousel-system-btn")?.addEventListener("click", () => {
    if (panel.classList.contains("hidden")) ouvrir(panel);
    else fermer(panel);
  });
  document.getElementById("system-test-all")?.addEventListener("click", (e) => {
    const b = e.currentTarget as HTMLButtonElement;
    resultats = {};
    b.disabled = true;
    b.textContent = "Test en cours…";
    envoyer({ type: "system_test", cible: "all" });
  });
  // Délégation : les boutons des cartes sont recréés à chaque mise à jour
  panel.addEventListener("click", (e) => {
    const cible = e.target as HTMLElement;
    const test = cible.closest("[data-test]") as HTMLElement | null;
    if (test) {
      delete resultats[test.dataset.test || ""];
      envoyer({ type: "system_test", cible: test.dataset.test });
      return;
    }
    if (cible.closest("#system-test-micro")) {
      delete resultats["micro"];
      envoyer({ type: "system_test", cible: "micro" });
      return;
    }
    if (cible.closest("#system-ecouter")) envoyer({ type: "system_test", cible: "voix" });
  });
}
