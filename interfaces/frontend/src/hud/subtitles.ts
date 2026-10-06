import { hudState } from "./state";

// ── Subtitles HUD Logic ──────────────────────────────────────────────────────
let subtitleTimer: number | null = null;
let subtitleTypeInterval: number | null = null;
let hudLogs: string[] = [];

export function showSubtitles(text: string) {
  const container = document.getElementById("subtitle-hud")!;
  const textEl = document.getElementById("subtitle-text")!;
  const metaEl = document.getElementById("subtitle-meta")!;

  if (textEl) {
    textEl.style.fontStyle = "normal";
    textEl.style.color = "#00e5ff";
  }

  // Si c'est un message du HUD de compilation (Iron Man Matrix)
  if (text.startsWith("[HUD]")) {
    if (subtitleTypeInterval) {
      clearInterval(subtitleTypeInterval);
      subtitleTypeInterval = null;
    }
    if (subtitleTimer) {
      clearTimeout(subtitleTimer);
      subtitleTimer = null;
    }
    container.style.display = "block";
    metaEl.textContent = "COMPILING_SKILL_MATRIX...";
    metaEl.style.color = "#ffaa00"; // Orange néon
    
    // Style type console / terminal
    if (textEl) {
      textEl.style.display = "block";
      textEl.style.textAlign = "left";
      textEl.style.whiteSpace = "pre-wrap";
      textEl.style.fontSize = "11px";
      textEl.style.lineHeight = "1.5";
      textEl.style.maxHeight = "120px";
      textEl.style.overflowY = "hidden";
      textEl.style.fontFamily = "'Courier New', monospace";
    }
    
    const cleanText = text.replace("[HUD] ", "").replace("[HUD]", "");
    
    // Réinitialiser les logs au début du processus
    if (cleanText.includes("COMPILING NEW SKILL") || cleanText.includes("SYSTEM: ALLOCATING")) {
            hudLogs = [];
    }
    
    // Filtrer les codes de couleur console ANSI éventuels
    const filteredText = cleanText.replace(/\u001b\[\d+m/g, '').replace(/\[0m/g, '').replace(/\[9\dm/g, '');
    
    if (filteredText.trim()) {
      hudLogs.push(filteredText);
      // Garder au maximum les 6 dernières lignes de logs à l'écran
      if (hudLogs.length > 6) {
        hudLogs.shift();
      }
    }
    
    if (textEl) {
      textEl.textContent = hudLogs.join("\n");
    }
    return;
  }

  // Restauration du style d'origine pour les sous-titres ordinaires de Jarvis
  if (textEl) {
    textEl.style.display = "inline";
    textEl.style.textAlign = "center";
    textEl.style.whiteSpace = "normal";
    textEl.style.fontSize = "18px";
    textEl.style.lineHeight = "1.4";
  }
  hudLogs = []; // Vider la console

  // Clear any existing animation
  if (subtitleTimer) clearTimeout(subtitleTimer);
  if (subtitleTypeInterval) clearInterval(subtitleTypeInterval);

  if (!hudState.subtitlesEnabled || text === "") {
    container.style.display = "none";
    return;
  }
  
  container.style.display = "block";
  textEl.textContent = "";
  metaEl.textContent = "DECRYPTING_RESPONSE...";
  metaEl.style.color = "rgba(0, 229, 255, 0.4)";

  let i = 0;
  // Faster for long text (news), slower for short phrases
  const speed = text.length > 100 ? 15 : 25;

  subtitleTypeInterval = window.setInterval(() => {
    if (i < text.length) {
      // Add a bit of "glitch" feel by sometimes adding random chars before the real one
      textEl.textContent += text.charAt(i);
      i++;

      // Auto-scroll if it's long? (The box is fixed width/max-width)
    } else {
      if (subtitleTypeInterval) clearInterval(subtitleTypeInterval);
      metaEl.textContent = "DECRYPTION_COMPLETE [STABLE]";
      metaEl.style.color = "#22c55e";

      // Hide after a delay proportional to text length
      const delay = Math.max(3000, text.length * 50);
      subtitleTimer = window.setTimeout(() => {
        container.style.display = "none";
      }, delay);
    }
  }, speed);
}
