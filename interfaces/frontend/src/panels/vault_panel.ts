// ── COFFRE-FORT CHIFFRÉ : panneau du HUD (style verre : css/13 et css/14) ─────────────────
import { makePanelDraggable } from "../ui/draggable";
import { esc, formatTaille, icone } from "./pm_utils";

function socket(): WebSocket | null {
  const w = (window as any)._jarvisWs || (window as any).ws;
  return w && w.readyState === 1 ? w : null;
}

function ouvrirPanneau(panel: HTMLElement): void {
  panel.classList.remove("hidden");
  panel.classList.add("visible");
}

function fermerPanneau(panel: HTMLElement): void {
  panel.classList.remove("visible");
  panel.classList.add("hidden");
}

/** Message d'information en pied de panneau (remplace les alert() du navigateur). */
function informer(texte: string): void {
  const info = document.getElementById("vault-info");
  if (info) info.textContent = texte;
}

export function updateVoiceVaultUI(data: any) {
  const panel = document.getElementById("vault-panel");
  const lockedScreen = document.getElementById("vault-locked-screen");
  const unlockedScreen = document.getElementById("vault-unlocked-screen");
  const errorMsg = document.getElementById("vault-error-msg");
  const filesList = document.getElementById("vault-files-list");
  const sous = document.getElementById("vault-sous");

  if (data.force_open_hud && panel) ouvrirPanneau(panel);
  if (data.type === "vault_lock_result" && panel) fermerPanneau(panel);

  const isUnlocked = data.is_unlocked === true || data.success === true;
  const isConfigured = data.is_configured !== false;
  const lockTitle = document.getElementById("vault-lock-title");
  const unlockBtn = document.getElementById("vault-unlock-btn");

  if (lockTitle) {
    lockTitle.textContent = isConfigured
      ? "ENTREZ VOTRE CODE PIN OU MOT DE PASSE"
      : "CRÉEZ VOTRE MOT DE PASSE OU CODE PIN";
  }
  if (unlockBtn) unlockBtn.textContent = isConfigured ? "Déverrouiller" : "Créer le coffre";

  if (errorMsg) {
    errorMsg.textContent = data.type === "vault_unlock_result" && !data.success
      ? (data.message || "Mot de passe ou PIN incorrect.")
      : "";
  }
  if (sous) sous.textContent = `Chiffrement AES-256 · ${isUnlocked ? "déverrouillé" : "verrouillé"}`;

  if (isUnlocked) {
    if (lockedScreen) lockedScreen.style.display = "none";
    if (unlockedScreen) unlockedScreen.style.display = "flex";

    if (filesList && data.files) {
      if (data.files.length === 0) {
        filesList.innerHTML = '<div class="pm-vide">AUCUN FICHIER DANS LE COFFRE-FORT</div>';
      } else {
        filesList.innerHTML = data.files.map((file: any) => {
          const ext = String(file.filename).includes(".") ? String(file.filename).split(".").pop()!.slice(0, 4).toUpperCase() : "FIC";
          const taille = formatTaille(Math.max(1, Math.round(Number(file.size_kb) || 0)));
          return `
          <div class="pm-ligne">
            <div class="pm-avatar">${esc(ext)}</div>
            <div class="pm-texte">
              <div class="pm-nom">${esc(file.filename)}</div>
              <div class="pm-detail">${esc(taille)} · chiffré AES-256</div>
            </div>
            <div class="pm-droite" style="display:flex;gap:6px">
              <button class="pm-icone-bouton" data-action="exporter" data-fichier="${esc(file.filename)}" title="Exporter">${icone("telecharger")}</button>
              <button class="pm-icone-bouton" data-action="supprimer" data-fichier="${esc(file.filename)}" title="Supprimer">${icone("corbeille")}</button>
            </div>
          </div>`;
        }).join("");
      }
    }
  } else {
    if (lockedScreen) lockedScreen.style.display = "flex";
    if (unlockedScreen) unlockedScreen.style.display = "none";
  }
}

export function initVaultPanel(): void {
  const panel = document.getElementById("vault-panel");
  const header = document.getElementById("vault-panel-header");
  if (panel && header) makePanelDraggable(panel as HTMLDivElement, header as HTMLDivElement);
  document.getElementById("vault-panel-close-btn")?.addEventListener("click", () => panel && fermerPanneau(panel));

  const unlockBtn = document.getElementById("vault-unlock-btn");
  const lockBtn = document.getElementById("vault-lock-btn");
  const pinInput = document.getElementById("vault-pin-input") as HTMLInputElement | null;
  const addBtn = document.getElementById("vault-add-btn");
  const fileInput = document.getElementById("vault-file-input") as HTMLInputElement | null;
  const filesList = document.getElementById("vault-files-list");

  if (unlockBtn && pinInput) {
    const triggerUnlock = () => {
      const pin = pinInput.value.trim();
      const w = socket();
      if (pin && w) w.send(JSON.stringify({ type: "vault_unlock", password: pin }));
    };
    unlockBtn.onclick = triggerUnlock;
    pinInput.onkeyup = (e) => { if (e.key === "Enter") triggerUnlock(); };
  }

  if (lockBtn) {
    lockBtn.onclick = () => {
      socket()?.send(JSON.stringify({ type: "vault_lock" }));
    };
  }

  if (addBtn && fileInput) {
    addBtn.onclick = () => fileInput.click();
    fileInput.onchange = () => {
      if (fileInput.files && fileInput.files[0]) {
        const filePath = (fileInput.files[0] as any).path || fileInput.files[0].name;
        socket()?.send(JSON.stringify({ type: "vault_add_file", file_path: filePath }));
        fileInput.value = "";
      }
    };
  }

  // Exporter / supprimer : un seul écouteur pour toutes les lignes
  filesList?.addEventListener("click", (e) => {
    const bouton = (e.target as HTMLElement).closest<HTMLElement>("button[data-action]");
    if (!bouton) return;
    const filename = bouton.dataset.fichier || "";
    const w = socket();
    if (!filename || !w) return;
    if (bouton.dataset.action === "exporter") {
      w.send(JSON.stringify({ type: "vault_export_file", filename }));
      informer(`« ${filename} » a été déchiffré et exporté vers votre dossier Téléchargements.`);
    } else if (bouton.dataset.action === "supprimer") {
      // La confirmation est demandée par JARVIS (fenêtre + voix), pas par le navigateur.
      w.send(JSON.stringify({ type: "vault_delete_file", filename }));
    }
  });
}
