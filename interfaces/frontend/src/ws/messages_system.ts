import { cardManager } from "../cards";
import { handleAntivirusWSMessage, openAntivirusPanel } from "../panels/antivirus_panel";
import { showImagePanel } from "../panels/image_panels";
import { handleInstalledPrograms, openUninstallerPanel, showCleanComplete, showUninstallComplete, updateUninstallProgress } from "../panels/uninstaller_panel";
import { appendWingetProgress, handleWingetUpgrades, openWingetPanel } from "../panels/winget_panel";
import { type JarvisMessage } from "./message_types";

// Messages backend : autopilote OS, explorateur, images, antivirus,
// désinstallateur, winget, fichiers (extrait du gestionnaire de main.ts).
// La capture d'écran, seule branche asynchrone, est restée dans wsRef.current/connection.ts.

export function handleAutopilotMessage(data: JarvisMessage): boolean {
  // ── OS Autopilot & Virtual Cursor ──
  if (data.action === "draw_virtual_cursor" && (data as any).x !== undefined && (data as any).y !== undefined) {
    const cursor = document.getElementById("virtual-cursor");
    if (cursor) {
      const wasHidden = cursor.style.display === "none";
      const animDuration = data.duration || 0.8;
      
      // Injecter la durée de transition dynamique
      cursor.style.transition = `left ${animDuration}s cubic-bezier(0.25, 0.8, 0.25, 1), top ${animDuration}s cubic-bezier(0.25, 0.8, 0.25, 1), transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1.275)`;
                if (wasHidden) {
        // Positionner initialement au centre pour un premier déplacement fluide
        cursor.style.left = "50%";
        cursor.style.top = "50%";
        cursor.style.display = "block";
        
        // Attendre deux ticks du moteur de rendu pour appliquer le display: block
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            cursor.style.left = `${(data as any).x}%`;
            cursor.style.top = `${(data as any).y}%`;
          });
        });
      } else {
        cursor.style.left = `${(data as any).x}%`;
        cursor.style.top = `${(data as any).y}%`;
      }
      
      const duration = animDuration * 1000;
      
      // Nettoyer les anciens timeouts de clic et de masquage
      if ((cursor as any).vcClickTimeout) clearTimeout((cursor as any).vcClickTimeout);
      if ((cursor as any).vcHideTimeout) clearTimeout((cursor as any).vcHideTimeout);
      
      (cursor as any).vcClickTimeout = setTimeout(() => {
        cursor.classList.add("clicking");
        
        const wave = document.createElement("div");
        wave.className = "vc-click-wave";
        cursor.appendChild(wave);
        
        setTimeout(() => {
          cursor.classList.remove("clicking");
          wave.remove();
        }, 600);
      }, duration);
      
      // Masquer le curseur après 3 secondes d'inactivité
      (cursor as any).vcHideTimeout = setTimeout(() => {
        cursor.style.display = "none";
      }, duration + 3000);
    }
    return true;
          }

  if (data.action === "os_agent_status") {
    const banner = document.getElementById("os-autopilot-banner");
    const logEl = document.getElementById("os-autopilot-log");
    if (banner && logEl) {
      if ((data as any).active) {
        banner.style.display = "flex";
        logEl.textContent = (data as any).log || "[JARVIS OS AUTOPILOT] ACTIF";
      } else {
        banner.style.display = "none";
        // Cacher le curseur virtuel quand l'autopilote est terminé
        const cursor = document.getElementById("virtual-cursor");
        if (cursor) {
          if ((cursor as any).vcHideTimeout) clearTimeout((cursor as any).vcHideTimeout);
          cursor.style.display = "none";
        }
      }
    }
    return true;
  }
  return false;
}

export function handleSystemMessage(data: JarvisMessage): boolean {
  // ── Spatial File Explorer 3D ──
  if (data.type === "spatial_result") {
    const explorer = (window as any)._spatialExplorer;
    if (explorer) explorer.handleServerResponse(data);
    return true;
  }
        // ── Image Search ──
  if (data.type === "show_images") {
    showImagePanel((data as any).query || "IMAGE_SCAN", (data as any).images || []);
    return true;
  }

  // ── Antivirus WS Messages ──
  if (data.type === "av_open") {
    openAntivirusPanel();
    return true;
  }

  if (data.type === "av_start" || data.type === "av_progress" || data.type === "av_threat_detected" || data.type === "av_complete" || data.type === "av_cancel" || data.type === "av_action_result") {
    handleAntivirusWSMessage(data);
    return true;
  }

  // Messages que le HUD ignorait : alerte de la protection temps réel, résultat de
  // l'export du coffre-fort, vidage du cache WebView.
  if (data.type === "av_live_threat_intercepted") {
    const menace = (data as any).threat || {};
    cardManager.showCard({
      title: "PROTECTION TEMPS RÉEL",
      content: `${menace.name || "Élément inconnu"} — ${menace.desc || ""}`,
      type: "alert" as any,
      duration: 15000,
      icon: "🛡",
    });
    return true;
  }
  if (data.type === "vault_export_result") {
    const ok = (data as any).success;
    cardManager.showCard({
      title: "COFFRE-FORT",
      content: ok ? `Fichier exporté : ${(data as any).path}` : `Impossible d'exporter ${(data as any).filename || "le fichier"}.`,
      type: (ok ? "info" : "alert") as any,
      duration: 8000,
      icon: "🔐",
    });
    return true;
  }
  if (data.type === "cache_cleared") {
    cardManager.showCard({
      title: "CACHE",
      content: (data as any).success ? "Cache de l'interface vidé, rechargement…" : "Le cache n'a pas pu être vidé.",
      type: ((data as any).success ? "info" : "alert") as any,
      duration: 5000,
      icon: "🧹",
    });
    return true;
  }

  // ── Uninstaller WS Messages ──
  if (data.action === "uninstaller_open" || data.type === "uninstaller_open") {
    openUninstallerPanel();
    return true;
  }

  if (data.type === "installed_programs" && (data as any).programs) {
    handleInstalledPrograms((data as any).programs);
    return true;
  }

  if (data.type === "uninstall_progress") {
    updateUninstallProgress(data);
    return true;
  }

  if (data.type === "uninstall_complete") {
    showUninstallComplete(data);
    return true;
  }

  if (data.type === "clean_complete") {
    showCleanComplete(data);
    return true;
  }
        // ── Winget WS Messages ──
  if (data.action === "winget_open" || data.type === "winget_open") {
    openWingetPanel();
    return true;
  }

  if (data.type === "winget_upgrades" && (data as any).upgrades) {
    handleWingetUpgrades((data as any).upgrades);
    return true;
  }

  if (data.type === "winget_upgrade_progress") {
    appendWingetProgress(data as any);
    return true;
  }


  // ── WS File Inspector Read/Write Events ──
  if (data.type === "file_content" || data.action === "file_content") {
    const fileData = data as any;
    const textarea = document.getElementById("code-editor-textarea") as HTMLTextAreaElement;
    const filepathEl = document.getElementById("code-editor-filepath");
    if (textarea && fileData.filepath) {
      textarea.value = fileData.content || (fileData.error ? `// Erreur : ${fileData.error}` : "");
    }
    if (filepathEl && fileData.filepath) {
      filepathEl.textContent = `Fichier : ${fileData.filepath}`;
    }
    return true;
  }
        if (data.type === "file_saved" || data.action === "file_saved") {
    const fileData = data as any;
    const saveBtn = document.getElementById("save-code-btn");
    if (saveBtn) {
      const oldText = saveBtn.textContent;
      saveBtn.textContent = fileData.success ? "✅ Sauvegardé !" : "❌ Échec !";
      setTimeout(() => { saveBtn.textContent = oldText; }, 2000);
    }
    return true;
  }

  if (data.type === "folder_selected") {
    const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
    if (folderInput && (data as any).folder) {
      folderInput.value = (data as any).folder;
    }
    return true;
  }
  return false;
}
