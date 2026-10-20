import { icone } from "./panels/pm_utils";
let stream: MediaStream | null = null;

export async function enableScreenCapture(): Promise<boolean> {
  if (stream) return true;
  try {
    stream = await navigator.mediaDevices.getDisplayMedia({
      video: { frameRate: 1 },
      audio: false,
    });
    stream.getVideoTracks()[0].addEventListener("ended", () => {
      stream = null;
      console.warn("[VISION] Partage d'écran arrêté par l'utilisateur");
      // Remettre le bouton dans l'état réel : sans cela, arrêter le partage via
      // la barre du navigateur laissait « VISION » affiché comme actif alors que
      // chaque capture renvoyait null, sans aucun signe visible pour l'utilisateur.
      const btn = document.getElementById("vision-button");
      if (btn) {
        btn.setAttribute("aria-pressed", "false");
        btn.classList.remove("is-toggled-on", "active");
        btn.innerHTML = `<span class="btn-icon">${icone("oeil")}</span> VISION`;
      }
    });
    console.log("[VISION] Capture d'écran activée");
    return true;
  } catch (e) {
    console.error("[VISION] Refusé:", e);
    return false;
  }
}

export async function captureFrame(): Promise<string | null> {
  if (!stream) {
    console.warn("[VISION] Pas de stream — clique sur 'Activer la vision'");
    return null;
  }

  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;

    video.onloadedmetadata = async () => {
      try {
        await video.play();

        const maxW = 1280;
        const ratio = video.videoWidth > maxW ? maxW / video.videoWidth : 1;
        const w = Math.round(video.videoWidth * ratio);
        const h = Math.round(video.videoHeight * ratio);

        const canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(video, 0, 0, w, h);
          resolve(canvas.toDataURL("image/jpeg", 0.8).split(",")[1]);
        } else {
          resolve(null);
        }
      } catch (e) {
        console.error("Erreur lecture video:", e);
        resolve(null);
      } finally {
        video.pause();
        video.srcObject = null;
      }
    };

    // Timeout de sécurité si la vidéo ne se charge pas
    setTimeout(() => {
      resolve(null);
    }, 5000);
  });
}

export function stopScreenCapture() {
  if (stream) {
    try {
      stream.getTracks().forEach(track => track.stop());
    } catch (e) {
      console.error("[VISION] Erreur lors de l'arrêt du stream:", e);
    }
    stream = null;
    console.log("[VISION] Capture d'écran arrêtée");
  }
}

let isEnablingVision = false;

export async function toggleVision(btn?: HTMLElement) {
  if (isEnablingVision) {
    console.warn("[VISION] Activation déjà en cours, appel ignoré");
    return;
  }
  isEnablingVision = true;

  try {
    const targetBtn = btn || document.getElementById('vision-button');
    
    // 1. Si le stream est actif -> ÉTEINDRE LA VISION
    if (stream) {
      console.log("[VISION] Demande d'arrêt de la vision...");
      stopScreenCapture();
      if (targetBtn) {
        targetBtn.innerHTML = `<span class="btn-icon">${icone("oeil")}</span> VISION`;
        targetBtn.classList.remove('is-toggled-on', 'vision-active', 'vision-error');
        targetBtn.setAttribute('aria-pressed', 'false');
      }
      return;
    }

    // 2. Si le stream est inactif -> DÉMARRAGE DE LA VISION
    console.log("[VISION] Demande d'activation de la vision...");
    const ok = await enableScreenCapture();
    if (targetBtn) {
      targetBtn.innerHTML = ok ? `<span class="btn-icon">${icone("oeil")}</span> VISION • ON` : `<span class="btn-icon">${icone("oeil")}</span> VISION KO`;
      targetBtn.classList.toggle('is-toggled-on', ok);
      targetBtn.classList.toggle('vision-active', ok);
      targetBtn.classList.toggle('vision-error', !ok);
      targetBtn.setAttribute('aria-pressed', ok ? 'true' : 'false');
    }
  } finally {
    isEnablingVision = false;
  }
}

export function injectVisionButton() {
  // L'action est gérée de façon centralisée par main.ts (bindCarouselAction)
  const btn = document.getElementById('vision-button');
  if (btn) {
    btn.setAttribute('title', 'Activer/Désactiver la vision par capture d\'écran');
  }
}
