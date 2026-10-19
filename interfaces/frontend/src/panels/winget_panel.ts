// ── Panneau mises à jour winget (style commun css/13_panneaux_modules.css) ──
// Compteur dans l'en-tête, versions lisibles, état de chaque mise à jour sur sa ligne
// (le serveur indique l'identifiant du paquet dans chaque message), journal repliable.

import { wsRef } from "../ws_link";
import { makePanelDraggable } from "../ui/draggable";
import { closeUninstallerPanel } from "./uninstaller_panel";
import { esc, icone, initiales } from "./pm_utils";

// ── Winget Upgrade DOM Refs ────────────────────────────────────────────────
const wingetPanel = document.getElementById("winget-panel") as HTMLDivElement;
const wingetToggleBtn = document.getElementById("winget-toggle-btn") as HTMLButtonElement;
const wingetCloseBtn = document.getElementById("winget-panel-close-btn") as HTMLButtonElement;
const wingetHeader = document.getElementById("winget-panel-header") as HTMLDivElement;
const wingetSearchInput = document.getElementById("winget-search-input") as HTMLInputElement;
const wingetList = document.getElementById("winget-upgrades-list") as HTMLDivElement;
const wingetSelectAll = document.getElementById("winget-select-all") as HTMLInputElement;
const wingetRefreshBtn = document.getElementById("winget-refresh-btn") as HTMLButtonElement;
const wingetUpgradeSelectedBtn = document.getElementById("winget-upgrade-selected-btn") as HTMLButtonElement;
const wingetUpgradeAllBtn = document.getElementById("winget-upgrade-all-btn") as HTMLButtonElement;
const wingetJournal = document.getElementById("winget-logs-container") as HTMLDetailsElement;
const wingetConsole = document.getElementById("winget-console") as HTMLPreElement;
const wingetCountBadge = document.getElementById("winget-count-badge") as HTMLSpanElement;
const wingetResume = document.getElementById("winget-resume") as HTMLDivElement;
const wingetSelectionCompte = document.getElementById("winget-selection-compte") as HTMLSpanElement;

interface WingetUpgradeItem {
  name: string;
  id: string;
  version: string;
  available: string;
  source: string;
}

type EtatMaj = { etat: "attente" | "cours" | "ok" | "echec"; pct?: number };

let allWingetUpgrades: WingetUpgradeItem[] = [];
const etats = new Map<string, EtatMaj>();   // identifiant winget → état de sa mise à jour


// ── Ouverture / fermeture ───────────────────────────────────────────────────
if (wingetPanel && wingetHeader) {
  makePanelDraggable(wingetPanel, wingetHeader);
}

wingetCloseBtn?.addEventListener("click", () => closeWingetPanel());

wingetToggleBtn?.addEventListener("click", () => {
  if (wingetPanel.classList.contains("hidden")) openWingetPanel();
  else closeWingetPanel();
});

function synchroniserBoutonMenu(ouvert: boolean) {
  wingetToggleBtn?.setAttribute("aria-pressed", String(ouvert));
  wingetToggleBtn?.classList.toggle("active", ouvert);
}

function demanderListe() {
  if (wingetList) wingetList.innerHTML = '<div class="pm-vide">RECHERCHE DES MISES À JOUR…</div>';
  if (wingetResume) wingetResume.textContent = "Recherche des mises à jour…";
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "get_winget_upgrades" }));
  }
}

export function openWingetPanel() {
  if (!wingetPanel) return;
  wingetPanel.classList.remove("hidden");
  wingetPanel.classList.add("visible");
  synchroniserBoutonMenu(true);
  closeUninstallerPanel(); // vérifie l'existence du panneau en interne
  // Pas de nouvelle recherche pendant des mises à jour en cours : on garde leur état
  if (!miseAJourEnCours()) demanderListe();
}

export function closeWingetPanel() {
  if (!wingetPanel) return;
  wingetPanel.classList.add("hidden");
  wingetPanel.classList.remove("visible");
  synchroniserBoutonMenu(false);
}


// ── Liste ───────────────────────────────────────────────────────────────────
function miseAJourEnCours(): boolean {
  return [...etats.values()].some(e => e.etat === "attente" || e.etat === "cours");
}

function droiteLigne(item: WingetUpgradeItem): string {
  const e = etats.get(item.id);
  if (!e) {
    return `<span class="pm-version">${esc(item.version)}</span>
            <span style="color:var(--pm-gris);display:flex">${icone("fleche")}</span>
            <span class="pm-version nouvelle">${esc(item.available)}</span>`;
  }
  if (e.etat === "attente") return `<span class="pm-detail">En attente</span>`;
  if (e.etat === "cours") {
    const pct = e.pct;
    return `<div class="pm-barre ${pct === undefined ? "indeterminee" : ""}"><i style="width:${pct ?? 0}%"></i></div>`;
  }
  if (e.etat === "ok") return `<span class="pm-ok" style="display:flex">${icone("ok")}</span>`;
  return `<span class="pm-erreur" style="display:flex">${icone("erreur")}</span>`;
}

function detailLigne(item: WingetUpgradeItem): string {
  const e = etats.get(item.id);
  if (!e) return esc(item.id);
  if (e.etat === "attente") return "Mise à jour en attente";
  if (e.etat === "cours") return e.pct === undefined ? "Installation…" : `Installation… ${e.pct} %`;
  if (e.etat === "ok") return `<span class="pm-ok">À jour en ${esc(item.available)}</span>`;
  return `<span class="pm-erreur">Échec de la mise à jour (voir le journal)</span>`;
}

function renderWingetUpgrades() {
  if (!wingetList) return;
  const n = allWingetUpgrades.length;
  if (wingetCountBadge) {
    wingetCountBadge.textContent = String(n);
    wingetCountBadge.classList.toggle("hidden", n === 0);
  }
  if (wingetResume) {
    const heure = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    wingetResume.textContent = n
      ? `${n} mise${n > 1 ? "s" : ""} à jour disponible${n > 1 ? "s" : ""} · vérifié à ${heure}`
      : `Tout est à jour · vérifié à ${heure}`;
  }
  if (n === 0) {
    wingetList.innerHTML = '<div class="pm-vide">VOTRE SYSTÈME EST À JOUR</div>';
    mettreAJourSelection();
    return;
  }
  wingetList.innerHTML = allWingetUpgrades.map((item, idx) => `
    <div class="pm-ligne" data-id="${esc(item.id)}">
      <input type="checkbox" class="pm-case winget-select-checkbox" data-idx="${idx}" checked>
      <div class="pm-avatar">${esc(initiales(item.name))}</div>
      <div class="pm-texte">
        <div class="pm-nom" title="${esc(item.name)}">${esc(item.name)}</div>
        <div class="pm-detail">${detailLigne(item)}</div>
      </div>
      <div class="pm-droite" style="display:flex;align-items:center;gap:6px">${droiteLigne(item)}</div>
    </div>`).join("");
  wingetList.querySelectorAll<HTMLInputElement>(".winget-select-checkbox")
    .forEach(cb => cb.addEventListener("change", mettreAJourSelection));
  filtrer();
  mettreAJourSelection();
}

/** Met à jour une seule ligne (sans reconstruire la liste ni perdre les cases cochées). */
function rafraichirLigne(id: string) {
  const item = allWingetUpgrades.find(i => i.id === id);
  const ligne = wingetList?.querySelector<HTMLElement>(`.pm-ligne[data-id="${CSS.escape(id)}"]`);
  if (!item || !ligne) return;
  const detail = ligne.querySelector(".pm-detail");
  const droite = ligne.querySelector(".pm-droite");
  if (detail) detail.innerHTML = detailLigne(item);
  if (droite) droite.innerHTML = droiteLigne(item);
}

function idsSelectionnes(): string[] {
  const ids: string[] = [];
  wingetList?.querySelectorAll<HTMLInputElement>(".winget-select-checkbox").forEach(cb => {
    // Une ligne masquée par la recherche n'est pas mise à jour, même cochée
    const ligne = cb.closest(".pm-ligne") as HTMLElement | null;
    if (ligne && ligne.style.display === "none") return;
    const item = allWingetUpgrades[parseInt(cb.dataset.idx || "0")];
    if (cb.checked && item) ids.push(item.id);
  });
  return ids;
}

function mettreAJourSelection() {
  const n = idsSelectionnes().length;
  const occupe = miseAJourEnCours();
  if (wingetSelectionCompte) wingetSelectionCompte.textContent = n ? `${n} sélectionnée${n > 1 ? "s" : ""}` : "";
  if (wingetUpgradeSelectedBtn) {
    wingetUpgradeSelectedBtn.textContent = occupe ? "Mise à jour en cours…" : `Mettre à jour${n ? ` (${n})` : ""}`;
    wingetUpgradeSelectedBtn.disabled = occupe || n === 0;
  }
  if (wingetUpgradeAllBtn) wingetUpgradeAllBtn.disabled = occupe || allWingetUpgrades.length === 0;
}

function filtrer() {
  const q = (wingetSearchInput?.value || "").trim().toLowerCase();
  wingetList?.querySelectorAll<HTMLElement>(".pm-ligne").forEach(ligne => {
    ligne.style.display = (ligne.textContent || "").toLowerCase().includes(q) ? "" : "none";
  });
}

function runWingetUpgrade(ids: string[]) {
  if (ids.length === 0) return;
  ids.forEach((id, i) => etats.set(id, { etat: i === 0 ? "cours" : "attente" }));
  ids.forEach(rafraichirLigne);
  mettreAJourSelection();
  if (wingetConsole) {
    wingetConsole.textContent = `[JARVIS] Mise à jour de :\n- ${ids.join("\n- ")}\n\n`;
  }
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    // Par identifiants : le serveur les traite un par un et indique lequel est en cours,
    // d'où l'état affiché sur chaque ligne.
    wsRef.current.send(JSON.stringify({ type: "run_winget_upgrade", ids }));
  }
}

wingetSearchInput?.addEventListener("input", () => { filtrer(); mettreAJourSelection(); });

wingetSelectAll?.addEventListener("change", () => {
  wingetList?.querySelectorAll<HTMLInputElement>(".winget-select-checkbox")
    .forEach(cb => { cb.checked = wingetSelectAll.checked; });
  mettreAJourSelection();
});

wingetRefreshBtn?.addEventListener("click", () => {
  if (miseAJourEnCours()) return;
  etats.clear();
  demanderListe();
});

wingetUpgradeSelectedBtn?.addEventListener("click", () => runWingetUpgrade(idsSelectionnes()));

// « Tout » : une seule commande winget --all, donc une seule demande d'autorisation Windows
// (UAC) sans droits administrateur ; paquet par paquet, il en fallait une par logiciel.
// Le serveur n'indique alors pas le paquet en cours : toutes les lignes sont « en cours »
// puis passent ensemble à réussi / échec.
wingetUpgradeAllBtn?.addEventListener("click", () => {
  if (allWingetUpgrades.length === 0) return;
  allWingetUpgrades.forEach(i => etats.set(i.id, { etat: "cours" }));
  allWingetUpgrades.forEach(i => rafraichirLigne(i.id));
  mettreAJourSelection();
  if (wingetConsole) wingetConsole.textContent = "[JARVIS] Mise à jour de tous les logiciels (winget --all)…\n\n";
  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "run_winget_upgrade", all: true }));
  }
});


// ── API pour le dispatch WebSocket ──
export function handleWingetUpgrades(upgrades: WingetUpgradeItem[]) {
  allWingetUpgrades = upgrades || [];
  // On ne garde l'état que des logiciels encore listés
  [...etats.keys()].forEach(id => { if (!allWingetUpgrades.some(i => i.id === id)) etats.delete(id); });
  renderWingetUpgrades();
}

export function appendWingetProgress(progressData: any) {
  const id: string | undefined = progressData.id || undefined;
  if (progressData.status === "running") {
    if (wingetConsole) {
      wingetConsole.textContent += progressData.log || "";
      wingetConsole.scrollTop = wingetConsole.scrollHeight;
    }
    if (id) {
      // winget affiche parfois un pourcentage (droits administrateur) ; sinon barre animée
      const m = /(\d{1,3})\s?%/.exec(progressData.log || "");
      const precedent = etats.get(id);
      etats.set(id, { etat: "cours", pct: m ? Math.min(100, parseInt(m[1])) : precedent?.pct });
      rafraichirLigne(id);
    }
  } else if (progressData.status === "complete") {
    const ok = progressData.returncode === 0;
    if (wingetConsole) {
      wingetConsole.textContent += `\n[JARVIS] ${id || "Mise à jour"} : ${ok ? "terminée" : `échec (code ${progressData.returncode})`}.\n`;
      wingetConsole.scrollTop = wingetConsole.scrollHeight;
    }
    if (id) {
      etats.set(id, { etat: ok ? "ok" : "echec" });
      rafraichirLigne(id);
    } else {
      // Fin d'un « Tout » (winget --all) : même résultat pour toutes les lignes en cours
      etats.forEach((e, cle) => {
        if (e.etat === "cours" || e.etat === "attente") {
          etats.set(cle, { etat: ok ? "ok" : "echec" });
          rafraichirLigne(cle);
        }
      });
    }
    if (!ok && wingetJournal) wingetJournal.open = true;
    // Ligne suivante de la file : « en cours » dès maintenant (le serveur les enchaîne)
    const suivant = allWingetUpgrades.find(i => etats.get(i.id)?.etat === "attente");
    if (suivant) {
      etats.set(suivant.id, { etat: "cours" });
      rafraichirLigne(suivant.id);
    }
    mettreAJourSelection();
  }
}
