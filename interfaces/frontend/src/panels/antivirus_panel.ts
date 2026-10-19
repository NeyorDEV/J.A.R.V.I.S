// ── Panneau sécurité / antivirus (style commun css/13_panneaux_modules.css) ──
// État en un coup d'œil (anneau d'avancement, fichiers analysés, menaces, durée), couleur
// selon l'état (ambre : analyse, vert : sain, rouge : menace), une carte par menace avec ses
// actions, protection en temps réel réglable depuis l'en-tête, journal repliable.

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { esc, formatNombre, icone } from "./pm_utils";

const avPanelEl = document.getElementById("av-panel") as HTMLDivElement;
const avHeaderEl = document.getElementById("av-panel-header") as HTMLDivElement;
const avCloseBtn = document.getElementById("av-panel-close-btn") as HTMLButtonElement;
const avCancelBtn = document.getElementById("av-cancel-btn") as HTMLButtonElement;
const avProgressFill = document.getElementById("av-progress-bar-fill") as HTMLElement;
const avProgressPct = document.getElementById("av-progress-percent") as unknown as SVGTextElement;
const avAnneau = document.getElementById("av-anneau-valeur") as unknown as SVGCircleElement;
const avStatusLabel = document.getElementById("av-status-label") as HTMLDivElement;
const avThreatsCount = document.getElementById("av-threats-count") as HTMLElement;
const avNbFichiers = document.getElementById("av-nb-fichiers") as HTMLElement;
const avDuree = document.getElementById("av-duree") as HTMLElement;
const avCurrentFile = document.getElementById("av-current-file") as HTMLDivElement;
const avConsole = document.getElementById("av-console") as HTMLDivElement;
const avThreatsListEl = document.getElementById("av-threats-list") as HTMLDivElement;
const avLiveToggle = document.getElementById("av-live-toggle") as HTMLInputElement;

const CIRCONFERENCE = 2 * Math.PI * 38;
const ETAPES: Record<string, string> = {
  registry: "Analyse du registre de démarrage",
  processes: "Analyse des processus actifs",
  files: "Analyse des fichiers",
};

let avScanInProgress = false;
let avThreatsList: any[] = [];
let avResolvedThreatsCount = 0;
let debutAnalyse = 0;
let minuterieDuree: number | null = null;
let avTimerMasquage: number | null = null;   // masquage différé, annulable à la réouverture

if (avPanelEl && avHeaderEl) {
  makePanelDraggable(avPanelEl, avHeaderEl);
}

// ── Affichage ───────────────────────────────────────────────────────────────
function etat(texte: string, classe: "" | "etat-sain" | "threat-detected" = "") {
  if (avStatusLabel) avStatusLabel.textContent = texte;
  avPanelEl?.classList.remove("etat-sain", "threat-detected");
  if (classe) avPanelEl?.classList.add(classe);
}

function progression(pct: number) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  if (avProgressFill) avProgressFill.style.width = `${p}%`;
  if (avProgressPct) avProgressPct.textContent = `${p}%`;
  if (avAnneau) avAnneau.setAttribute("stroke-dashoffset", String(CIRCONFERENCE * (1 - p / 100)));
}

function compterMenaces(n: number) {
  if (avThreatsCount) {
    avThreatsCount.textContent = String(n);
    avThreatsCount.style.color = n > 0 ? "#ff5a5f" : "";
  }
}

function journal(texte: string, classe: "" | "menace" | "ok" = "") {
  if (!avConsole) return;
  const ligne = document.createElement("div");
  if (classe) ligne.className = classe;
  ligne.textContent = texte;
  avConsole.appendChild(ligne);
  avConsole.scrollTop = avConsole.scrollHeight;
}

function demarrerMinuterie() {
  arreterMinuterie();
  debutAnalyse = Date.now();
  const tic = () => {
    const s = Math.floor((Date.now() - debutAnalyse) / 1000);
    if (avDuree) avDuree.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  tic();
  minuterieDuree = window.setInterval(tic, 1000);
}

function arreterMinuterie() {
  if (minuterieDuree !== null) clearInterval(minuterieDuree);
  minuterieDuree = null;
}

function finAnalyse() {
  avScanInProgress = false;
  arreterMinuterie();
  if (avCancelBtn) avCancelBtn.textContent = "Fermer";
}

// ── Ouverture / fermeture ───────────────────────────────────────────────────
export function openAntivirusPanel() {
  if (!avPanelEl) return;
  // Annule un masquage différé encore en attente (réouverture dans les 400 ms)
  if (avTimerMasquage !== null) {
    clearTimeout(avTimerMasquage);
    avTimerMasquage = null;
  }
  avPanelEl.classList.remove("hidden");
  void avPanelEl.offsetWidth; // reflow : relance l'animation d'ouverture
  avPanelEl.classList.add("visible");

  etat("Initialisation de l'analyse…");
  progression(0);
  compterMenaces(0);
  if (avNbFichiers) avNbFichiers.textContent = "0";
  if (avCurrentFile) { avCurrentFile.textContent = "Connexion au moteur de sécurité…"; avCurrentFile.style.display = ""; }
  if (avConsole) avConsole.innerHTML = "";
  journal("[INFO] Démarrage de l'analyse rapide.");
  avThreatsList = [];
  avResolvedThreatsCount = 0;
  if (avThreatsListEl) { avThreatsListEl.innerHTML = ""; avThreatsListEl.classList.add("hidden"); }

  // Interrupteur de protection temps réel : même état que dans les paramètres
  const reglage = document.getElementById("settings-av-live") as HTMLInputElement | null;
  if (avLiveToggle && reglage) avLiveToggle.checked = reglage.checked;

  if (avCancelBtn) { avCancelBtn.textContent = "Annuler"; avCancelBtn.disabled = false; }
  avScanInProgress = true;
  demarrerMinuterie();
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "av_scan_start" }));
  }
}

export function closeAntivirusPanel() {
  if (!avPanelEl) return;
  if (avScanInProgress) cancelAvScan();
  avPanelEl.classList.remove("visible");
  if (avTimerMasquage !== null) clearTimeout(avTimerMasquage);
  avTimerMasquage = window.setTimeout(() => {
    avPanelEl.classList.add("hidden");
    avTimerMasquage = null;
  }, 150);
}

function cancelAvScan() {
  finAnalyse();
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "av_scan_cancel" }));
  }
}

avCloseBtn?.addEventListener("click", closeAntivirusPanel);
avCancelBtn?.addEventListener("click", () => {
  if (avScanInProgress) cancelAvScan();
  else closeAntivirusPanel();
});

// Protection en temps réel : enregistrée tout de suite (réglage partiel, cf. ws_reglages)
avLiveToggle?.addEventListener("change", () => {
  const actif = avLiveToggle.checked;
  const reglage = document.getElementById("settings-av-live") as HTMLInputElement | null;
  if (reglage) reglage.checked = actif;
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "update_settings", settings: { av_live_protection: actif } }));
  }
  journal(`[INFO] Protection en temps réel ${actif ? "activée" : "désactivée"}.`, actif ? "ok" : "");
});

// ── Messages du serveur ─────────────────────────────────────────────────────
export function handleAntivirusWSMessage(data: any) {
  if (data.type === "av_start") {
    journal(`[NOYAU] ${data.message || "Moteur antivirus démarré."}`);
  }

  else if (data.type === "av_progress") {
    if (data.percent !== undefined) progression(data.percent);
    if (data.step) etat(ETAPES[data.step] || "Analyse en cours", avThreatsList.length ? "threat-detected" : "");
    if (data.threats_found !== undefined) compterMenaces(data.threats_found);
    if (data.step === "files" && data.scanned !== undefined && avNbFichiers) {
      avNbFichiers.textContent = formatNombre(data.scanned);
    }
    if (data.message) {
      if (avCurrentFile) avCurrentFile.textContent = data.message;
      const prefixe = data.step === "registry" ? "[REGISTRE]" : data.step === "processes" ? "[PROCESSUS]" : "[FICHIER]";
      journal(`${prefixe} ${data.message}`);
    }
  }

  else if (data.type === "av_threat_detected" && data.threat) {
    avThreatsList.push(data.threat);
    etat("Menace détectée — analyse en cours", "threat-detected");
    journal(`[DANGER] ${data.threat.class} : ${data.threat.name} (${data.threat.desc || ""})`, "menace");
  }

  else if (data.type === "av_complete") {
    finAnalyse();
    progression(100);
    if (avCurrentFile) avCurrentFile.style.display = "none";
    if (data.status === "infected") {
      avThreatsList = data.threats || avThreatsList;
      avResolvedThreatsCount = 0;
      const n = avThreatsList.length;
      etat(`${n} menace${n > 1 ? "s" : ""} à traiter`, "threat-detected");
      compterMenaces(n);
      journal(`[TERMINÉ] Analyse terminée : ${n} menace${n > 1 ? "s" : ""} détectée${n > 1 ? "s" : ""}.`, "menace");
      renderThreatsList();
    } else if (data.status === "error") {
      etat("Erreur pendant l'analyse", "threat-detected");
      journal(`[ERREUR] ${data.message || "Une erreur est survenue pendant l'analyse."}`, "menace");
    } else {
      etat("Système sain : aucune menace", "etat-sain");
      journal("[TERMINÉ] Analyse terminée. Aucune menace détectée.", "ok");
    }
  }

  else if (data.type === "av_cancel") {
    finAnalyse();
    etat("Analyse interrompue");
    journal(`[INTERROMPU] ${data.message || "L'analyse a été annulée."}`);
  }

  else if (data.type === "av_action_result") {
    const idx = avThreatsList.findIndex(t => t.target === data.threat_target);
    const ligne = idx !== -1 ? document.getElementById(`av-threat-${idx}`) : null;
    if (data.success) {
      journal(`[RÉSOLU] ${String(data.action).toUpperCase()} : ${data.message}`, "ok");
      if (ligne && !ligne.classList.contains("resolved")) {
        ligne.classList.add("resolved");
        const libelles: Record<string, string> = { delete: "Supprimée", clean: "Nettoyée", quarantine: "En quarantaine", allow: "Autorisée" };
        const actions = ligne.querySelector(".pm-menace-actions");
        if (actions) actions.innerHTML = `<span class="av-threat-status-badge">✓ ${libelles[data.action] || "Résolue"}</span>`;
        avResolvedThreatsCount++;
        const restantes = avThreatsList.length - avResolvedThreatsCount;
        compterMenaces(restantes);
        if (restantes === 0) {
          etat("Système sain : toutes les menaces sont traitées", "etat-sain");
          journal("[SYSTÈME] Toutes les menaces ont été traitées.", "ok");
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
              type: "av_speak",
              text: "Toutes les menaces détectées ont été traitées. Votre système est sécurisé.",
            }));
          }
        } else {
          etat(`${restantes} menace${restantes > 1 ? "s" : ""} à traiter`, "threat-detected");
        }
      }
    } else {
      journal(`[ÉCHEC] ${String(data.action).toUpperCase()} sur ${data.threat_target} : ${data.message}`, "menace");
      ligne?.querySelectorAll<HTMLButtonElement>("button").forEach(b => { b.disabled = false; });
    }
  }
}

function renderThreatsList() {
  if (!avThreatsListEl) return;
  avThreatsListEl.classList.remove("hidden");
  if (avThreatsList.length === 0) {
    avThreatsListEl.innerHTML = '<div class="pm-vide pm-ok">AUCUNE MENACE ACTIVE</div>';
    return;
  }
  avThreatsListEl.innerHTML = avThreatsList.map((menace, idx) => `
    <div class="pm-ligne pm-menace" id="av-threat-${idx}">
      <div class="pm-icone">${icone("insecte")}</div>
      <div class="pm-texte">
        <div class="pm-nom" title="${esc(menace.target)}">${esc(menace.name)}</div>
        <div class="pm-detail" title="${esc(menace.target)}">${esc(menace.class)} · ${esc(String(menace.type || "").toLowerCase())}${menace.desc ? ` · ${esc(menace.desc)}` : ""}</div>
        <div class="pm-mono" style="padding:0;margin-top:2px">${esc(menace.target)}</div>
      </div>
      <div class="pm-menace-actions">
        <button class="pm-bouton discret petit" data-index="${idx}" data-action="allow">Autoriser</button>
        <button class="pm-bouton petit" data-index="${idx}" data-action="clean">Nettoyer</button>
        <button class="pm-bouton petit" data-index="${idx}" data-action="quarantine">Quarantaine</button>
        <button class="pm-bouton plein petit" data-index="${idx}" data-action="delete">Supprimer</button>
      </div>
    </div>`).join("");
  avThreatsListEl.querySelectorAll<HTMLButtonElement>("button[data-action]").forEach(btn => {
    btn.addEventListener("click", () => triggerAvThreatAction(btn.dataset.action || "", parseInt(btn.dataset.index || "0")));
  });
}

function triggerAvThreatAction(action: string, idx: number) {
  const menace = avThreatsList[idx];
  if (!menace) return;
  document.getElementById(`av-threat-${idx}`)?.querySelectorAll<HTMLButtonElement>("button")
    .forEach(b => { b.disabled = true; });
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "av_threat_action", action, threat: menace }));
  }
}


// Plus d'info sur l'antivirus (paramètres)
const settingsAvInfoBtn = document.getElementById("settings-av-info-btn") as HTMLAnchorElement;
const avInfoModal = document.getElementById("av-info-modal") as HTMLDivElement;
const avInfoModalClose = document.getElementById("av-info-modal-close") as HTMLSpanElement;
const avInfoModalOk = document.getElementById("av-info-modal-ok") as HTMLButtonElement;

if (settingsAvInfoBtn && avInfoModal) {
  settingsAvInfoBtn.addEventListener("click", (e) => {
    e.preventDefault();
    avInfoModal.style.display = "flex";
  });
}
avInfoModalClose?.addEventListener("click", () => { if (avInfoModal) avInfoModal.style.display = "none"; });
avInfoModalOk?.addEventListener("click", () => { if (avInfoModal) avInfoModal.style.display = "none"; });
