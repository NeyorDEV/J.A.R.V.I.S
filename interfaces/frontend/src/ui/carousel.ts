// ── Dock carrousel 3D des boutons HUD (boucle infinie, drag, molette) ──
// Extrait de main.ts. Tout est encapsulé dans initCarouselDock() pour
// conserver exactement l'ordre d'initialisation d'origine.

// Contrôles de la flèche exposés aux vues 3D plein écran (renseignés par initCarouselDock)
let _arrowControls: { hide: () => void; show: () => void } | null = null;

export function hideCarouselArrow(): void {
  _arrowControls?.hide();
}

export function showCarouselArrow(): void {
  _arrowControls?.show();
}

// Redessine le dock (opacités/échelles) — utile quand l'état « allumé » d'un
// bouton change depuis l'extérieur (commande vocale, menu, WebSocket).
let _refresh: (() => void) | null = null;

export function refreshCarousel(): void {
  _refresh?.();
}

export function initCarouselDock(): void {
// ── Carousel toggle arrow ─────────────────────────────────────────────────────
const _carouselBar   = document.getElementById("hud-control-bar");
const _carouselArrow = document.getElementById("carousel-toggle-arrow") as HTMLButtonElement | null;

// Position JS directe — immunisé contre tout conflit CSS/stacking-context
// La flèche reste TOUJOURS à bottom:8px, seule son apparence change
function _positionArrow(open: boolean) {
  if (!_carouselArrow) return;
  // Si la flèche a été masquée (vue 3D ouverte), on ne la ré-affiche pas :
  // Object.assign forçait display:'flex' à chaque redimensionnement de fenêtre
  // et la faisait réapparaître par-dessus la vue 3D.
  if (_carouselArrow.style.display === "none") return;
  const w = 36, h = 22;
  Object.assign(_carouselArrow.style, {
    position:   'fixed',
    left:       `${Math.round(window.innerWidth / 2 - w / 2)}px`,
    bottom:     open ? '32px' : '8px',
    width:      `${w}px`,
    height:     `${h}px`,
    zIndex:     '10010',
    display:    'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(0,8,20,0.75)',
    border:     `1px solid rgba(0,229,255,${open ? '0.7' : '0.35'})`,
    borderRadius: '4px',
    color:      open ? '#00e5ff' : 'rgba(0,229,255,0.6)',
    fontSize:   '16px',
    cursor:     'pointer',
    padding:    '0',
    lineHeight: '1',
    transform:  open ? 'rotate(180deg)' : 'none',
    transition: 'transform 0.25s ease, color 0.15s, border-color 0.15s',
  });
}

let _carouselOpen = false;   // replié au démarrage

function _toggleCarousel(force?: boolean) {
  if (!_carouselBar) return;
  _carouselOpen = force !== undefined ? force : !_carouselOpen;
  _carouselBar.classList.toggle("carousel-hidden", !_carouselOpen);
  _positionArrow(_carouselOpen);
}

// Clic ou survol de la flèche = bascule l'affichage du carrousel.
// Le verrou temporel est partagé par les deux gestes : sans lui, un clic (qui est
// toujours précédé d'un mouseenter) basculerait deux fois et rien ne changerait.
let _carouselLastToggle = 0;

function _basculerDepuisFleche() {
  const now = Date.now();
  if (now - _carouselLastToggle < 300) return;
  _carouselLastToggle = now;
  _toggleCarousel();   // vraie bascule : ouvre ET ferme (avant : forcé ouvert au survol)
}

_carouselArrow?.addEventListener("click", _basculerDepuisFleche);
_carouselArrow?.addEventListener("mouseenter", _basculerDepuisFleche);

// Init — carrousel replié au démarrage (le HTML porte déjà .carousel-hidden) :
// on le déploie au survol ou au clic sur la flèche.
_toggleCarousel(false);
_positionArrow(false);
window.addEventListener("resize", () => _positionArrow(_carouselOpen));

// ── Carousel Controls for Button Bar (3D Dial / Cover Flow) ───────────────────
const track = document.getElementById("carousel-track");
const getCarouselButtons = () => Array.from(track ? track.getElementsByTagName("button") : []);

let activeIndex = 0;

function renderCarousel(progress = 0) {
  const buttons = getCarouselButtons();
  const N = buttons.length;
  if (N === 0) return;

  // Modulo index pour défilement infini sans aucun trou
  let virtualIndex = (activeIndex - progress) % N;
  if (virtualIndex < 0) virtualIndex += N;

  const buttonOffset = 135; // 120px + 15px gap
  const halfBarWidth = 340; // 680px bar width / 2
  const halfButtonWidth = 60; // 120px / 2

  buttons.forEach((btn, idx) => {
    let diff = idx - virtualIndex;

    // Englober la distance dans [-N/2, N/2] pour un anneau infini continu
    if (diff > N / 2) diff -= N;
    if (diff < -N / 2) diff += N;

    const xPos = Math.round(halfBarWidth + (diff * buttonOffset) - halfButtonWidth);

    btn.style.position = "absolute";
    btn.style.left = `${xPos}px`;
    btn.style.top = "9px";
    btn.style.transition = isPointerDown ? "none" : "left 0.35s cubic-bezier(0.16, 1, 0.3, 1), transform 0.35s ease, opacity 0.35s ease";

    const isCenter = Math.abs(diff) < 0.5;
    const isToggledOn = btn.getAttribute("aria-pressed") === "true" || btn.classList.contains("is-toggled-on");

    if (isCenter) {
      btn.classList.add("active");
      btn.style.opacity = "1";
      btn.style.transform = "scale(1.08)";
      btn.style.zIndex = "10";
    } else {
      btn.classList.remove("active");
      btn.style.opacity = isToggledOn ? "0.9" : (Math.abs(diff) > 2.5 ? "0" : Math.max(0.35, 1 - Math.abs(diff) * 0.35).toString());
      btn.style.transform = "scale(0.92)";
      btn.style.zIndex = "2";
    }

    // Un bouton totalement transparent doit être « traversable » : sinon il
    // reste posé (position absolue) au bord du viewport et intercepte les clics
    // destinés aux boutons visibles voisins.
    btn.style.pointerEvents = parseFloat(btn.style.opacity || "1") < 0.05 ? "none" : "auto";
  });

  // Mettre à jour les points indicateurs (modulo N : Math.round peut donner N)
  const dots = document.querySelectorAll(".carousel-dot");
  const roundedActive = Math.round(virtualIndex) % N;
  dots.forEach((dot, idx) => {
    if (idx === roundedActive) {
      dot.classList.add("active");
    } else {
      dot.classList.remove("active");
    }
  });
}

function updateCarousel() {
  renderCarousel(0);
}

const indicatorsContainer = document.querySelector(".carousel-indicators");

function createIndicators() {
  if (!indicatorsContainer) return;
  indicatorsContainer.innerHTML = "";
  const buttons = getCarouselButtons();
  // Un point par bouton. (L'ancien "/ 3" était un reste de l'époque où la piste
  // était triplée pour simuler la boucle infinie : il ne créait plus qu'un tiers
  // des points.)
  const N = buttons.length;
  if (N === 0) return;

  for (let idx = 0; idx < N; idx++) {
    const dot = document.createElement("span");
    dot.className = `carousel-dot${activeIndex === idx ? " active" : ""}`;
    dot.setAttribute("data-page", idx.toString());
    dot.title = buttons[idx].textContent?.trim() || `Bouton ${idx + 1}`;
    dot.addEventListener("click", () => {
      activeIndex = idx;
      updateCarousel();
    });
    indicatorsContainer.appendChild(dot);
  }
}

const controlBar = document.getElementById("hud-control-bar");
let isPointerDown = false;
let startX = 0;
let wasDragging = false;

if (controlBar && track) {
  // Prevent native browser drag-and-drop and text selection on the carousel
  controlBar.addEventListener("dragstart", (e) => e.preventDefault());
  controlBar.addEventListener("selectstart", (e) => e.preventDefault());

  // 1. Click listener: Center carousel AND trigger registered action via global dispatcher
  controlBar.addEventListener("click", (e) => {
    e.stopPropagation();

    const btn = (e.target as HTMLElement).closest("button");
    if (!btn) return;

    const targetId = btn.id || btn.getAttribute("data-original-id");

    if (wasDragging) {
      e.preventDefault();
      return;
    }

    const buttons = getCarouselButtons();
    const idx = buttons.indexOf(btn);
    if (idx !== -1) {
      activeIndex = idx;
      updateCarousel();
    }

    // Déclencher l'action métier enregistrée pour ce bouton
    if (targetId && (window as any)._carouselActions && typeof (window as any)._carouselActions[targetId] === "function") {
      try {
        (window as any)._carouselActions[targetId](btn);
      } catch (errAction) {
        console.error(`[CAROUSEL] Erreur action "${targetId}":`, errAction);
      }
    }
  });

  // 2. Pointer down listener (on controlBar)
  controlBar.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return; // Only trigger for primary click / touch
    isPointerDown = true;
    startX = e.clientX;
    wasDragging = false;
  });

  // 3. Pointer move listener (on document) — Seul un glissement supérieur à 25px annule le clic
  document.addEventListener("pointermove", (e) => {
    if (!isPointerDown) return;
    const dx = e.clientX - startX;
    if (Math.abs(dx) > 25) {
      if (!wasDragging) {
        wasDragging = true;
        const buttons = getCarouselButtons();
        buttons.forEach(btn => btn.style.transition = "none");
      }
    }
    if (wasDragging) {
      const progress = dx / 135;
      renderCarousel(progress);
    }
  });

  // 4. Pointer up listener (on document)
  document.addEventListener("pointerup", (e) => {
    if (!isPointerDown) return;
    isPointerDown = false;

    const buttons = getCarouselButtons();
    buttons.forEach(btn => btn.style.transition = "");

    const dx = e.clientX - startX;
    const len = buttons.length;

    if (len > 0 && wasDragging) {
      const progress = dx / 135;
      const offset = Math.round(-progress);
      activeIndex = (activeIndex + offset) % len;
      if (activeIndex < 0) activeIndex += len;
    }

    updateCarousel();

    if (wasDragging) {
      setTimeout(() => {
        wasDragging = false;
      }, 100);
    }
  });

  // 5. Pointer cancel listener (on document)
  document.addEventListener("pointercancel", () => {
    isPointerDown = false;
    const buttons = getCarouselButtons();
    buttons.forEach(btn => btn.style.transition = "");
    updateCarousel();
    wasDragging = false;
  });

  // 6. Scroll wheel listener (on controlBar)
  controlBar.addEventListener("wheel", (e) => {
    e.preventDefault();
    const buttons = getCarouselButtons();
    const len = buttons.length;
    if (len === 0) return;
    if (e.deltaY > 0) {
      activeIndex = (activeIndex + 1) % len;
    } else {
      activeIndex = (activeIndex - 1 + len) % len;
    }
    updateCarousel();
  }, { passive: false });
}

// Initialize single-copy carousel dock
createIndicators();   // (n'était plus appelé : aucun point indicateur n'apparaissait)
updateCarousel();
_refresh = updateCarousel;

// Exposer les contrôles de la flèche pour les vues 3D plein écran
_arrowControls = {
  hide: () => { if (_carouselArrow) _carouselArrow.style.display = "none"; },
  show: () => { if (_carouselArrow) { _carouselArrow.style.display = "flex"; _positionArrow(_carouselOpen); } },
};


}
