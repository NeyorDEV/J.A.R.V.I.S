/**
 * J.A.R.V.I.S — Module de Réalité Augmentée et Suivi Gestuel (Hand Tracking)
 *
 * Utilise MediaPipe Hands pour capturer les mouvements de la main via la webcam du PC,
 * dessiner un squelette néon et simuler des actions de souris/drag holographiques.
 */

// Types pour MediaPipe
type Landmark = { x: number; y: number; z: number };

let videoEl: HTMLVideoElement;
let canvasEl: HTMLCanvasElement;
let ctx: CanvasRenderingContext2D;
let handsDetector: any = null;
let cameraInstance: any = null;

let isTrackingActive = false;
const isPinched = [false, false];
const pinchStartTime = [0, 0];
let isArMirror = true;

// Historique de l'index pour le geste circulaire (Circular Wake)
type GesturePoint = { x: number; y: number; t: number };
const indexHistory: GesturePoint[][] = [[], []];
let lastMicToggleTime = 0;


export function toggleArMirror(): boolean {
  isArMirror = !isArMirror;
  if (videoEl) {
    videoEl.style.transform = isArMirror ? "scaleX(-1)" : "scaleX(1)";
  }
  return isArMirror;
}

// Variables pour le lissage des positions (support multi-curseur pour deux mains)
const cursorX = [0, 0];
const cursorY = [0, 0];
const SMOOTHING = 0.25; // Facteur d'amortissement (lerp) pour un curseur ultra-stable

// Réticule de visée holographique
let targetScale = 1.0;
let reticleRotation = 0;

// Sélecteurs CSS des widgets JARVIS pouvant être manipulés par geste
const MANIPULABLE_WIDGETS = [
  "#calendar-hud",
  "#weather-hud",
  "#music-hud",
  "#temp-panel",
  "#weather-panel",
  "#recipe-modal",
  "#image-hud",
  ".settings-container"
];

let activeManipulatedWidget: HTMLElement | null = null;
let manipulationMode: "drag" | "resize" = "drag";
let widgetOffsetX = 0;
let widgetOffsetY = 0;
let widgetInitialX = 0;
let widgetInitialY = 0;
let widgetInitialWidth = 0;
let widgetInitialHeight = 0;
let handStartX = 0;
let handStartY = 0;

export function initHandTracking() {
  videoEl = document.getElementById("hand-video") as HTMLVideoElement;
  canvasEl = document.getElementById("hand-canvas") as HTMLCanvasElement;

  if (!videoEl || !canvasEl) {
    console.error("Éléments de hand tracking absents du DOM.");
    return;
  }

  ctx = canvasEl.getContext("2d")!;
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);
}

function resizeCanvas() {
  canvasEl.width = window.innerWidth;
  canvasEl.height = window.innerHeight;
}

/**
 * Active ou désactive le suivi gestuel
 */
export async function toggleHandTracking(active?: boolean): Promise<boolean> {
  const targetState = active !== undefined ? active : !isTrackingActive;

  if (targetState) {
    try {
      const started = await startTracking();
      if (started) {
        isTrackingActive = true;
        document.body.classList.add("ar-mode-active");
        
        // Minimiser l'orbe principal en bas à gauche de façon synchronisée
        const orbCanvas = document.getElementById("orb-canvas");
        if (orbCanvas) orbCanvas.classList.add("minimized");

        // Créer un bouton de sortie flottant d'urgence "QUITTER AR" au sommet de l'écran
        let exitBtn = document.getElementById("ar-exit-floating-btn");
        if (!exitBtn) {
          exitBtn = document.createElement("button");
          exitBtn.id = "ar-exit-floating-btn";
          exitBtn.innerHTML = "✖ QUITTER LE MODE AR";
          Object.assign(exitBtn.style, {
            position: "fixed",
            top: "20px",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: "35000",
            background: "rgba(255, 51, 102, 0.85)",
            border: "1px solid #ff3366",
            borderRadius: "20px",
            color: "#fff",
            fontFamily: "monospace",
            fontSize: "12px",
            fontWeight: "bold",
            padding: "8px 20px",
            cursor: "pointer",
            boxShadow: "0 0 20px rgba(255, 51, 102, 0.6)",
            letterSpacing: "1.5px",
          });
          exitBtn.onclick = () => {
            toggleHandTracking(false);
          };
          document.body.appendChild(exitBtn);
        } else {
          exitBtn.style.display = "block";
        }
      }
      return isTrackingActive;
    } catch (err) {
      console.error("Impossible de démarrer le hand tracking:", err);
      isTrackingActive = false;
      return false;
    }
  } else {
    stopTracking();
    isTrackingActive = false;
    document.body.classList.remove("ar-mode-active");
    
    const exitBtn = document.getElementById("ar-exit-floating-btn");
    if (exitBtn) exitBtn.style.display = "none";

    // Mettre à jour les boutons d'état AR dans la page
    const btn = document.getElementById("gestures-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", "false");
      btn.classList.remove("active", "ar-active");
      btn.innerHTML = '<span class="btn-icon">🖐️</span> MODE AR';
    }
    
    // Restaurer l'orbe principal si le globe n'est pas affiché
    const orbCanvas = document.getElementById("orb-canvas");
    const globeOverlay = document.getElementById("globe-overlay");
    const globeVisible = globeOverlay && globeOverlay.style.display !== "none" && globeOverlay.style.opacity === "1";
    if (orbCanvas && !globeVisible) {
      orbCanvas.classList.remove("minimized");
    }
    return false;
  }
}

async function startTracking(): Promise<boolean> {
  // S'assurer que les bibliothèques MediaPipe sont chargées
  if (!(window as any).Hands || !(window as any).Camera) {
    throw new Error("Les scripts CDN MediaPipe ne sont pas encore chargés. Veuillez patienter.");
  }

  // Initialisation du détecteur de main
  if (!handsDetector) {
    handsDetector = new (window as any).Hands({
      locateFile: (file: string) => {
        return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
      }
    });

    handsDetector.setOptions({
      maxNumHands: 2, // Permet de détecter les deux mains
      modelComplexity: 1,
      minDetectionConfidence: 0.65,
      minTrackingConfidence: 0.65
    });

    handsDetector.onResults(onHandResults);
  }

  // Demander l'accès à la webcam (avec caméra sélectionnée si définie)
  let stream: MediaStream;
  try {
    const preferredCamId = localStorage.getItem("jarvis-camera-id") || "";
    const videoConstraints: any = {
      width: { ideal: 1280 },
      height: { ideal: 720 }
    };
    if (preferredCamId) {
      videoConstraints.deviceId = { exact: preferredCamId };
    } else {
      videoConstraints.facingMode = "user";
    }
    stream = await navigator.mediaDevices.getUserMedia({
      video: videoConstraints,
      audio: false
    });
  } catch (err) {
    console.warn("Échec du démarrage de la caméra préférée, essai avec la caméra par défaut:", err);
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1280 },
        height: { ideal: 720 },
        facingMode: "user"
      },
      audio: false
    });
  }

  videoEl.srcObject = stream;
  videoEl.style.display = "block"; // Affiche en plein écran d'arrière-plan
  videoEl.style.transform = isArMirror ? "scaleX(-1)" : "scaleX(1)";

  // Lancement de la boucle de caméra MediaPipe
  if (!cameraInstance) {
    cameraInstance = new (window as any).Camera(videoEl, {
      onFrame: async () => {
        if (isTrackingActive) {
          await handsDetector.send({ image: videoEl });
        }
      },
      width: 1280,
      height: 720
    });
  }

  await cameraInstance.start();
  return true;
}

function stopTracking() {
  if (cameraInstance) {
    cameraInstance.stop();
  }
  
  if (videoEl.srcObject) {
    const stream = videoEl.srcObject as MediaStream;
    stream.getTracks().forEach(track => track.stop());
    videoEl.srcObject = null;
  }
  
  videoEl.style.display = "none";
  ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
}

function pushIndexHistory(handIdx: number, indexTip: Landmark) {
  if (!indexTip) {
    indexHistory[handIdx] = [];
    return;
  }
  const now = Date.now();
  indexHistory[handIdx].push({ x: indexTip.x, y: indexTip.y, t: now });
  
  // Conserver 2.5 secondes d'historique
  while (indexHistory[handIdx].length > 0 && now - indexHistory[handIdx][0].t > 2500) {
    indexHistory[handIdx].shift();
  }
}

function detectCircle(handIdx: number): boolean {
  const points = indexHistory[handIdx];
  if (!points || points.length < 20) return false;

  // 1. Barycentre
  let sumX = 0, sumY = 0;
  for (const p of points) {
    sumX += p.x;
    sumY += p.y;
  }
  const centerX = sumX / points.length;
  const centerY = sumY / points.length;

  // 2. Rayon moyen
  let sumR = 0;
  const radii = [];
  for (const p of points) {
    const r = Math.hypot(p.x - centerX, p.y - centerY);
    radii.push(r);
    sumR += r;
  }
  const avgR = sumR / points.length;

  // Limite de taille du cercle dans le champ de la caméra
  if (avgR < 0.035 || avgR > 0.25) return false;

  // 3. Écart-type des rayons (régularité du cercle)
  let sumSqDiff = 0;
  for (const r of radii) {
    const diff = r - avgR;
    sumSqDiff += diff * diff;
  }
  const stdDev = Math.sqrt(sumSqDiff / points.length);
  const coeffOfVariation = stdDev / avgR;

  if (coeffOfVariation > 0.22) return false;

  // 4. Somme de l'angle cumulé
  let totalAngle = 0;
  let prevAngle: number | null = null;
  for (const p of points) {
    const angle = Math.atan2(p.y - centerY, p.x - centerX);
    if (prevAngle !== null) {
      let diff = angle - prevAngle;
      while (diff < -Math.PI) diff += 2 * Math.PI;
      while (diff > Math.PI) diff -= 2 * Math.PI;
      totalAngle += diff;
    }
    prevAngle = angle;
  }

  // Seuil pour un tour complet (5.0 radians)
  if (Math.abs(totalAngle) < 5.0) return false;

  return true;
}

function showHudToast(text: string) {
  let toast = document.getElementById("hud-gesture-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "hud-gesture-toast";
    toast.style.position = "fixed";
    toast.style.bottom = "120px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%) translateY(20px)";
    toast.style.zIndex = "10000";
    toast.style.background = "rgba(0, 229, 255, 0.08)";
    toast.style.border = "1px solid rgba(0, 229, 255, 0.4)";
    toast.style.color = "#00e5ff";
    toast.style.fontFamily = "'Courier New', monospace";
    toast.style.fontSize = "13px";
    toast.style.letterSpacing = "3px";
    toast.style.textTransform = "uppercase";
    toast.style.padding = "7px 22px";
    toast.style.borderRadius = "3px";
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.2s ease, transform 0.2s ease";
    toast.style.pointerEvents = "none";
    toast.style.backdropFilter = "blur(6px)";
    toast.style.boxShadow = "0 0 20px rgba(0, 229, 255, 0.15)";
    toast.style.whiteSpace = "nowrap";
    document.body.appendChild(toast);
  }
  
  toast.textContent = text;
  toast.style.display = "block";
  toast.getBoundingClientRect(); // force le reflow
  toast.style.opacity = "1";
  toast.style.transform = "translateX(-50%) translateY(0)";

  const timer = (toast as any)._timer;
  if (timer) clearTimeout(timer);
  
  (toast as any)._timer = setTimeout(() => {
    if (toast) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(-50%) translateY(20px)";
    }
  }, 1200);
}

/**
 * Traitement des résultats de détection de main
 */
function onHandResults(results: any) {
  ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

  if (!isTrackingActive) return;

  if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
    // 1. Dessiner le squelette pour toutes les mains détectées en néon
    for (let i = 0; i < results.multiHandLandmarks.length; i++) {
      drawHandSkeleton(results.multiHandLandmarks[i]);
    }

    // 2. Traiter chaque main de manière totalement indépendante (comme en mode Holo !)
    const numHands = results.multiHandLandmarks.length;
    for (let i = 0; i < 2; i++) {
      if (i >= numHands) {
        indexHistory[i] = [];
        continue;
      }
      const landmarks = results.multiHandLandmarks[i] as Landmark[];
      const indexTip = landmarks[8];

      // Suivi et détection du geste circulaire
      pushIndexHistory(i, indexTip);
      const now = Date.now();
      if (now - lastMicToggleTime > 2000) {
        if (detectCircle(i)) {
          lastMicToggleTime = now;
          indexHistory[i] = []; // Vider l'historique après détection
          
          const ws = (window as any)._jarvisWs;
          if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "toggle_mic" }));
          }
          
          showHudToast("MIC TOGGLE");
        }
      }
      
      // Coordonnées de l'index
      const targetX = isArMirror ? (1 - indexTip.x) * canvasEl.width : indexTip.x * canvasEl.width;
      const targetY = indexTip.y * canvasEl.height;

      // Lissage adaptatif chirurgical par Lerp dynamique (élimine le tremblement mais reste ultra réactif)
      const lastX = cursorX[i];
      const lastY = cursorY[i];
      const cursorDist = Math.hypot(targetX - lastX, targetY - lastY);
      const dynamicSmoothing = Math.min(0.38, Math.max(0.03, cursorDist / 160));
      
      cursorX[i] += (targetX - lastX) * dynamicSmoothing;
      cursorY[i] += (targetY - lastY) * dynamicSmoothing;

      // 2.5. Si un widget est activement manipulé par CETTE main (on utilise la première main pour la manipulation globale)
      if (i === 0 && activeManipulatedWidget) {
        if (manipulationMode === "drag") {
          let newX = cursorX[0] - widgetOffsetX;
          let newY = cursorY[0] - widgetOffsetY;
          newX = Math.max(10, Math.min(window.innerWidth - 100, newX));
          newY = Math.max(10, Math.min(window.innerHeight - 50, newY));
          activeManipulatedWidget.style.left = `${newX}px`;
          activeManipulatedWidget.style.top = `${newY}px`;
        } else if (manipulationMode === "resize") {
          let newWidth = cursorX[0] - widgetInitialX;
          let newHeight = cursorY[0] - widgetInitialY;
          newWidth = Math.max(180, Math.min(window.innerWidth - widgetInitialX - 20, newWidth));
          newHeight = Math.max(120, Math.min(window.innerHeight - widgetInitialY - 20, newHeight));
          activeManipulatedWidget.style.width = `${newWidth}px`;
          activeManipulatedWidget.style.height = `${newHeight}px`;
        }
      }

      // 3. Détecter le geste de Pincement indépendant par main
      const thumbTip = landmarks[4];
      const dx = thumbTip.x - indexTip.x;
      const dy = thumbTip.y - indexTip.y;
      const dz = thumbTip.z - indexTip.z;
      const distance = Math.sqrt(dx*dx + dy*dy + dz*dz);

      const PINCH_THRESHOLD = 0.035;
      const RELEASE_THRESHOLD = 0.045;

      if (!isPinched[i] && distance < PINCH_THRESHOLD) {
        isPinched[i] = true;
        pinchStartTime[i] = Date.now();
        triggerPinchEvent("start", cursorX[i], cursorY[i], i);
      } else if (isPinched[i] && distance > RELEASE_THRESHOLD) {
        isPinched[i] = false;
        triggerPinchEvent("end", cursorX[i], cursorY[i], i);
      }

      // 4. Dessiner le pointeur holographique de style JARVIS pour CETTE main (SYS_POINTER_01 ou SYS_POINTER_02)
      drawJarvisReticle(cursorX[i], cursorY[i], isPinched[i], i);

    }

    // Si c'est la main principale (index 0), on gère le curseur virtuel HTML et Three.js
    if (numHands > 0) {
      const virtCursor = document.getElementById("virtual-cursor");
      if (virtCursor) {
        virtCursor.style.left = `${cursorX[0]}px`;
        virtCursor.style.top = `${cursorY[0]}px`;
      }
      triggerMoveEvent(
        cursorX[0],
        cursorY[0],
        isPinched[0],
        numHands > 1 ? cursorX[1] : undefined,
        numHands > 1 ? cursorY[1] : undefined,
        numHands > 1 ? isPinched[1] : undefined
      );
    }

    // 3.5. Dessiner l'overlay de sélection holographique si manipulation en cours
    drawManipulatedWidgetOverlay();
  } else {
    indexHistory[0] = [];
    indexHistory[1] = [];
  }
}

/**
 * Émet des événements globaux pour piloter le reste du frontend
 */
function triggerMoveEvent(x: number, y: number, pinched: boolean, x1?: number, y1?: number, pinched1?: boolean) {
  const event = new CustomEvent("jarvis-hand-move", {
    detail: { x, y, pinched, x1, y1, pinched1 }
  });
  document.dispatchEvent(event);
}


function triggerPinchEvent(type: "start" | "end", x: number, y: number, handIdx: number = 0) {
  const eventName = type === "start" ? "jarvis-hand-click" : "jarvis-hand-release";
  const event = new CustomEvent(eventName, {
    detail: { x, y, handIdx }
  });
  document.dispatchEvent(event);

  if (type === "start") {
    const manipulation = getWidgetUnderPointer(x, y);
    
    if (manipulation) {
      // Activer le mode manipulation de widget holographique
      activeManipulatedWidget = manipulation.element;
      manipulationMode = manipulation.mode;
      
      const rect = activeManipulatedWidget.getBoundingClientRect();
      
      widgetInitialX = rect.left;
      widgetInitialY = rect.top;
      widgetInitialWidth = rect.width;
      widgetInitialHeight = rect.height;
      
      widgetOffsetX = x - rect.left;
      widgetOffsetY = y - rect.top;
      
      handStartX = x;
      handStartY = y;
      
      // Désactiver temporairement les transitions CSS et les transforms d'alignement pour un déplacement à 60 FPS
      activeManipulatedWidget.style.transition = "none";
      activeManipulatedWidget.style.transform = "none";
      activeManipulatedWidget.style.position = "fixed";
      activeManipulatedWidget.style.right = "auto";
      activeManipulatedWidget.style.bottom = "auto";
      
      // Passer au premier plan au-dessus du reste du HUD
      activeManipulatedWidget.style.zIndex = "10000";
    } else {
      // Simulation classique du clic DOM sur les boutons
      simulateDomClick(x, y);
    }
  } else if (type === "end") {
    if (activeManipulatedWidget) {
      // Rétablir la transition pour de futures animations ordinaires
      activeManipulatedWidget.style.transition = "";
      
      // Réduire un peu le zIndex tout en le maintenant au-dessus du HUD standard (70)
      activeManipulatedWidget.style.zIndex = "500";
      
      activeManipulatedWidget = null;
    }
  }
}

/**
 * Détermine si le curseur survole un bouton interactif ou un widget manipulable.
 * Si un widget est trouvé, détecte s'il faut passer en mode déplacement (drag) ou redimensionnement (resize).
 */
function getWidgetUnderPointer(x: number, y: number): { element: HTMLElement, mode: "drag" | "resize" } | null {
  // Désactiver momentanément le pointeur sur le canvas pour le hit-testing sous-jacent
  const oldPointerEvents = canvasEl.style.pointerEvents;
  canvasEl.style.pointerEvents = "none";
  const target = document.elementFromPoint(x, y) as HTMLElement | null;
  canvasEl.style.pointerEvents = oldPointerEvents;
  
  if (!target) return null;

  let current: HTMLElement | null = target;
  let foundWidget: HTMLElement | null = null;
  let foundInteractive = false;

  while (current && current.tagName !== "BODY" && current.tagName !== "HTML") {
    const tagName = current.tagName.toUpperCase();
    
    // Classes et identifiants interactifs (boutons, listes, entrées)
    const isInteractiveClass = current.classList.contains("music-btn") || 
                               current.classList.contains("close-recipe") || 
                               current.classList.contains("tp-close") || 
                               current.classList.contains("wp-close") || 
                               current.classList.contains("settings-close") ||
                               current.classList.contains("ha-tab-btn") ||
                               current.id === "close-recipe" ||
                               current.id === "music-toggle" ||
                               current.id === "settings-save-btn";

    if (tagName === "BUTTON" || tagName === "A" || tagName === "INPUT" || tagName === "SELECT" || isInteractiveClass) {
      foundInteractive = true;
      break; // Un bouton interactif a la priorité absolue pour simuler un clic classique
    }

    // Tester si l'élément correspond à l'un de nos widgets holographiques configurés
    for (const selector of MANIPULABLE_WIDGETS) {
      if (current.matches(selector)) {
        foundWidget = current;
        break;
      }
    }

    if (foundWidget) {
      break;
    }

    current = current.parentElement;
  }

  // Ne pas manipuler le widget si l'utilisateur cliquait sur un de ses boutons internes
  if (foundInteractive || !foundWidget) return null;

  const rect = foundWidget.getBoundingClientRect();
  
  // Zone de redimensionnement de 35px dans le coin inférieur droit du widget
  const RESIZE_ZONE = 35;
  const inResizeZone = (x >= rect.right - RESIZE_ZONE && y >= rect.bottom - RESIZE_ZONE);
  
  return {
    element: foundWidget,
    mode: inResizeZone ? "resize" : "drag"
  };
}

/**
 * Simule de façon transparente un clic DOM sur l'élément sous-jacent
 */
function simulateDomClick(x: number, y: number) {
  const oldPointerEvents = canvasEl.style.pointerEvents;
  canvasEl.style.pointerEvents = "none";
  const element = document.elementFromPoint(x, y) as HTMLElement;
  canvasEl.style.pointerEvents = oldPointerEvents;

  if (
    element && 
    element.id !== "orb-canvas" && 
    element.id !== "globe-canvas" && 
    element.id !== "hand-video" && 
    element.id !== "hand-canvas" && 
    element.tagName !== "BODY" && 
    element.tagName !== "HTML"
  ) {
    console.log(`[JARVIS] Clic virtuel à (x: ${Math.round(x)}, y: ${Math.round(y)}) -> Élément touché :`, element.tagName, element.id ? `#${element.id}` : "", element.className ? `.${element.className.split(' ').join('.')}` : "");
    element.click();
    
    // Feedback tactile / visuel de pression
    const originalTransform = element.style.transform;
    element.style.transform = "scale(0.95)";
    setTimeout(() => { element.style.transform = originalTransform; }, 150);
  }
}

/**
 * Dessine un cadre de diagnostic néon ultra-premium autour du widget sélectionné
 */
function drawManipulatedWidgetOverlay() {
  if (!activeManipulatedWidget) return;

  const rect = activeManipulatedWidget.getBoundingClientRect();
  
  ctx.save();
  
  const isResize = manipulationMode === "resize";
  const neonColor = isResize ? "#00ffaa" : "#00e5ff";
  ctx.strokeStyle = neonColor;
  ctx.shadowColor = neonColor;
  ctx.shadowBlur = 15;
  ctx.lineWidth = 2;
  
  // 1. Cadre de ciblage pointillé
  ctx.setLineDash([8, 6]);
  ctx.beginPath();
  ctx.rect(rect.left - 6, rect.top - 6, rect.width + 12, rect.height + 12);
  ctx.stroke();
  ctx.setLineDash([]);
  
  // 2. Supports de coins en L (style HUD technologique d'Iron Man)
  const L_SIZE = 12;
  ctx.lineWidth = 3;
  ctx.shadowBlur = 8;
  
  const pad = 6;
  const l = rect.left - pad;
  const t = rect.top - pad;
  const r = rect.right + pad;
  const b = rect.bottom + pad;
  
  // Coins Haut Gauche / Haut Droit / Bas Gauche / Bas Droit
  ctx.beginPath(); ctx.moveTo(l + L_SIZE, t); ctx.lineTo(l, t); ctx.lineTo(l, t + L_SIZE); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(r - L_SIZE, t); ctx.lineTo(r, t); ctx.lineTo(r, t + L_SIZE); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(l + L_SIZE, b); ctx.lineTo(l, b); ctx.lineTo(l, b - L_SIZE); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(r - L_SIZE, b); ctx.lineTo(r, b); ctx.lineTo(r, b - L_SIZE); ctx.stroke();

  // 3. Faisceau scanner radar horizontal
  const scanTime = Date.now() * 0.003;
  const scanY = rect.top + (Math.sin(scanTime) * 0.5 + 0.5) * rect.height;
  ctx.strokeStyle = isResize ? "rgba(0, 255, 170, 0.25)" : "rgba(0, 229, 255, 0.25)";
  ctx.lineWidth = 1;
  ctx.shadowBlur = 0;
  ctx.beginPath();
  ctx.moveTo(rect.left, scanY);
  ctx.lineTo(rect.right, scanY);
  ctx.stroke();

  // 4. Libellés de diagnostics et télémétrie du système holographique
  ctx.fillStyle = neonColor;
  ctx.font = "bold 9px 'Courier New', monospace";
  ctx.shadowBlur = 4;
  
  // Étiquette supérieure : Identifiant système et protocole
  const modeText = isResize ? "SYS_RESZ_ACTIVE" : "SYS_DRAG_ACTIVE";
  ctx.textAlign = "left";
  ctx.fillText(`◈ ${modeText} // ID: ${activeManipulatedWidget.id.toUpperCase() || "W_CONTAINER"}`, rect.left, rect.top - 12);
  
  // Étiquette inférieure : Dimensions courantes de l'hologramme
  ctx.textAlign = "right";
  ctx.fillText(`${Math.round(rect.width)}px x ${Math.round(rect.height)}px`, rect.right, rect.bottom + 16);
  
  ctx.restore();
}

/**
 * Dessine le squelette de la main en mode holographique néon
 */
function drawHandSkeleton(landmarks: Landmark[]) {
  // Articulations reliées (MediaPipe standard)
  const CONNECTIONS = [
    [0, 1], [1, 2], [2, 3], [3, 4], // Pouce
    [0, 5], [5, 6], [6, 7], [7, 8], // Index
    [5, 9], [9, 10], [10, 11], [11, 12], // Majeur
    [9, 13], [13, 14], [14, 15], [15, 16], // Annulaire
    [13, 17], [17, 18], [18, 19], [19, 20], // Auriculaire
    [0, 17] // Base paume
  ];

  ctx.save();
  
  // Style néon bleu électrique
  ctx.strokeStyle = "rgba(0, 229, 255, 0.65)";
  ctx.lineWidth = 3;
  ctx.lineCap = "round";
  ctx.shadowColor = "#00e5ff";
  ctx.shadowBlur = 12;

  // Dessin des liaisons
  CONNECTIONS.forEach(([start, end]) => {
    const p1 = landmarks[start];
    const p2 = landmarks[end];

    const x1 = isArMirror ? (1 - p1.x) * canvasEl.width : p1.x * canvasEl.width;
    const x2 = isArMirror ? (1 - p2.x) * canvasEl.width : p2.x * canvasEl.width;

    ctx.beginPath();
    ctx.moveTo(x1, p1.y * canvasEl.height);
    ctx.lineTo(x2, p2.y * canvasEl.height);
    ctx.stroke();
  });

  // Dessin des joints
  ctx.fillStyle = "#ffffff";
  ctx.shadowColor = "#00e5ff";
  ctx.shadowBlur = 18;

  landmarks.forEach((p, idx) => {
    const x = isArMirror ? (1 - p.x) * canvasEl.width : p.x * canvasEl.width;
    const y = p.y * canvasEl.height;

    ctx.beginPath();
    // Les extrémités des doigts brillent plus fort et sont un peu plus grosses
    const size = [4, 8, 12, 16, 20].includes(idx) ? 6 : 4;
    
    if (idx === 8) {
      // Index (cible principale) : halo vert néon additionnel
      ctx.fillStyle = "#00ffaa";
      ctx.shadowColor = "#00ffaa";
      ctx.arc(x, y, 7, 0, 2 * Math.PI);
    } else {
      ctx.fillStyle = "#ffffff";
      ctx.shadowColor = "#00e5ff";
      ctx.arc(x, y, size, 0, 2 * Math.PI);
    }
    
    ctx.fill();
  });

  ctx.restore();
}

/**
 * Dessine un magnifique réticule holographique rotatif de style JARVIS
 */
function drawJarvisReticle(x: number, y: number, pinched: boolean, handIdx: number = 0) {
  ctx.save();
  ctx.translate(x, y);

  // Rotation constante pour l'effet technologique
  reticleRotation += pinched ? 0.08 : 0.02;

  // Animer l'échelle lors du pincement
  if (pinched) {
    targetScale += (0.8 - targetScale) * 0.25;
  } else {
    targetScale += (1.1 - targetScale) * 0.15;
  }
  ctx.scale(targetScale, targetScale);

  ctx.shadowColor = pinched ? "#00ff88" : "#00e5ff";
  ctx.shadowBlur = 15;
  ctx.strokeStyle = pinched ? "rgba(0, 255, 136, 0.8)" : "rgba(0, 229, 255, 0.7)";
  ctx.lineWidth = 2;

  // 1. Cercle extérieur pointillé/interrompu
  ctx.beginPath();
  ctx.arc(0, 0, 24, reticleRotation, reticleRotation + Math.PI * 0.4);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(0, 0, 24, reticleRotation + Math.PI, reticleRotation + Math.PI * 1.4);
  ctx.stroke();

  // 2. Réticule intérieur de ciblage
  ctx.strokeStyle = pinched ? "rgba(0, 255, 136, 0.5)" : "rgba(0, 229, 255, 0.4)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(0, 0, 14, 0, 2 * Math.PI);
  ctx.stroke();

  // 3. Point de visée central
  ctx.fillStyle = pinched ? "#00ff88" : "#ffffff";
  ctx.beginPath();
  ctx.arc(0, 0, pinched ? 5 : 3, 0, 2 * Math.PI);
  ctx.fill();

  // 4. Lignes de calibration HUD (Iron Man)
  if (!pinched) {
    ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
    ctx.beginPath();
    ctx.moveTo(-35, 0); ctx.lineTo(-28, 0);
    ctx.moveTo(28, 0); ctx.lineTo(35, 0);
    ctx.moveTo(0, -35); ctx.lineTo(0, -28);
    ctx.moveTo(0, 28); ctx.lineTo(0, 35);
    ctx.stroke();
  }

  // 5. Texte indicateur d'action (SYS_POINTER_01 ou SYS_POINTER_02)
  ctx.fillStyle = pinched ? "#00ff88" : "#00e5ff";
  ctx.font = "bold 9px 'Courier New', monospace";
  ctx.textAlign = "center";
  ctx.shadowBlur = 4;
  ctx.fillText(pinched ? "LOCK_CLICK" : `SYS_POINTER_0${handIdx + 1}`, 0, -32);

  ctx.restore();
}


