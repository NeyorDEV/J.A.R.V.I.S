import { hudState } from "./state";

// ── Paroles de JARVIS : texte léger dont les mots apparaissent un à un, au-dessus d'une ligne fine ─────────────
let subtitleTimer: number | null = null;
let subtitleTypeInterval: number | null = null;
let hudLogs: string[] = [];

function arreter(): void {
  if (subtitleTimer) { clearTimeout(subtitleTimer); subtitleTimer = null; }
  if (subtitleTypeInterval) { clearInterval(subtitleTypeInterval); subtitleTypeInterval = null; }
}

function progression(ratio: number): void {
  document.getElementById("subtitle-hud")?.style.setProperty("--progression", `${Math.round(ratio * 100)}%`);
}

export function showSubtitles(text: string) {
  const container = document.getElementById("subtitle-hud")!;
  const textEl = document.getElementById("subtitle-text")!;
  const metaEl = document.getElementById("subtitle-meta")!;

  // Messages de compilation d'une compétence : fil de journal façon console, sans animation mot à mot
  if (text.startsWith("[HUD]")) {
    arreter();
    container.classList.add("log");
    container.classList.remove("vous");
    container.style.display = "block";
    metaEl.textContent = "COMPILATION D'UNE COMPÉTENCE";
    progression(0);
    const cleanText = text.replace("[HUD] ", "").replace("[HUD]", "");
    // Réinitialiser les logs au début du processus
    if (cleanText.includes("COMPILING NEW SKILL") || cleanText.includes("SYSTEM: ALLOCATING")) hudLogs = [];
    // Filtrer les codes de couleur console ANSI éventuels
    const filteredText = cleanText.replace(/\u001b\[\d+m/g, "").replace(/\[0m/g, "").replace(/\[9\dm/g, "");
    if (filteredText.trim()) {
      hudLogs.push(filteredText);
      if (hudLogs.length > 6) hudLogs.shift(); // les 6 dernières lignes seulement
    }
    textEl.textContent = hudLogs.join("\n");
    return;
  }

  container.classList.remove("log", "vous");
  hudLogs = [];
  arreter();

  if (!hudState.subtitlesEnabled || text === "") {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";
  metaEl.textContent = "JARVIS";
  textEl.textContent = "";
  progression(0);

  // Les mots sont tous dans la page (invisibles) : la mise en page ne bouge pas pendant qu'ils apparaissent
  const mots = text.split(/\s+/).filter(Boolean).map((mot) => {
    const span = document.createElement("span");
    span.className = "mot";
    span.textContent = mot;
    textEl.appendChild(span);
    textEl.appendChild(document.createTextNode(" "));
    return span;
  });
  const pas = text.length > 200 ? 90 : 220; // plus vite pour un long texte (actualités)
  let i = 0;
  subtitleTypeInterval = window.setInterval(() => {
    if (i > 0) mots[i - 1].classList.remove("courant");
    if (i < mots.length) {
      mots[i].classList.add("visible", "courant");
      i++;
      progression(i / mots.length);
      return;
    }
    if (subtitleTypeInterval) { clearInterval(subtitleTypeInterval); subtitleTypeInterval = null; }
    // Masquer après un délai proportionnel à la longueur du texte
    subtitleTimer = window.setTimeout(() => { container.style.display = "none"; }, Math.max(3000, text.length * 50));
  }, pas);
}
