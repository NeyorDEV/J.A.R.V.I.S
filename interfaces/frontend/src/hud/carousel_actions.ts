import { icone } from "../panels/pm_utils";
import { toggleHandTracking } from "../hand_tracking";
import { toggleVision } from "../screen_capture";
import { wsRef } from "../ws_link";
import { helpOverlayEl, jarvisMenuBtn, jarvisMenuDropdown, settingsModalEl } from "./dom_refs";
import { hideHelpHUD, showHelpHUD } from "./help_hud";
import { closeSettingsModal, openSettingsModal } from "./settings";
import { hudState } from "./state";
import { closeAntivirusPanel, openAntivirusPanel } from "../panels/antivirus_panel";
import { closeUninstallerPanel, openUninstallerPanel } from "../panels/uninstaller_panel";
import { closeWingetPanel, openWingetPanel } from "../panels/winget_panel";
import { refreshCarousel } from "../ui/carousel";

export function initCarouselActions(): void {
  // ── BINDINGS D'ÉVÉNEMENTS POUR LE DOCK CAROUSEL OPERATIONAL ──
  (window as any)._carouselActions = (window as any)._carouselActions || {};

  const bindCarouselAction = (btnId: string, actionFn: (btn: HTMLElement) => void) => {
    (window as any)._carouselActions[btnId] = actionFn;
  };

  // 0. Vision Button
  bindCarouselAction("vision-button", (btn) => {
    toggleVision(btn);
  });

  // 3. HUD Text Subtitles
  bindCarouselAction("subtitle-toggle", (btn) => {
    hudState.subtitlesEnabled = !hudState.subtitlesEnabled;
    setCarouselBtnState(btn, hudState.subtitlesEnabled);
    btn.innerHTML = hudState.subtitlesEnabled ? `<span class="btn-icon">${icone("discussion")}</span> HUD TEXT` : `<span class="btn-icon">${icone("discussion")}</span> TEXT OFF`;
    const subHud = document.getElementById("subtitle-hud");
    if (subHud && !hudState.subtitlesEnabled) {
      // On masque à la désactivation. À l'activation on NE force PAS l'affichage :
      // showSubtitles() ouvrira la boîte quand JARVIS aura réellement du texte à
      // afficher — sinon on laissait un cadre vide impossible à faire disparaître.
      subHud.style.display = "none";
    }
  });

  // 4. Mode AR Gestures
  bindCarouselAction("gestures-toggle", async (btn) => {
    const isPressed = btn.getAttribute("aria-pressed") === "true";
    const newState = !isPressed;
    (btn as HTMLButtonElement).disabled = true;
    btn.innerHTML = newState ? `<span class="btn-icon">${icone("sablier")}</span> CHARGEMENT...` : `<span class="btn-icon">${icone("main")}</span> MODE AR`;
    const active = await toggleHandTracking(newState);
    (btn as HTMLButtonElement).disabled = false;
    setCarouselBtnState(btn, active);
    btn.classList.toggle("ar-active", active);
    btn.innerHTML = active ? `<span class="btn-icon">${icone("main")}</span> AR ACTIF` : `<span class="btn-icon">${icone("main")}</span> MODE AR`;
  });

  // ── État visuel des boutons du carrousel ──────────────────────────────────────
  // N.B. : on n'utilise PAS la classe .active ici — elle est réservée au bouton
  // centré par renderCarousel(). L'état « allumé » passe par aria-pressed +
  // .is-toggled-on, que le CSS du carrousel sait déjà styler.
  function setCarouselBtnState(btnOrId: HTMLElement | string, on: boolean): void {
    const b = typeof btnOrId === "string" ? document.getElementById(btnOrId) : btnOrId;
    if (!b) return;
    b.setAttribute("aria-pressed", String(on));
    b.classList.toggle("is-toggled-on", on);
  }

  // Helper d'ouverture/fermeture d'un panneau HUD.
  // IMPORTANT : on ne pilote QUE les classes .hidden/.visible, qui sont le contrat
  // des feuilles de style (.xxx-panel.hidden { display:none !important }).
  // Poser des styles inline !important ici (comme le faisait la version
  // précédente) les laissait collés sur l'élément après fermeture : tous les
  // autres chemins d'ouverture (commande vocale, menu déroulant, message
  // WebSocket) remettaient bien les bonnes classes mais le panneau restait
  // invisible, car le display:none inline gagnait sur le CSS.
  function toggleHudPanel(panelId: string, btn: HTMLElement, onOpen?: () => void, onClose?: () => void): boolean {
    const p = document.getElementById(panelId);
    if (!p) {
      console.warn(`[CAROUSEL] Panneau introuvable : #${panelId}`);
      return false;
    }

    // Purge des styles inline hérités qui écraseraient le CSS
    ["display", "opacity", "visibility", "z-index"].forEach(prop => p.style.removeProperty(prop));

    const estOuvert = !p.classList.contains("hidden");

    if (estOuvert) {
      p.classList.add("hidden");
      p.classList.remove("visible");
      setCarouselBtnState(btn, false);
      if (onClose) onClose();
      return false;
    }

    p.classList.remove("hidden");
    p.classList.add("visible");
    setCarouselBtnState(btn, true);
    if (onOpen) onOpen();
    return true;
  }

  // 6. Désinstallateur
  bindCarouselAction("carousel-uninstaller-btn", (btn) => {
    const panneau = document.getElementById("uninstaller-panel");
    const estOuvert = panneau ? !panneau.classList.contains("hidden") : false;
    if (estOuvert) {
      closeUninstallerPanel();
      setCarouselBtnState(btn, false);
    } else {
      openUninstallerPanel();
      setCarouselBtnState(btn, true);
      setCarouselBtnState("carousel-winget-btn", false); // openUninstallerPanel ferme l'autre
    }
  });

  // 7. Winget / Mises à jour
  // Le panneau réel est #winget-panel (l'ancien code ciblait #winget-logs-panel,
  // qui n'existe pas → le bouton ne faisait rien). On réutilise les fonctions du
  // module, qui gèrent aussi la requête des mises à jour et le bouton du menu.
  bindCarouselAction("carousel-winget-btn", (btn) => {
    const panneau = document.getElementById("winget-panel");
    const estOuvert = panneau ? !panneau.classList.contains("hidden") : false;
    if (estOuvert) {
      closeWingetPanel();
      setCarouselBtnState(btn, false);
    } else {
      openWingetPanel();
      setCarouselBtnState(btn, true);
      setCarouselBtnState("carousel-uninstaller-btn", false); // openWingetPanel ferme l'autre
    }
  });

  // 8. Antivirus Scan
  // openAntivirusPanel() affiche le panneau ET envoie av_scan_start (le type
  // attendu par le backend ; l'ancien code envoyait start_av_scan, jamais traité).
  bindCarouselAction("carousel-av-scan-btn", (btn) => {
    const panneau = document.getElementById("av-panel");
    // On teste « .visible » et non « !.hidden » : la fermeture est animée sur
    // 400 ms, pendant lesquelles le panneau ne porte NI l'une NI l'autre classe.
    // Avec !.hidden, un clic dans cette fenêtre était interprété comme « c'est
    // ouvert, referme » — le panneau ne se rouvrait donc jamais.
    const estOuvert = panneau ? panneau.classList.contains("visible") : false;
    if (estOuvert) {
      closeAntivirusPanel();
      setCarouselBtnState(btn, false);
    } else {
      openAntivirusPanel();
      setCarouselBtnState(btn, true);
    }
  });

  // 9. Domotique (Home Assistant)
  bindCarouselAction("carousel-ha-btn", (btn) => {
    toggleHudPanel("ha-panel", btn as HTMLElement, () => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ha_get_states" }));
      }
    });
  });

  // 11. Liste des commandes (Toggle ON/OFF)
  bindCarouselAction("carousel-commands-btn", () => {
    if (!helpOverlayEl) return;
    if (helpOverlayEl.classList.contains("visible")) {
      hideHelpHUD();
    } else {
      showHelpHUD();
    }
  });

  // 12. Clés API — ouvre la page paramètres sur l'onglet Clés API (Toggle ON/OFF)
  bindCarouselAction("carousel-api-btn", () => {
    if (settingsModalEl?.classList.contains("visible")
      && document.querySelector('.settings-nav-item[data-panel="api"]')?.classList.contains("active")) {
      closeSettingsModal();
    } else {
      openSettingsModal("api");
    }
  });

  // 13. Vider Cache
  bindCarouselAction("clear-cache-btn", (btn) => {
    // Refermer le menu déroulant s'il est ouvert (le bouton y figure aussi)
    if (jarvisMenuDropdown) jarvisMenuDropdown.classList.add("hidden");
    if (jarvisMenuBtn) jarvisMenuBtn.classList.remove("active");

    (btn as HTMLButtonElement).disabled = true;
    btn.innerHTML = `<span class="btn-icon">${icone("sablier")}</span> CACHE...`;

    const banner = document.getElementById("update-banner");
    if (banner) {
      banner.style.display = "block";
      banner.style.cursor = "default";
      banner.textContent = "NETTOYAGE DU CACHE EN COURS...";
      banner.style.background = "linear-gradient(90deg, rgba(0,30,80,0.95), rgba(0,100,180,0.85))";
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "clear_cache" }));
    } else {
      setTimeout(() => location.reload(), 1500);
    }
  });

  // 14. Paramètres Globaux (settings-modal)
  bindCarouselAction("settings-button", () => {
    if (settingsModalEl?.classList.contains("visible")) {
      closeSettingsModal();
    } else {
      openSettingsModal();
    }
  });

  // ── SYNCHRONISATION D'ÉTAT DES BOUTONS DU CARROUSEL ───────────────────────────
  // Un panneau peut s'ouvrir/se fermer par bien d'autres chemins que le carrousel :
  // commande vocale, menu déroulant, message WebSocket, bouton ✕ interne...
  // Sans cela, le bouton du dock affichait un état mensonger (allumé alors que le
  // panneau est fermé, et inversement) et il fallait cliquer deux fois pour
  // retrouver la cohérence. On observe donc la classe .hidden des panneaux — seule
  // source de vérité — et on aligne le bouton correspondant.
  const CAROUSEL_PANEL_MAP: Record<string, string[]> = {
    "uninstaller-panel": ["carousel-uninstaller-btn"],
    "winget-panel":      ["carousel-winget-btn"],
    "ha-panel":          ["carousel-ha-btn"],
    "av-panel":          ["carousel-av-scan-btn"],
    "help-overlay":      ["carousel-commands-btn"],
    // La page paramètres unifiée a deux points d'entrée (bouton haut + dock) : les deux
    // doivent refléter son état ouvert/fermé.
    "settings-modal":    ["settings-button", "carousel-api-btn"],
  };

  Object.entries(CAROUSEL_PANEL_MAP).forEach(([panelId, btnIds]) => {
    const panneau = document.getElementById(panelId);
    if (!panneau) return;

    const synchroniser = () => {
      const ouvert = !panneau.classList.contains("hidden")
                  && panneau.style.display !== "none"
                  && getComputedStyle(panneau).display !== "none";
      btnIds.forEach(btnId => setCarouselBtnState(btnId, ouvert));
      refreshCarousel();
    };

    new MutationObserver(synchroniser).observe(panneau, {
      attributes: true,
      attributeFilter: ["class", "style"],
    });

    synchroniser(); // état initial
  });
}
