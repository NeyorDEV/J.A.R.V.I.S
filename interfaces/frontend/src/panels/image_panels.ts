// ── Panneaux images (HUD image générée + grilles de recherche flottantes) ──
// Extrait de main.ts.

import { makePanelDraggable } from "../ui/draggable";
import { ouvrirEcran, fermerEcran } from "../hud/cylindre_ouvert";
import { esc, icone } from "./pm_utils";

// Intervalle de l'animation de balayage en cours (un seul à la fois)
let scanIntervalActif: number | null = null;

export function showImageHUD(url: string, prompt: string) {
  const container = document.getElementById("image-hud")!;
  const img = document.getElementById("image-display") as HTMLImageElement;
  const promptEl = document.getElementById("image-prompt")!;
  const statusEl = document.getElementById("image-status")!;
  const scan = document.getElementById("image-scan")!;

  container.style.display = "block";
  ouvrirEcran("image-generee", container); // recherche de la fiche, puis le cylindre s'étire en écran de la taille de l'image
  img.style.opacity = "0";
  img.src = url;
  promptEl.textContent = `PROMPT: ${prompt}`;
  statusEl.textContent = "[RECONSTRUCTING_DATA...]";
  statusEl.style.color = "#ff3d00";
  scan.style.display = "block";

  // Animation de balayage.
  // Le handle est conservé au niveau du module : si une deuxième image arrive
  // avant la fin du chargement de la première, img.onload est écrasé et
  // l'intervalle précédent devenait inatteignable — il continuait à tourner
  // toutes les 30 ms pour toujours, en modifiant sans cesse #image-scan.
  if (scanIntervalActif !== null) clearInterval(scanIntervalActif);
  let pos = 0;
  const scanInterval = window.setInterval(() => {
    pos += 5;
    scan.style.top = `${pos % 100}%`;
  }, 30);
  scanIntervalActif = scanInterval;

  // Sécurité : Si l'image met trop de temps (15s), on arrête tout
  const timeout = setTimeout(() => {
    if (img.style.opacity === "0") {
      clearInterval(scanInterval);
      if (scanIntervalActif === scanInterval) scanIntervalActif = null;
      scan.style.display = "none";
      statusEl.textContent = "[ERROR: RECONSTRUCTION_FAILED]";
      statusEl.style.color = "#ff3d00";
      console.error("Timeout loading image:", url);
    }
  }, 15000);

  img.onload = () => {
    clearTimeout(timeout);
    setTimeout(() => {
      clearInterval(scanInterval);
      if (scanIntervalActif === scanInterval) scanIntervalActif = null;
      scan.style.display = "none";
      img.style.opacity = "1";
      statusEl.textContent = "[RECONSTRUCTION_COMPLETE]";
      statusEl.style.color = "#00e5ff";
    }, 2000);
  };

  img.onerror = () => {
    clearTimeout(timeout);
    clearInterval(scanInterval);
    if (scanIntervalActif === scanInterval) scanIntervalActif = null;
    scan.style.display = "none";
    statusEl.textContent = "[ERROR: SOURCE_UNREACHABLE]";
    statusEl.style.color = "#ff3d00";
    console.error("Failed to load image from URL:", url);
  };
}

document.getElementById("image-close")?.addEventListener("click", () => {
  const hud = document.getElementById("image-hud");
  if (hud) hud.style.display = "none";
  fermerEcran("image-generee", hud ?? undefined);
  // Fermer à la main pendant le chargement laissait l'animation tourner sans fin.
  if (scanIntervalActif !== null) {
    clearInterval(scanIntervalActif);
    scanIntervalActif = null;
  }
});


// ── Image Panels Logic (Iron Man style floating panels) ──────────────────────
let imgPanelCount = 0;
let imgPanelId = 0;
let maxZIndex = 600;

export function showImagePanel(query: string, images: string[]) {
  const container = document.getElementById("image-panels-container");
  if (!container) return;

  const raison = `images-${++imgPanelId}`;
  const panel = document.createElement("div");
  panel.className = "pm visible";
  panel.style.setProperty("--pm-a", "#00e5ff");
  panel.style.setProperty("--pm-largeur", "460px");
  panel.style.transform = "none";

  // Bring to front on mousedown
  panel.addEventListener("mousedown", () => {
    maxZIndex++;
    panel.style.zIndex = maxZIndex.toString();
  });

  // Calculate dynamic position with cascade offset
  const offset = (imgPanelCount % 6) * 30;
  const left = Math.max(20, (window.innerWidth - 420) / 2 + offset);
  const top = Math.max(20, (window.innerHeight - 380) / 2 + offset);
  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
  imgPanelCount++;

  const n = images.length;
  panel.innerHTML = `
    <div class="pm-tete">
      <div class="pm-icone">${icone("image")}</div>
      <div><div class="pm-titre">IMAGES</div><div class="pm-sous">${n} résultat${n > 1 ? "s" : ""} · ${esc(query)}</div></div>
      <div class="pm-tete-droite"><button class="pm-fermer img-panel-close" title="Fermer">${icone("fermer")}</button></div>
    </div>
    <div class="pm-grille-images"></div>
    <div class="pm-pied"><span>Cliquez sur une image pour l'agrandir</span></div>
  `;

  // Populate grid
  const grid = panel.querySelector(".pm-grille-images") as HTMLElement;
  if (images.length === 0) {
    const empty = document.createElement("div");
    empty.className = "pm-vide";
    empty.style.gridColumn = "1 / -1";
    empty.textContent = "AUCUNE IMAGE TROUVÉE";
    grid.appendChild(empty);
  } else {
    images.forEach((url, index) => {
      const item = document.createElement("div");
      item.className = "pm-vignette";
      // Stagger animation delay
      item.style.animationDelay = `${index * 0.08}s`;
      
      const img = document.createElement("img");
      img.src = url;
      img.alt = query;
      img.loading = "lazy";
      
      // Handle image load error
      img.onerror = () => {
        img.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'><rect width='100' height='100' fill='rgba(0,8,20,0.8)'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-family='Courier, monospace' font-size='9' fill='%23ff5a5f'>INDISPONIBLE</text></svg>";
      };

      item.appendChild(img);
      
      // Click for fullscreen zoom
      item.addEventListener("click", () => {
        showFullscreenImage(url, query);
      });

      grid.appendChild(item);
    });
  }

  // Setup close button
  const closeBtn = panel.querySelector(".img-panel-close") as HTMLElement;
  closeBtn.addEventListener("click", () => {
    fermerEcran(raison, panel);
    panel.classList.remove("visible");
    setTimeout(() => {
      panel.remove();
    }, 400);
  });

  // Setup Drag & Drop
  const header = panel.querySelector(".pm-tete") as HTMLElement;
  makePanelDraggable(panel, header);

  // Append & animate in
  container.appendChild(panel);
  ouvrirEcran(raison, panel);
  
  // Trigger Reflow to animate opacity/scale
  void panel.offsetWidth;
  panel.classList.add("visible");
}

function showFullscreenImage(url: string, query: string) {
  const overlay = document.createElement("div");
  overlay.className = "img-zoom-overlay";

  overlay.innerHTML = `
    <button class="img-zoom-close">FERMER [ÉCHAP]</button>
    <img src="${esc(url)}" alt="${esc(query)}" />
    <div class="img-zoom-label">IMAGE // ${esc(query.toUpperCase())}</div>
  `;

  const closeOverlay = () => {
    overlay.remove();
    document.removeEventListener("keydown", handleEsc);
  };

  const handleEsc = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      closeOverlay();
    }
  };

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay || (e.target as HTMLElement).classList.contains("img-zoom-close")) {
      closeOverlay();
    }
  });

  document.addEventListener("keydown", handleEsc);
  document.body.appendChild(overlay);
}

