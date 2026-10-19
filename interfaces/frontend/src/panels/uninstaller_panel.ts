// ── Panneau désinstallateur (style commun css/13_panneaux_modules.css) ──
// Liste triable (nom, taille, date), action au survol, désinstallation en trois étapes
// visibles (désinstallation → analyse des traces → nettoyage) dans un volet en bas.

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { closeWingetPanel } from "./winget_panel";
import { esc, formatDate, formatTaille, icone, initiales } from "./pm_utils";

// ── Uninstaller DOM Refs ───────────────────────────────────────────────────
const uninstallerPanel = document.getElementById("uninstaller-panel") as HTMLDivElement;
const uninstallerToggleBtn = document.getElementById("uninstaller-toggle-btn") as HTMLButtonElement;
const uninstallerCloseBtn = document.getElementById("uninstaller-panel-close-btn") as HTMLButtonElement;
const uninstallerHeader = document.getElementById("uninstaller-panel-header") as HTMLDivElement;
const uninstallerSearchInput = document.getElementById("uninstaller-search-input") as HTMLInputElement;
const uninstallerAppsList = document.getElementById("uninstaller-apps-list") as HTMLDivElement;
const uninstallerActionView = document.getElementById("uninstaller-action-view") as HTMLDivElement;
const uninstallerStatusMsg = document.getElementById("uninstaller-status-msg") as HTMLDivElement;
const uninstallerRadarContainer = document.getElementById("uninstaller-radar-container") as HTMLDivElement;
const uninstallerLeftoversContainer = document.getElementById("uninstaller-leftovers-container") as HTMLDivElement;
const uninstallerLeftoversList = document.getElementById("uninstaller-leftovers-list") as HTMLDivElement;
const uninstallerSelectAll = document.getElementById("uninstaller-select-all") as HTMLInputElement;
const uninstallerCleanBtn = document.getElementById("uninstaller-clean-btn") as HTMLButtonElement;
const uninstallerSkipBtn = document.getElementById("uninstaller-skip-btn") as HTMLButtonElement;
const uninstallerResume = document.getElementById("uninstaller-resume") as HTMLDivElement;
const uninstallerTracesTitre = document.getElementById("uninstaller-traces-titre") as HTMLSpanElement;
const uninstallerEtapes = document.getElementById("uninstaller-etapes") as HTMLDivElement;

interface Programme {
  name: string;
  subkey: string;
  publisher: string;
  version: string;
  uninstall_string: string;
  install_location: string;
  icon_path: string;
  hive: string;
  size_kb?: number;        // taille estimée (registre), 0 si inconnue
  install_date?: string;   // AAAAMMJJ (registre), "" si inconnue
}

let allInstalledPrograms: Programme[] = [];
let currentLeftovers: Array<{ type: string; path: string; desc: string; hive?: string }> = [];
let triActif: "nom" | "taille" | "date" = "nom";
let programmeEnCours: Programme | null = null;


// ── Ouverture / fermeture ───────────────────────────────────────────────────
if (uninstallerPanel && uninstallerHeader) {
  makePanelDraggable(uninstallerPanel, uninstallerHeader);
}

uninstallerCloseBtn?.addEventListener("click", () => closeUninstallerPanel());

uninstallerToggleBtn?.addEventListener("click", () => {
  if (uninstallerPanel.classList.contains("hidden")) openUninstallerPanel();
  else closeUninstallerPanel();
});

function synchroniserBoutonMenu(ouvert: boolean) {
  uninstallerToggleBtn?.setAttribute("aria-pressed", String(ouvert));
  const menuBtn = document.getElementById("menu-uninstaller-toggle-btn");
  if (menuBtn) {
    menuBtn.setAttribute("aria-pressed", String(ouvert));
    menuBtn.classList.toggle("active", ouvert);
  }
}

export function openUninstallerPanel() {
  if (!uninstallerPanel) return;
  uninstallerPanel.classList.remove("hidden");
  uninstallerPanel.classList.add("visible");
  synchroniserBoutonMenu(true);
  closeWingetPanel(); // vérifie l'existence du panneau en interne

  fermerVolet();
  programmeEnCours = null;
  if (uninstallerAppsList) {
    uninstallerAppsList.innerHTML = '<div class="pm-vide">CHARGEMENT DE LA LISTE DES LOGICIELS…</div>';
  }
  if (uninstallerResume) uninstallerResume.textContent = "Chargement des programmes…";
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "get_installed_programs" }));
  }
}

export function closeUninstallerPanel() {
  if (!uninstallerPanel) return;
  uninstallerPanel.classList.add("hidden");
  uninstallerPanel.classList.remove("visible");
  synchroniserBoutonMenu(false);
}


// ── Liste des programmes ────────────────────────────────────────────────────
function programmesAffiches(): Programme[] {
  const q = (uninstallerSearchInput?.value || "").trim().toLowerCase();
  let liste = allInstalledPrograms;
  if (q) {
    liste = liste.filter(p => p.name.toLowerCase().includes(q) || (p.publisher || "").toLowerCase().includes(q));
  }
  const triee = [...liste];
  if (triActif === "taille") triee.sort((a, b) => (b.size_kb || 0) - (a.size_kb || 0));
  else if (triActif === "date") triee.sort((a, b) => (b.install_date || "").localeCompare(a.install_date || ""));
  else triee.sort((a, b) => a.name.localeCompare(b.name, "fr", { sensitivity: "base" }));
  return triee;
}

function renderInstalledPrograms() {
  if (!uninstallerAppsList) return;
  const programmes = programmesAffiches();
  if (programmes.length === 0) {
    uninstallerAppsList.innerHTML = '<div class="pm-vide">AUCUN LOGICIEL TROUVÉ</div>';
    return;
  }
  uninstallerAppsList.innerHTML = "";
  const enCours = programmeEnCours !== null;
  programmes.forEach(prog => {
    const ligne = document.createElement("div");
    ligne.className = "pm-ligne";
    const taille = formatTaille(prog.size_kb || 0);
    const date = formatDate(prog.install_date || "");
    ligne.innerHTML = `
      <div class="pm-avatar">${esc(initiales(prog.name))}</div>
      <div class="pm-texte">
        <div class="pm-nom" title="${esc(prog.name)}">${esc(prog.name)}</div>
        <div class="pm-detail">${esc(prog.publisher || "Éditeur inconnu")}${prog.version ? ` · v${esc(prog.version)}` : ""}</div>
      </div>
      <div class="pm-droite">
        <div class="pm-taille">${taille || "—"}</div>
        <div class="pm-detail">${date ? `installé le ${date}` : "&nbsp;"}</div>
      </div>
      <button class="pm-bouton danger petit pm-action-survol" ${enCours ? "disabled" : ""}>Désinstaller</button>`;
    ligne.querySelector("button")?.addEventListener("click", () => triggerUninstall(prog));
    uninstallerAppsList.appendChild(ligne);
  });
}

function mettreAJourResume() {
  if (!uninstallerResume) return;
  const totalKo = allInstalledPrograms.reduce((s, p) => s + (p.size_kb || 0), 0);
  const n = allInstalledPrograms.length;
  uninstallerResume.textContent = `${n} programme${n > 1 ? "s" : ""}${totalKo ? ` · ${formatTaille(totalKo)}` : ""}`;
}

uninstallerSearchInput?.addEventListener("input", () => renderInstalledPrograms());

uninstallerPanel?.querySelectorAll<HTMLButtonElement>(".pm-pastille[data-tri]").forEach(btn => {
  btn.addEventListener("click", () => {
    triActif = (btn.dataset.tri as typeof triActif) || "nom";
    uninstallerPanel.querySelectorAll(".pm-pastille[data-tri]").forEach(b => b.classList.toggle("active", b === btn));
    renderInstalledPrograms();
  });
});


// ── Volet de désinstallation (étapes) ────────────────────────────────────────
function etapes(etat: Record<number, "faite" | "courante" | "echec" | "">) {
  uninstallerEtapes?.querySelectorAll<HTMLElement>(".pm-etape").forEach(el => {
    const n = Number(el.dataset.etape);
    el.className = `pm-etape ${etat[n] || ""}`.trim();
    const pastille = el.querySelector("b");
    if (pastille) pastille.textContent = etat[n] === "faite" ? "✓" : etat[n] === "echec" ? "!" : String(n);
  });
}

function fermerVolet() {
  uninstallerActionView?.classList.add("hidden");
  uninstallerLeftoversContainer?.classList.add("hidden");
  uninstallerRadarContainer?.classList.remove("hidden");
}

function triggerUninstall(prog: Programme) {
  programmeEnCours = prog;
  renderInstalledPrograms();   // boutons désactivés pendant l'opération
  uninstallerActionView?.classList.remove("hidden");
  uninstallerRadarContainer?.classList.remove("hidden");
  uninstallerLeftoversContainer?.classList.add("hidden");
  etapes({ 1: "courante" });
  if (uninstallerStatusMsg) uninstallerStatusMsg.textContent = `Désinstallation de ${prog.name}…`;

  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({
      type: "uninstall_program",
      name: prog.name,
      publisher: prog.publisher,
      install_location: prog.install_location,
      uninstall_string: prog.uninstall_string,
    }));
  }
}

export function updateUninstallProgress(data: any) {
  if (uninstallerStatusMsg) uninstallerStatusMsg.textContent = data.message || "En cours…";
  // Le serveur passe à la recherche de traces après la désinstallation
  if (/trace|résidu|residu|analyse/i.test(data.message || "")) etapes({ 1: "faite", 2: "courante" });
}

export function showUninstallComplete(data: any) {
  uninstallerRadarContainer?.classList.add("hidden");
  uninstallerLeftoversContainer?.classList.remove("hidden");
  currentLeftovers = data.leftovers || [];
  if (uninstallerSelectAll) uninstallerSelectAll.checked = true;

  // Désinstallation annulée ou ratée : on le dit, au lieu de « aucune trace résiduelle »
  const echec = data.success === false
    ? (data.cancelled ? "Désinstallation annulée." : (data.message || "La désinstallation n'a pas abouti."))
    : null;
  if (echec) etapes({ 1: "echec" });
  else if (currentLeftovers.length) etapes({ 1: "faite", 2: "faite", 3: "courante" });
  else etapes({ 1: "faite", 2: "faite", 3: "faite" });
  renderLeftovers(echec);
}

function afficherToutSelectionner(visible: boolean) {
  const label = uninstallerSelectAll?.closest("label") as HTMLElement | null;
  if (label) label.style.display = visible ? "" : "none";
}

function renderLeftovers(messageVide: string | null = null) {
  if (!uninstallerLeftoversList) return;
  const nom = programmeEnCours?.name || "le programme";
  afficherToutSelectionner(currentLeftovers.length > 0);
  if (currentLeftovers.length === 0) {
    uninstallerLeftoversList.innerHTML =
      `<div class="pm-detail" style="padding:6px 0">${esc(messageVide || `${nom} est désinstallé, sans trace résiduelle.`)}</div>`;
    if (uninstallerTracesTitre) uninstallerTracesTitre.textContent = messageVide ? "Désinstallation" : "Terminé";
    if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = true;
    if (uninstallerSkipBtn) uninstallerSkipBtn.textContent = "Fermer";
    return;
  }
  if (uninstallerTracesTitre) {
    uninstallerTracesTitre.textContent = `${currentLeftovers.length} trace${currentLeftovers.length > 1 ? "s" : ""} résiduelle${currentLeftovers.length > 1 ? "s" : ""} de ${nom}`;
  }
  if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = false;
  if (uninstallerSkipBtn) uninstallerSkipBtn.textContent = "Garder et fermer";
  uninstallerLeftoversList.innerHTML = currentLeftovers.map((t, idx) => `
    <label class="pm-trace">
      <input type="checkbox" class="pm-case uninstaller-leftover-checkbox" data-idx="${idx}" checked>
      ${icone(t.type === "folder" ? "dossier" : "registre")}
      <div class="pm-texte">
        <div class="pm-nom" title="${esc(t.path)}">${esc(t.path)}</div>
        <div class="pm-detail">${t.type === "folder" ? "Dossier" : "Registre"} · ${esc(t.desc)}</div>
      </div>
    </label>`).join("");
}

export function showCleanComplete(data: any) {
  const nettoyees = data.cleaned_count || 0;
  const total = data.total_count || 0;
  etapes({ 1: "faite", 2: "faite", 3: nettoyees === total ? "faite" : "echec" });
  afficherToutSelectionner(false);
  if (uninstallerTracesTitre) uninstallerTracesTitre.textContent = "Nettoyage terminé";
  if (uninstallerLeftoversList) {
    uninstallerLeftoversList.innerHTML =
      `<div class="pm-detail" style="padding:6px 0">${nettoyees}/${total} trace${total > 1 ? "s" : ""} supprimée${nettoyees > 1 ? "s" : ""}.</div>`;
  }
  if (uninstallerCleanBtn) uninstallerCleanBtn.disabled = true;
  if (uninstallerSkipBtn) uninstallerSkipBtn.textContent = "Fermer";
}

uninstallerSelectAll?.addEventListener("change", () => {
  document.querySelectorAll<HTMLInputElement>(".uninstaller-leftover-checkbox")
    .forEach(cb => { cb.checked = uninstallerSelectAll.checked; });
});

uninstallerCleanBtn?.addEventListener("click", () => {
  const selection: any[] = [];
  document.querySelectorAll<HTMLInputElement>(".uninstaller-leftover-checkbox").forEach(cb => {
    if (cb.checked) selection.push(currentLeftovers[parseInt(cb.dataset.idx || "0")]);
  });
  if (selection.length === 0) {
    if (uninstallerTracesTitre) uninstallerTracesTitre.textContent = "Sélectionnez au moins une trace à nettoyer.";
    return;
  }
  uninstallerCleanBtn.disabled = true;
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "clean_leftovers", items: selection }));
  }
});

// « Garder et fermer » / « Fermer » : retour à la liste, rafraîchie
uninstallerSkipBtn?.addEventListener("click", () => openUninstallerPanel());


// ── API pour le dispatch WebSocket ──
export function handleInstalledPrograms(programs: Programme[]) {
  allInstalledPrograms = programs || [];
  mettreAJourResume();
  renderInstalledPrograms();
}
