// ── MISES À JOUR : bannière dans les Paramètres, bouton de vérification manuelle, carte au lancement ──
// Le backend (core/mises_a_jour.py) compare la version installée à la dernière release GitHub.
import { cardManager } from "../cards";
import { wsRef } from "../ws_link";
import { esc } from "./pm_utils";

interface EtatMaj {
  etat: "a_jour" | "disponible" | "erreur";
  actuelle: string;
  version?: string;
  notes?: string;
  url?: string;
  detail?: string;
  auto?: boolean;
}

let derniere: EtatMaj | null = null;
let carteMontree = false;

function envoyer(msg: object): void {
  const ws = wsRef.current;
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

function reportee(version: string): boolean {
  try {
    return localStorage.getItem("jarvis_maj_reportee") === version;
  } catch {
    return false;
  }
}

function reporter(version: string): void {
  try {
    localStorage.setItem("jarvis_maj_reportee", version);
  } catch {
    // navigation privée : la bannière reviendra au prochain lancement
  }
}

/** Notes de release en texte simple : sans titres ni gras Markdown, sur quelques lignes. */
function notesLisibles(notes: string): string {
  return notes
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/\*\*|__|`/g, "")
    .replace(/^>\s?/gm, "")
    .split("\n").map((l) => l.trim()).filter(Boolean).slice(0, 6).join("\n");
}

function afficherEtat(texte: string, classe: string): void {
  const el = document.getElementById("maj-etat");
  if (el) {
    el.textContent = texte;
    el.className = `maj-etat ${classe}`;
  }
}

function afficher(d: EtatMaj): void {
  derniere = d;
  const version = document.getElementById("maj-version");
  if (version) version.textContent = `Version ${d.actuelle}`;
  const bouton = document.getElementById("maj-verifier") as HTMLButtonElement | null;
  if (bouton) bouton.disabled = false;
  const ban = document.getElementById("maj-banniere");

  if (d.etat === "erreur") {
    if (!d.auto) afficherEtat(d.detail || "Vérification impossible.", "maj-ko");
    return;
  }
  if (d.etat === "a_jour") {
    afficherEtat(`Vous êtes à jour (v${d.actuelle})`, "maj-ok");
    ban?.classList.add("hidden");
    return;
  }
  // Mise à jour disponible
  afficherEtat(`Mise à jour disponible (v${d.version})`, "maj-nouveau");
  if (d.auto && reportee(String(d.version))) return; // « Plus tard » déjà choisi pour cette version
  if (ban) {
    ban.innerHTML = `
      <span class="maj-point"></span>
      <div class="maj-texte">
        <div class="maj-titre">Mise à jour disponible : v${esc(d.version)} <small>(actuelle : v${esc(d.actuelle)})</small></div>
        ${d.notes ? `<div class="maj-notes">${esc(notesLisibles(d.notes))}</div>` : ""}
      </div>
      <div class="maj-actions">
        <button class="settings-btn primary" data-maj="telecharger">Télécharger la mise à jour</button>
        <button class="settings-btn" data-maj="plus-tard">Plus tard</button>
      </div>`;
    ban.classList.remove("hidden");
  }
  if (d.auto && !carteMontree) {
    carteMontree = true;
    cardManager.showCard({
      id: "carte-maj", title: "Mise à jour disponible", type: "info", icon: "◈", duration: 12000,
      content: `JARVIS ${esc(d.version)} est disponible (vous avez ${esc(d.actuelle)}). Ouvrez les Paramètres pour la télécharger.`,
    });
  }
}

export function handleUpdateMessage(data: any): boolean {
  if (data.type === "update_status") {
    afficher(data as EtatMaj);
    return true;
  }
  // Lu sans être consommé : la case « Vérifier au lancement » reflète le réglage enregistré
  if (data.type === "settings_data" && data.data) {
    const caseAuto = document.getElementById("maj-auto") as HTMLInputElement | null;
    if (caseAuto) caseAuto.checked = data.data.maj_auto !== false;
  }
  return false;
}

/** Vérification automatique discrète, ~3 s après la connexion (appelée par connection.ts). */
export function verificationAuLancement(): void {
  window.setTimeout(() => envoyer({ type: "check_update", auto: true }), 3000);
}

export function initMisesAJour(): void {
  document.getElementById("maj-verifier")?.addEventListener("click", (e) => {
    (e.currentTarget as HTMLButtonElement).disabled = true;
    afficherEtat("Vérification en cours...", "maj-attente");
    envoyer({ type: "check_update", auto: false });
  });
  document.getElementById("maj-auto")?.addEventListener("change", (e) => {
    envoyer({ type: "update_settings", settings: { maj_auto: (e.currentTarget as HTMLInputElement).checked } });
  });
  document.getElementById("maj-banniere")?.addEventListener("click", (e) => {
    const action = (e.target as HTMLElement).closest("[data-maj]") as HTMLElement | null;
    if (!action || !derniere) return;
    if (action.dataset.maj === "telecharger" && derniere.url) {
      envoyer({ type: "open_release", url: derniere.url });
    } else if (action.dataset.maj === "plus-tard") {
      if (derniere.version) reporter(derniere.version);
      document.getElementById("maj-banniere")?.classList.add("hidden");
    }
  });
}
