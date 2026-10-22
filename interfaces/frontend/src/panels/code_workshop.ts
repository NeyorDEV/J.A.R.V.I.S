import { SwarmLounge } from "../swarm_lounge";
import { wsRef } from "../ws_link";
import { swarmLoungeClose, swarmLoungeHud, swarmTerminalLogs } from "../hud/dom_refs";
import { type JarvisMessage } from "../ws/message_types";

// Command Center Swarm 3D, console Website Builder, flux de code en direct et
// éditeur de fichiers (extraits de main.ts).

let swarmLoungeInstance: SwarmLounge | null = null;

// Website Builder Console HUD DOM refs
const wbHud = document.getElementById("website-builder-hud") as HTMLDivElement;
const wbCloseBtn = document.getElementById("wb-close-btn") as HTMLButtonElement;
const wbStepBadge = document.getElementById("wb-step-badge") as HTMLSpanElement;
const wbStatusText = document.getElementById("wb-status-text") as HTMLSpanElement;
const wbImagesCount = document.getElementById("wb-images-count") as HTMLSpanElement;
const wbProgressPct = document.getElementById("wb-progress-pct") as HTMLSpanElement;
const wbProgressFill = document.getElementById("wb-progress-fill") as HTMLDivElement;
const wbTerminalLogs = document.getElementById("wb-terminal-logs") as HTMLDivElement;

export function initSwarmLounge(): void {
  window.addEventListener("DOMContentLoaded", () => {
    try {
      const canvasEl = document.getElementById("swarm-lounge-canvas") as HTMLCanvasElement;
      if (canvasEl) {
        swarmLoungeInstance = new SwarmLounge("swarm-lounge-canvas");
        swarmLoungeInstance.start();
        (window as any).swarmLounge = swarmLoungeInstance;
      }
    } catch (e) {
      console.warn("Could not init SwarmLounge 3D Canvas:", e);
    }
  });

  swarmLoungeClose?.addEventListener("click", () => {
    swarmLoungeHud?.classList.add("hidden");
    if (swarmLoungeHud) swarmLoungeHud.style.display = "none";
  });
}

export function initWebsiteBuilderHud(): void {
  wbCloseBtn?.addEventListener("click", () => {
    wbHud?.classList.add("hidden");
    if (wbHud) wbHud.style.display = "none";
  });

  const wbBrowseBtn = document.getElementById("wb-browse-btn");
  if (wbBrowseBtn) {
    wbBrowseBtn.addEventListener("click", () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "select_folder" }));
      }
    });
  }
}

function getFileBadgeHTML(filename: string): string {
  if (!filename || typeof filename !== "string") return '<span class="file-icon-tag default">FILE</span>';
  const clean = filename.toLowerCase();
  if (clean.endsWith(".html")) {
    return '<span class="file-icon-tag html"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> HTML</span>';
  }
  if (clean.endsWith(".css")) {
    return '<span class="file-icon-tag css"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2l9 4.9v10.2L12 22l-9-4.9V6.9L12 2z"/></svg> CSS</span>';
  }
    if (clean.endsWith(".js")) {
    return '<span class="file-icon-tag js"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> JS</span>';
  }
  return '<span class="file-icon-tag default"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/></svg> FILE</span>';
}

// Les deux variables ci-dessous sont recréées à CHAQUE message, comme dans
// l'ancien gestionnaire de main.ts où elles étaient déclarées.
export function handleCodeWorkshopMessage(data: JarvisMessage): boolean {
  const _projectWrittenCode: Record<string, string> = {};
  let _activeStreamFile: string = "";

  function updateLiveCodeStream(fileName?: string, codeContent?: string) {
    const tabsContainer = document.getElementById("swarm-code-tabs");
    const codeContentEl = document.getElementById("swarm-code-content");
    const codeGutterEl = document.getElementById("swarm-code-gutter");

    if (fileName) {
      if (codeContent) {
        _projectWrittenCode[fileName] = codeContent;
      }
      _activeStreamFile = fileName;
    }

    const targetFile = fileName || _activeStreamFile;

    if (tabsContainer) {
      tabsContainer.innerHTML = "";
      const fileKeys = Object.keys(_projectWrittenCode);
      if (fileKeys.length === 0 && targetFile) fileKeys.push(targetFile);

      fileKeys.forEach((fKey) => {
        const tabBtn = document.createElement("button");
        tabBtn.className = `swarm-code-tab ${fKey === targetFile ? "active" : ""}`;
        tabBtn.innerHTML = `${getFileBadgeHTML(fKey)} ${fKey}`;
        tabBtn.style.cursor = "pointer";
        tabBtn.onclick = (e) => {
          e.stopPropagation();
          _activeStreamFile = fKey;
          updateLiveCodeStream(fKey, _projectWrittenCode[fKey]);
        };
        tabsContainer.appendChild(tabBtn);
      });
    }
      const displayCode = (targetFile && _projectWrittenCode[targetFile]) || codeContent || "";
    if (codeContentEl) {
      codeContentEl.textContent = displayCode;

      if (codeGutterEl) {
        const lines = displayCode.split('\n');
        codeGutterEl.innerHTML = lines.map((_, i) => `<span class="ln">${i + 1}</span>`).join('');
      }

      codeContentEl.scrollTop = codeContentEl.scrollHeight;
      if (codeGutterEl) codeGutterEl.scrollTop = codeContentEl.scrollTop;

      codeContentEl.onscroll = () => {
        if (codeGutterEl) codeGutterEl.scrollTop = codeContentEl.scrollTop;
      };
    }
  }

  // ── Autonomous Dev Swarm Command Center HUD (Full 3D & 6-Agents) ──
  if (data.action === "dev_swarm_update") {
    const swarmData = data as any;

    // 1. Ouvrir le grand Command Center 3D Swarm Modal
    if (swarmLoungeHud) {
      swarmLoungeHud.classList.remove("hidden");
      swarmLoungeHud.style.display = "flex";
    }

    // 2. Mettre à jour l'état de la scène 3D Three.js
    if (swarmLoungeInstance) {
      swarmLoungeInstance.updateSwarmStatus(
        swarmData.agent || null,
        swarmData.status || 'in_progress',
        swarmData.message || '',
        swarmData.project || ''
      );
    }
            // 3. Mettre à jour les 6 cartes d'agents du volet latéral
    const currentRole = (swarmData.agent || '').toLowerCase();
    const rolesOrder = ['pm', 'ui', 'dev', 'sec', 'qa', 'ops'];
    const currentIndex = rolesOrder.indexOf(currentRole);

    rolesOrder.forEach((r, idx) => {
      const cardEl = document.getElementById(`card-agent-${r}`);
      const statusBadge = document.getElementById(`status-${r}`);
      const msgEl = document.getElementById(`msg-${r}`);

      if (cardEl && statusBadge && msgEl) {
        if (swarmData.status === 'success') {
          cardEl.classList.remove("active");
          statusBadge.className = "card-status-badge success";
          statusBadge.textContent = "SUCCÈS";
        } else if (r === currentRole) {
          cardEl.classList.add("active");
          statusBadge.className = "card-status-badge active";
          statusBadge.textContent = "ACTION";
          if (swarmData.message) msgEl.textContent = swarmData.message;
        } else if (idx < currentIndex) {
          cardEl.classList.remove("active");
          statusBadge.className = "card-status-badge success";
          statusBadge.textContent = "VALIDÉ";
        } else {
          cardEl.classList.remove("active");
          statusBadge.className = "card-status-badge idle";
          statusBadge.textContent = "EN ATTENTE";
        }
      }
    });

    // 4. Mettre à jour le visualiseur de code en direct (Live Stream IDE)
    if (swarmData.current_file) {
      _activeStreamFile = swarmData.current_file;
      updateLiveCodeStream(swarmData.current_file, swarmData.current_code || _projectWrittenCode[swarmData.current_file]);
    }

    // 5. Ajouter une ligne de log au terminal du Command Center
    if (swarmTerminalLogs && (swarmData.log || swarmData.message)) {
                const logEntry = document.createElement("div");
      logEntry.className = "swarm-log-line";
      const timestamp = new Date().toLocaleTimeString();
      logEntry.textContent = `[${timestamp}] [${swarmData.agent || 'SYS'}] ${swarmData.message || swarmData.log}`;
      swarmTerminalLogs.appendChild(logEntry);
      swarmTerminalLogs.scrollTop = swarmTerminalLogs.scrollHeight;
    }

    return true;
  }

  // ── Website Builder Console HUD Event ──
  if (data.action === "website_builder_update") {
    const wbData = data as any;
    if (wbHud) {
      wbHud.classList.remove("hidden");
      wbHud.style.display = "block";
    }
    if (wbStepBadge && wbData.step_label) {
      wbStepBadge.textContent = wbData.step_label;
    }
    if (wbStatusText && wbData.message) {
      wbStatusText.textContent = wbData.message;
    }
    const wbFilesCount = document.getElementById("wb-files-count");
    if (wbFilesCount && wbData.files_count) {
      wbFilesCount.textContent = `${wbData.files_count.generated} / ${wbData.files_count.total}`;
    }
            if (wbImagesCount && wbData.images_count) {
      const imgGen = wbData.images_count.generated !== undefined ? wbData.images_count.generated : 0;
      const imgTot = wbData.images_count.total !== undefined ? wbData.images_count.total : 0;
      wbImagesCount.textContent = `${imgGen} / ${imgTot}`;
    }
    if (wbProgressPct) {
      wbProgressPct.textContent = `${wbData.progress || 0}%`;
    }
    if (wbProgressFill) {
      wbProgressFill.style.width = `${wbData.progress || 0}%`;
    }
    const filesContainer = document.getElementById("wb-files-list-container");
    if (filesContainer && wbData.files_list && Array.isArray(wbData.files_list)) {
      filesContainer.innerHTML = "";
      wbData.files_list.forEach((fItem: any) => {
        const filePath = typeof fItem === "string" ? fItem : (fItem.file_path || fItem.name || String(fItem));
        const btn = document.createElement("button");
        btn.className = "wb-file-btn";
        btn.innerHTML = `${getFileBadgeHTML(filePath)}<span>${filePath}</span>`;
        btn.title = `Cliquer pour éditer / voir ${filePath}`;
        btn.onclick = (e) => {
          e.stopPropagation();
          openCodeEditorModal(filePath, wbData.project_name);
        };
        filesContainer.appendChild(btn);
      });
    }
    if (wbTerminalLogs && wbData.logs && Array.isArray(wbData.logs)) {
      wbTerminalLogs.innerHTML = "";
      wbData.logs.forEach((logStr: string) => {
        const entry = document.createElement("div");
        entry.className = "wb-log-entry";
        if (logStr.includes("IMAGE IA")) entry.classList.add("image");
        else if (logStr.includes("CODE ENGINE")) entry.classList.add("code");
        else if (logStr.includes("succès") || logStr.includes("RÉUSSI")) entry.classList.add("success");

        const fileMatch = logStr.match(/([\w\-\\./]+\.(?:html|css|js|json))/i);
        if (fileMatch) {
          const matchedFile = fileMatch[1];
          const parts = logStr.split(matchedFile);
          entry.appendChild(document.createTextNode(parts[0]));
          
          const fileLink = document.createElement("span");
          fileLink.className = "file-click-link";
          fileLink.textContent = matchedFile;
          fileLink.title = "Cliquer pour ouvrir et éditer ce fichier";
                        fileLink.onclick = (e) => {
            e.stopPropagation();
            openCodeEditorModal(matchedFile, wbData.project_name);
          };
          entry.appendChild(fileLink);
          entry.appendChild(document.createTextNode(parts.slice(1).join(matchedFile)));
        } else {
          entry.textContent = logStr;
        }
        wbTerminalLogs.appendChild(entry);
      });
      wbTerminalLogs.scrollTop = wbTerminalLogs.scrollHeight;
    }
    if (wbData.status === "success" || wbData.status === "failure") {
      setTimeout(() => {
        wbHud?.classList.add("hidden");
        if (wbHud) wbHud.style.display = "none";
      }, 14000);
    }
    return true;
  }
  return false;
}

export function openCodeEditorModal(filePath: string, projectName?: string) {
  const modal = document.getElementById("code-editor-modal");
  const filenameEl = document.getElementById("code-editor-filename");
  const filepathEl = document.getElementById("code-editor-filepath");
  const textarea = document.getElementById("code-editor-textarea") as HTMLTextAreaElement;
  const closeBtn = document.getElementById("close-code-editor");
  const saveBtn = document.getElementById("save-code-btn");
  const previewBtn = document.getElementById("preview-code-btn");

  if (!modal || !textarea) return;

  modal.classList.remove("hidden");
  modal.style.display = "flex";

  const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
  const customFolder = folderInput?.value.trim() || "";
    let fullPath = filePath;
  if (!filePath.includes(":") && !filePath.startsWith("/")) {
    if (customFolder) {
      fullPath = `${customFolder}\\${filePath}`;
    } else {
      const proj = projectName || "apexmind_studio_saas";
      fullPath = `backend\\sandbox\\${proj}\\${filePath}`; // relatif à la racine du projet : le backend le résout
    }
  }

  if (filenameEl) filenameEl.textContent = `JARVIS // ÉDITEUR (${filePath})`;
  if (filepathEl) filepathEl.textContent = `Fichier : ${fullPath}`;

  textarea.value = `// Chargement de ${filePath} depuis le disque...`;

  if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify({ type: "read_file", action: "read_file", filepath: fullPath }));
  }

  if (closeBtn) {
    closeBtn.onclick = () => {
      modal.classList.add("hidden");
      modal.style.display = "none";
    };
  }

  if (saveBtn) {
    saveBtn.onclick = () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: "write_file",
          action: "write_file",
          filepath: fullPath,
          content: textarea.value
        }));
      }
    };
  }
    if (previewBtn) {
    previewBtn.onclick = () => {
      // Chemin absolu renvoyé par le backend à la lecture du fichier (aperçu dans le navigateur)
      const cleanPath = String((window as any)._wbAbsolu || fullPath).replace(/\\/g, "/");
      window.open(`file:///${cleanPath}`, "_blank");
    };
  }
}
