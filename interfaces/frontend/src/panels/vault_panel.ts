// ── VOICE VAULT UI LOGIC ──────────────────────────────────────────────────────
export function updateVoiceVaultUI(data: any) {
  const panel = document.getElementById("vault-panel");
  const lockedScreen = document.getElementById("vault-locked-screen");
  const unlockedScreen = document.getElementById("vault-unlocked-screen");
  const errorMsg = document.getElementById("vault-error-msg");
  const filesList = document.getElementById("vault-files-list");

  if (data.force_open_hud && panel) {
    panel.classList.remove("hidden");
    panel.classList.add("visible");
    panel.style.setProperty("display", "flex", "important");
  }

  if (data.type === "vault_lock_result" && panel) {
    panel.classList.remove("visible");
    panel.classList.add("hidden");
    panel.style.setProperty("display", "none", "important");
  }

  const isUnlocked = data.is_unlocked === true || data.success === true;
  const isConfigured = data.is_configured !== false;
  const lockTitle = document.getElementById("vault-lock-title");
  const unlockBtn = document.getElementById("vault-unlock-btn");

  if (lockTitle) {
    lockTitle.textContent = isConfigured
      ? "ENTREZ VOTRE CODE PIN OU MOT DE PASSE"
      : "INITIALISATION : CRÉEZ VOTRE MOT DE PASSE OU CODE PIN";
  }

  if (unlockBtn) {
    unlockBtn.textContent = isConfigured ? "DÉVERROUILLER" : "CRÉER LE COFFRE";
  }

  if (errorMsg) {
    if (data.type === "vault_unlock_result" && !data.success) {
      errorMsg.textContent = "❌ " + (data.message || "Mot de passe ou PIN incorrect.");
    } else {
      errorMsg.textContent = "";
    }
  }

  if (isUnlocked) {
    if (lockedScreen) lockedScreen.style.display = "none";
    if (unlockedScreen) unlockedScreen.style.display = "flex";

    if (filesList && data.files) {
      if (data.files.length === 0) {
        filesList.innerHTML = '<div style="font-size: 10px; color: rgba(255, 255, 255, 0.4); text-align: center; padding: 20px;">Aucun fichier dans le coffre-fort.</div>';
      } else {
        filesList.innerHTML = data.files.map((file: any) => `
          <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.15); padding: 8px 12px; border-radius: 6px; margin-bottom: 6px;">
            <div>
              <div style="font-size: 11px; font-weight: bold; color: #fff;">📄 ${file.filename}</div>
              <div style="font-size: 9px; color: rgba(0, 229, 255, 0.6);">${file.size_kb} KB · Crypté AES-256</div>
            </div>
            <div style="display: flex; gap: 6px;">
              <button onclick="window.exportVaultFile('${file.filename}')" style="background: rgba(0, 229, 255, 0.15); border: 1px solid #00e5ff; color: #00e5ff; padding: 4px 8px; border-radius: 4px; font-size: 9px; cursor: pointer;">📥 EXPORTER</button>
              <button onclick="window.deleteVaultFile('${file.filename}')" style="background: rgba(255, 51, 102, 0.15); border: 1px solid #ff3366; color: #ff3366; padding: 4px 8px; border-radius: 4px; font-size: 9px; cursor: pointer;">🗑️</button>
            </div>
          </div>
        `).join('');
      }
    }
  } else {
    if (lockedScreen) lockedScreen.style.display = "flex";
    if (unlockedScreen) unlockedScreen.style.display = "none";
  }
}

export function initVaultPanel(): void {
  (window as any).exportVaultFile = (filename: string) => {
    const wsInst = (window as any)._jarvisWs || (window as any).ws;
    if (wsInst && wsInst.readyState === 1) {
      wsInst.send(JSON.stringify({ type: "vault_export_file", filename }));
      alert(`Fichier "${filename}" déchiffré et exporté vers votre dossier Téléchargements !`);
    }
  };

  (window as any).deleteVaultFile = (filename: string) => {
    const wsInst = (window as any)._jarvisWs || (window as any).ws;
    // La confirmation est demandée par JARVIS (popup + voix) : le confirm() du navigateur
    // faisait demander deux fois la même chose.
    if (wsInst && wsInst.readyState === 1) {
      wsInst.send(JSON.stringify({ type: "vault_delete_file", filename }));
    }
  };

  // Listeners Vault
  setTimeout(() => {
    const unlockBtn = document.getElementById("vault-unlock-btn");
    const lockBtn = document.getElementById("vault-lock-btn");
    const pinInput = document.getElementById("vault-pin-input") as HTMLInputElement | null;
    const addBtn = document.getElementById("vault-add-btn");
    const fileInput = document.getElementById("vault-file-input") as HTMLInputElement | null;

    if (unlockBtn && pinInput) {
      const triggerUnlock = () => {
        const pin = pinInput.value.trim();
        const wsInst = (window as any)._jarvisWs || (window as any).ws;
        if (pin && wsInst && wsInst.readyState === 1) {
          wsInst.send(JSON.stringify({ type: "vault_unlock", password: pin }));
        }
      };
      unlockBtn.onclick = triggerUnlock;
      pinInput.onkeyup = (e) => { if (e.key === "Enter") triggerUnlock(); };
    }

    if (lockBtn) {
      lockBtn.onclick = () => {
        const wsInst = (window as any)._jarvisWs || (window as any).ws;
        if (wsInst && wsInst.readyState === 1) {
          wsInst.send(JSON.stringify({ type: "vault_lock" }));
        }
      };
    }

    if (addBtn && fileInput) {
      addBtn.onclick = () => fileInput.click();
      fileInput.onchange = () => {
        if (fileInput.files && fileInput.files[0]) {
          const filePath = (fileInput.files[0] as any).path || fileInput.files[0].name;
          const wsInst = (window as any)._jarvisWs || (window as any).ws;
          if (wsInst && wsInst.readyState === 1) {
            wsInst.send(JSON.stringify({ type: "vault_add_file", file_path: filePath }));
          }
        }
      };
    }
  }, 1000);
}
