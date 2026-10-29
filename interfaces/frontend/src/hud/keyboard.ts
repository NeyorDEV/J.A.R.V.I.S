import { wsRef } from "../ws_link";
import { keyboardHudEl, keyboardInputEl, keyboardToggleButtonEl } from "./dom_refs";
import { hudState } from "./state";
import { orb } from "./orb_state";

// (Écouteur de #mute-button retiré ici : un second, plus complet, existe plus bas
//  dans le fichier. Les deux étant actifs, un clic envoyait « stop_audio » DEUX
//  fois et forçait l'orbe en « idle » sans attendre la confirmation du backend.)

// NOTE : l'écouteur "click" direct de #subtitle-toggle a été supprimé. Ce bouton
// vit dans le carrousel, dont le gestionnaire délégué exécute déjà son action via
// _carouselActions. Garder les deux faisait basculer l'état DEUX fois par clic →
// le bouton semblait ne rien faire.
// Voir bindCarouselAction("subtitle-toggle") plus bas.
export function initKeyboard(): void {
  const CLE_POSITION = "jarvis-saisie-position";
  let enAnimation = false;

  const placer = (x: number, y: number): void => {
    const maxX = Math.max(0, window.innerWidth - keyboardHudEl.offsetWidth), maxY = Math.max(0, window.innerHeight - keyboardHudEl.offsetHeight);
    Object.assign(keyboardHudEl.style, {
      left: `${Math.min(Math.max(0, x), maxX)}px`, top: `${Math.min(Math.max(0, y), maxY)}px`, right: "auto", bottom: "auto", transform: "none",
    });
  };
  const positionParDefaut = (): void => {
    Object.assign(keyboardHudEl.style, { left: "", top: "", right: "", bottom: "", transform: "" });
  };
  const restaurerPosition = (): void => {
    try {
      const p = JSON.parse(localStorage.getItem(CLE_POSITION) || "null");
      if (p && typeof p.x === "number" && typeof p.y === "number") { placer(p.x, p.y); return; }
    } catch { /* position illisible : emplacement par défaut */ }
    positionParDefaut();
  };

  // La barre part du bouton « Écrire à JARVIS… » (en haut à gauche) et vole jusqu'à sa place, ou y retourne en se fermant.
  const voler = (ouvrir: boolean): Promise<void> => {
    const hud = keyboardHudEl.getBoundingClientRect(), bt = keyboardToggleButtonEl.getBoundingClientRect();
    // transform (et non les propriétés translate/scale) : même rendu sur tous les moteurs ; on garde le transform de repos
    // de la barre (centrage par translateX(-50%) tant qu'elle n'a pas été déplacée)
    const base = getComputedStyle(keyboardHudEl).transform;
    const prefixe = base && base !== "none" ? `${base} ` : "";
    const dx = bt.left + bt.width / 2 - (hud.left + hud.width / 2), dy = bt.top + bt.height / 2 - (hud.top + hud.height / 2);
    const depuis = { transform: `${prefixe}translate(${dx}px, ${dy}px) scale(${bt.width / hud.width}, ${bt.height / hud.height})`, opacity: 1 };
    const repos = { transform: `${prefixe}translate(0px, 0px) scale(1, 1)`, opacity: 1 };
    const anims: Animation[] = [keyboardHudEl.animate(ouvrir ? [depuis, repos] : [repos, depuis], {
      duration: ouvrir ? 1500 : 800, easing: "cubic-bezier(.45,.05,.25,1)", fill: "both",
    })];
    keyboardHudEl.querySelectorAll(".keyboard-hud-inner > *").forEach((el) => {
      anims.push(el.animate(ouvrir ? [{ opacity: 0 }, { opacity: 0, offset: 0.2 }, { opacity: 1, offset: 0.7 }, { opacity: 1 }] : [{ opacity: 1 }, { opacity: 0, offset: 0.4 }, { opacity: 0 }], { duration: ouvrir ? 1500 : 800, fill: "both" }));
    });
    // Halo vif pendant le vol (filter : les règles « !important » de la barre bloqueraient une animation de box-shadow)
    const halo = { filter: "brightness(2.4) saturate(1.3) drop-shadow(0 0 14px rgba(0,229,255,.95))" };
    anims.push(keyboardHudEl.animate(ouvrir ? [halo, { ...halo, offset: 0.8 }] : [halo], { duration: ouvrir ? 1500 : 800, fill: "both" }));
    return Promise.all(anims.map((a) => a.finished)).then(() => anims.forEach((a) => a.cancel())).catch(() => undefined);
  };

  keyboardToggleButtonEl.addEventListener("click", async () => {
    if (enAnimation) return;
    enAnimation = true;
    const ouvrir = !hudState.keyboardEnabled;
    hudState.keyboardEnabled = ouvrir;
    keyboardToggleButtonEl.setAttribute("aria-pressed", ouvrir.toString());
    if (ouvrir) {
      keyboardHudEl.style.display = "block";
      restaurerPosition();
      keyboardInputEl.focus({ preventScroll: true });  // on peut écrire pendant que la barre vole
      await voler(true);
      keyboardInputEl.focus({ preventScroll: true });
    } else {
      await voler(false);
      keyboardHudEl.style.display = "none";
    }
    enAnimation = false;
  });

  // Déplacement libre : on saisit la barre n'importe où sauf sur le champ et le bouton d'envoi ; double-clic = emplacement d'origine
  let prise: { dx: number; dy: number } | null = null;
  keyboardHudEl.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || (e.target as HTMLElement).closest("input, button")) return;
    const r = keyboardHudEl.getBoundingClientRect();
    prise = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    placer(r.left, r.top);
    keyboardHudEl.setPointerCapture(e.pointerId);
    keyboardHudEl.classList.add("deplace");
    e.preventDefault();
  });
  keyboardHudEl.addEventListener("pointermove", (e) => {
    if (prise) placer(e.clientX - prise.dx, e.clientY - prise.dy);
  });
  const lacher = (): void => {
    if (!prise) return;
    prise = null;
    keyboardHudEl.classList.remove("deplace");
    try { localStorage.setItem(CLE_POSITION, JSON.stringify({ x: parseFloat(keyboardHudEl.style.left), y: parseFloat(keyboardHudEl.style.top) })); } catch { /* stockage indisponible */ }
  };
  keyboardHudEl.addEventListener("pointerup", lacher);
  keyboardHudEl.addEventListener("pointercancel", lacher);
  keyboardHudEl.addEventListener("dblclick", (e) => {
    if ((e.target as HTMLElement).closest("input, button")) return;
    positionParDefaut();
    try { localStorage.removeItem(CLE_POSITION); } catch { /* stockage indisponible */ }
  });
  window.addEventListener("resize", () => {
    if (keyboardHudEl.style.left) placer(parseFloat(keyboardHudEl.style.left), parseFloat(keyboardHudEl.style.top));
  });

  const statusLabel = document.getElementById("keyboard-status-label");
  const sendButton = document.getElementById("keyboard-send");
  let statusTimeout: any = null;

  // Message bref sous la barre (« Envoyé », « JARVIS n'est pas connecté »), effacé tout seul
  const flashStatus = (message: string, kind: "ok" | "ko") => {
    if (!statusLabel) return;
    statusLabel.textContent = message;
    statusLabel.dataset.kind = kind;
    if (statusTimeout) clearTimeout(statusTimeout);
    statusTimeout = setTimeout(() => {
      statusLabel.textContent = "";
      delete statusLabel.dataset.kind;
    }, 1400);
  };

  const sendCommand = () => {
    const val = keyboardInputEl.value.trim();
    if (!val) return;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      flashStatus("JARVIS n'est pas connecté", "ko");
      return;
    }
    const folderInput = document.getElementById("wb-folder-input") as HTMLInputElement | null;
    const targetDir = folderInput?.value.trim() || undefined;
    orb.noteText(val);
    wsRef.current.send(JSON.stringify({ type: "user_input", text: val, target_dir: targetDir }));
    keyboardInputEl.value = "";
  };

  keyboardInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendCommand();
    else if (e.key === "Escape") keyboardToggleButtonEl.click();
  });
  sendButton?.addEventListener("click", () => {
    sendCommand();
    keyboardInputEl.focus();
  });
}
