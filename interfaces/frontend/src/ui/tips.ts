// ── Carrousel de conseils dynamiques (panneau pliable) — extrait de main.ts ──

// ── Dynamic Quick Tips Carousel (Option 2) ──────────────────────────
const QUICK_TIPS = [
  "DEMANDEZ : 'ACTIVE LE MODE IRON MAN'",
  "DEMANDEZ : 'LANCE LE SCAN ANTIVIRUS'",
  "DEMANDEZ : 'ALLUME LA LUMIERE DU SALON'",
  "DEMANDEZ : 'LANCE UNE PARTIE D'ECHECS'",
  "DEMANDEZ : 'LANCE LE DESSIN DE JARVIS'",
  "CONSEIL : SURVOLEZ LES BOUTONS POUR L'ATTRACTION MAGNETIQUE",
  "SAISIE DIRECTE : CLIQUEZ SUR CLAVIER POUR LES COMMANDES TEXTE",
  "CONFIGURATION : COMMANDE 'METS LA VOIX D'HOMME / DE FEMME'"
];

export function initDynamicUserTips() {
  const tipPanelEl = document.getElementById("user-tip");
  const tipTextEl = document.getElementById("user-tip-text");
  if (!tipPanelEl || !tipTextEl) return;

  let currentTipIndex = 0;
  let typingInterval: number | null = null;
  let collapseTimeout: number | null = null;
  let isCollapsed = false;

  function typeText(text: string, callback: () => void) {
    let charIndex = 0;
    tipTextEl!.textContent = "";
    
    if (typingInterval) clearInterval(typingInterval);
    
    typingInterval = window.setInterval(() => {
      if (charIndex < text.length) {
        tipTextEl!.textContent += text.charAt(charIndex);
        charIndex++;
      } else {
        if (typingInterval) {
          clearInterval(typingInterval);
          typingInterval = null;
        }
        callback();
      }
    }, 35); // 35ms par lettre
  }

  function collapsePanel() {
    isCollapsed = true;
    tipPanelEl!.classList.add("collapsed");
    // Changer le texte en "?" après un léger délai pour coller à la transition CSS (200ms)
    setTimeout(() => {
      if (isCollapsed) {
        tipTextEl!.textContent = "?";
      }
    }, 200);
  }

  function expandPanel() {
    if (!isCollapsed) return; // Déjà déplié
    isCollapsed = false;
    tipPanelEl!.classList.remove("collapsed");

    // Choisir le conseil suivant
    currentTipIndex = (currentTipIndex + 1) % QUICK_TIPS.length;
    
    // Attendre la fin de l'expansion CSS (300ms) puis dactylographier
    setTimeout(() => {
      if (!isCollapsed) {
        typeText(QUICK_TIPS[currentTipIndex], () => {
          // Relancer le timer de disparition automatique (5s)
          resetCollapseTimer(5000);
        });
      }
    }, 300);
  }

  function resetCollapseTimer(delay: number) {
    if (collapseTimeout) clearTimeout(collapseTimeout);
    collapseTimeout = window.setTimeout(() => {
      collapsePanel();
    }, delay);
  }

  // Horodatage du dernier changement d'astuce, partagé par le survol et le clic
  // (voir le commentaire dans le gestionnaire de clic).
  let dernierChangement = 0;

  // Événements d'interaction
  tipPanelEl.addEventListener("mouseenter", () => {
    if (isCollapsed) {
      dernierChangement = Date.now();
      expandPanel();
    } else {
      // Si l'utilisateur survole alors qu'il est déjà étendu, on garde ouvert
      if (collapseTimeout) clearTimeout(collapseTimeout);
    }
  });

  tipPanelEl.addEventListener("mouseleave", () => {
    if (!isCollapsed) {
      // S'il quitte la zone, on replie après 5 secondes d'inactivité
      resetCollapseTimer(5000);
    }
  });

  tipPanelEl.addEventListener("click", () => {
    // Un clic physique est TOUJOURS précédé d'un « mouseenter » : celui-ci a déjà
    // déplié le panneau et avancé d'une astuce. Sans ce verrou, le clic en
    // avançait une seconde — on sautait donc deux astuces d'un coup et
    // l'animation de frappe repartait en plein milieu d'un mot.
    const maintenant = Date.now();
    if (maintenant - dernierChangement < 400) return;
    dernierChangement = maintenant;

    if (isCollapsed) {
      expandPanel();
    } else {
      // Si déjà ouvert, un clic force le passage directement à l'astuce suivante
      currentTipIndex = (currentTipIndex + 1) % QUICK_TIPS.length;
      typeText(QUICK_TIPS[currentTipIndex], () => {
        resetCollapseTimer(5000);
      });
    }
  });

  // Cycle initial : Dactylographie la première astuce, puis se replie au bout de 5 secondes
  typeText(QUICK_TIPS[currentTipIndex], () => {
    resetCollapseTimer(5000);
  });
}

// Initialiser le carrousel d'astuces
