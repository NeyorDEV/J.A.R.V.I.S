// Crée ou met à jour le bandeau HUD visible de J.A.R.V.I.S
function showJarvisHUD(message, submessage = "") {
  let hud = document.getElementById("jarvis-hud-banner");
  if (!hud) {
    hud = document.createElement("div");
    hud.id = "jarvis-hud-banner";
    Object.assign(hud.style, {
      position: "fixed",
      top: "20px",
      right: "20px",
      padding: "14px 22px",
      background: "rgba(10, 25, 45, 0.95)",
      border: "1px solid #00e5ff",
      borderRadius: "10px",
      boxShadow: "0 0 25px rgba(0, 229, 255, 0.5)",
      color: "#00e5ff",
      fontFamily: "'Courier New', monospace",
      fontSize: "12px",
      zIndex: "999999999",
      pointerEvents: "none",
      transition: "all 300ms ease",
      lineHeight: "1.5"
    });
    document.body.appendChild(hud);
  }
  hud.textContent = "";
  const titre = document.createElement("div");
  Object.assign(titre.style, { fontWeight: "bold", marginBottom: "6px", letterSpacing: "1px", color: "#00e5ff" });
  titre.textContent = "◈ J.A.R.V.I.S // AUTOMATION_AGENT";
  const corps = document.createElement("div");
  Object.assign(corps.style, { color: "#ffffff", fontSize: "13px", fontWeight: "500" });
  corps.textContent = String(message);
  hud.append(titre, corps);
  if (submessage) {
    const sous = document.createElement("div");
    Object.assign(sous.style, { fontSize: "10px", color: "rgba(0,229,255,0.75)", marginTop: "6px", borderTop: "1px solid rgba(0,229,255,0.2)", paddingTop: "6px", wordBreak: "break-all", whiteSpace: "pre-line" });
    sous.textContent = String(submessage);
    hud.append(sous);
  }
  hud.style.opacity = "1";
}

function hideJarvisHUD() {
  const hud = document.getElementById("jarvis-hud-banner");
  if (hud) {
    hud.style.opacity = "0";
  }
}

// Crée et retourne le curseur virtuel de JARVIS sur la page
function getOrCreateVirtualCursor() {
  let cursor = document.getElementById("jarvis-web-cursor");
  if (!cursor) {
    cursor = document.createElement("div");
    cursor.id = "jarvis-web-cursor";
    Object.assign(cursor.style, {
      position: "fixed",
      width: "28px",
      height: "28px",
      borderRadius: "50%",
      background: "radial-gradient(circle, #00e5ff 0%, rgba(0,100,255,0.4) 70%)",
      boxShadow: "0 0 20px #00e5ff, inset 0 0 10px #ffffff",
      zIndex: "9999999",
      pointerEvents: "none",
      transition: "all 800ms cubic-bezier(0.25, 1, 0.5, 1)",
      left: `${window.innerWidth / 2}px`,
      top: `${window.innerHeight / 2}px`,
      transform: "translate(-50%, -50%) scale(1)",
      opacity: "0",
      display: "block"
    });
    document.body.appendChild(cursor);
  }
  return cursor;
}

// Fonction de temporisation
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Exécute une action DOM individuelle
async function executeSingleAction(step) {
  const actionType = step.action_type || step.action;
  const { selector, text } = step;

  if (actionType === "open_url" && text) {
    console.log(`[JARVIS] Navigation vers : ${text}`);
    window.location.href = text;
    // Laisser le temps à la page de charger
    await wait(3000);
    return;
  }

  let element = null;
  
  // Fonction pour trouver le premier élément visible correspondant au sélecteur
  const findVisibleElement = () => {
    let currentSelector = selector;
    
    // Nettoyer les quotes échappées envoyées par l'IA (ex: \"s-search-result\")
    currentSelector = currentSelector.replace(/\\"/g, '"');

    // Support générique pour le pseudo-sélecteur [item-number=N] (1-indexed) - EXTRACATION EN PRIORITÉ !
    let targetIndex = 0; // Par défaut, premier élément (index 0)
    const indexMatch = currentSelector.match(/\[item-number=(\d+)\]/);
    if (indexMatch) {
      targetIndex = parseInt(indexMatch[1]) - 1; // 1-indexed vers 0-indexed
      currentSelector = currentSelector.replace(/\[item-number=\d+\]/, ""); // Retirer le pseudo-sélecteur pour la recherche DOM
    }

    // Résolution robuste et fallbacks pour Amazon
    if (window.location.hostname.includes("amazon")) {
      if (currentSelector.includes("s-search-result")) {
        // En cascade : sélecteur original nettoyé, sélecteurs d'attributs sans préfixe de tag, classe de carte produit, et enfin n'importe quel titre d'article
        currentSelector = `${currentSelector}, [data-component-type="s-search-result"] h2 a, [data-asin] h2 a, .s-result-item h2 a, .s-card-container h2 a, h2 a.a-link-normal`;
      } else if (currentSelector.includes("twotabsearchtextbox")) {
        currentSelector = "input#twotabsearchtextbox, input[name='field-keywords'], input.nav-input";
      } else if (currentSelector.includes("nav-search-submit-button")) {
        currentSelector = "input#nav-search-submit-button, input.nav-input[type='submit'], #nav-search-submit-text + input";
      } else if (currentSelector.includes(".s-image")) {
        // EXCLUSION STRICTE : Amazon applique parfois la classe '.s-image' sur de petites icônes comme "Fonctionne avec Alexa".
        // Nous restreignons le ciblage UNIQUEMENT aux vraies images principales de produits organiques pour éviter tout faux-positif.
        currentSelector = ".s-image-container img.s-image, .s-product-image-container img.s-image, .s-image-overlay-parent img.s-image";
      }
    }

    showJarvisHUD("RECHERCHE D'ÉLÉMENT", `Sélecteur : ${currentSelector}\nCible index : ${targetIndex}`);
    console.log(`[JARVIS] Recherche élément avec sélecteur résolu : ${currentSelector} (Cible index: ${targetIndex})`);
    const elements = document.querySelectorAll(currentSelector);
    let visibleCount = 0;
    for (let el of elements) {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        if (visibleCount === targetIndex) {
          return el;
        }
        visibleCount++;
      }
    }
    return null;
  };

  const cursor = getOrCreateVirtualCursor();
  
  // Rendre le curseur visible AVANT de chercher l'élément, pour montrer que JARVIS travaille
  if (cursor.style.opacity === "0") {
    cursor.style.left = `${window.innerWidth / 2}px`;
    cursor.style.top = `${window.innerHeight / 2}px`;
    cursor.style.opacity = "1";
    await wait(200);
  }

  // Animation de recherche (pulsation rapide)
  cursor.style.transform = "translate(-50%, -50%) scale(1.2)";
  
  element = findVisibleElement();
  
  // Attendre jusqu'à 8 secondes que l'élément apparaisse (pour les grosses pages comme Amazon)
  let retries = 0;
  while (!element && retries < 32) {
    await wait(250);
    element = findVisibleElement();
    retries++;
  }

  // Remise à l'échelle normale
  cursor.style.transform = "translate(-50%, -50%) scale(1)";

  if (!element) {
    console.log(`[JARVIS] Élément introuvable pour le sélecteur : ${selector}`);
    showJarvisHUD("ERREUR_CIBLAGE", `Élément introuvable : ${selector}`);
    return;
  }

  // Mettre en surbrillance l'élément ciblé pour que l'utilisateur comprenne
  const originalOutline = element.style.outline;
  const originalBoxShadow = element.style.boxShadow;
  element.style.outline = "3px solid #00ffaa";
  element.style.boxShadow = "0 0 15px #00ffaa";
  
  const elDesc = `<${element.tagName.toLowerCase()} class="${element.className}" id="${element.id}">`;
  showJarvisHUD(`CIBLAGE : ${actionType.toUpperCase()}`, `Élément résolu : ${elDesc}`);

  // Calculer les coordonnées de l'élément cible via le DOM
  const rect = element.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;

  // Glissement du curseur virtuel
  cursor.style.left = `${x}px`;
  cursor.style.top = `${y}px`;
  
  // Attendre la fin du glissement (800ms) + délai d'attente (500ms comme demandé par l'utilisateur !)
  await wait(800 + 500);

  // Retirer la surbrillance juste avant l'action
  element.style.outline = originalOutline;
  element.style.boxShadow = originalBoxShadow;
  hideJarvisHUD();

  if (actionType === "click") {
    // Animation de clic physique
    cursor.style.transform = "translate(-50%, -50%) scale(0.6)";
    await wait(150);
    cursor.style.transform = "translate(-50%, -50%) scale(1)";
    
    // Clic DOM ultra-robuste (simule un vrai comportement humain pour passer les sécurités SPA)
    element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
    await wait(50);
    element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
    element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    
    // Fallback pour les boutons de soumission (contourne les sécurités isTrusted)
    if ((element.type === "submit" || element.tagName === "BUTTON") && element.form) {
      try { element.form.requestSubmit(); } catch(e) { element.form.submit(); }
      console.log(`[JARVIS] Formulaire soumis sur : ${selector}`);
      return true; // Signale qu'une navigation est en cours
    } else {
      try { element.click(); } catch(e) {}
      if (element.tagName === "A" && element.href) {
        return true; // Signale qu'une navigation est en cours (lien cliqué)
      }
    }
    
    console.log(`[JARVIS] Clic effectué sur : ${selector}`);
  } else if (actionType === "type") {
    // Focus l'élément
    element.focus();
    
    // Saisie lettre par lettre (100ms par touche !)
    const valueToType = text || "";
    element.value = "";
    for (let char of valueToType) {
      element.value += char;
      element.dispatchEvent(new Event("input", { bubbles: true }));
      await wait(100);
    }
    element.dispatchEvent(new Event("change", { bubbles: true }));
    
    // Simuler l'appui sur "Entrée" pour valider au cas où le site écoute l'événement
    await wait(200);
    element.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keypress', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    element.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    
    console.log(`[JARVIS] Texte saisi dans : ${selector}`);
  }

  // Petit délai post-action
  await wait(500);
}

// Gère la réception des commandes de l'extension
chrome.runtime.onMessage.addListener(async (message) => {
  if (message.action === "dom_sequence" && message.steps) {
    let navigationTriggered = false;
    for (let i = 0; i < message.steps.length; i++) {
      if (navigationTriggered) break; // Stoppe l'exécution locale, la nouvelle page prendra le relais
      
      // Sauvegarder les étapes SUIVANTES dans le storage Chrome (survit aux changements de sous-domaines)
      await chrome.storage.local.set({ "jarvis_pending_sequence": { etapes: message.steps.slice(i + 1), t: Date.now() } });
      navigationTriggered = await executeSingleAction(message.steps[i]);
      if (!navigationTriggered) await wait(800); // Petite pause vitale
    }
    // Séquence terminée sans rechargement
    if (!navigationTriggered) {
      await chrome.storage.local.remove("jarvis_pending_sequence");
    }
  } else if (message.type === "dom_action") {
    await executeSingleAction(message);
  }

  // Faire disparaître le curseur virtuel après 2 secondes d'inactivité
  setTimeout(() => {
    const cursor = document.getElementById("jarvis-web-cursor");
    if (cursor) {
      cursor.style.left = `${window.innerWidth / 2}px`;
      cursor.style.top = `${window.innerHeight / 2}px`;
      setTimeout(() => {
        cursor.style.opacity = "0";
      }, 800);
    }
  }, 2000);
});

// Auto-reprise de la séquence après un rechargement de page (navigation)
(async () => {
  try {
    const data = await chrome.storage.local.get("jarvis_pending_sequence");
    const attente = data.jarvis_pending_sequence;
    const frais = attente && Array.isArray(attente.etapes) && Date.now() - attente.t < 30000;
    const steps = frais ? attente.etapes : [];
    if (attente && !frais) await chrome.storage.local.remove("jarvis_pending_sequence"); // périmée : on l'oublie
    
    if (steps && steps.length > 0) {
      console.log("[JARVIS] Reprise de la séquence depuis le stockage global...");
      await wait(2500); // Attendre que le nouveau DOM soit vraiment stable
      
      let navigationTriggered = false;
      for (let i = 0; i < steps.length; i++) {
        if (navigationTriggered) break;
        await chrome.storage.local.set({ "jarvis_pending_sequence": { etapes: steps.slice(i + 1), t: Date.now() } });
        navigationTriggered = await executeSingleAction(steps[i]);
        if (!navigationTriggered) await wait(800);
      }
      if (!navigationTriggered) {
        await chrome.storage.local.remove("jarvis_pending_sequence");
      }
      
      // Faire disparaître le curseur virtuel après la séquence
      setTimeout(() => {
        const cursor = document.getElementById("jarvis-web-cursor");
        if (cursor) {
          cursor.style.left = `${window.innerWidth / 2}px`;
          cursor.style.top = `${window.innerHeight / 2}px`;
          setTimeout(() => {
            cursor.style.opacity = "0";
          }, 800);
        }
      }, 2000);
    }
  } catch (e) {
    console.error("[JARVIS] Erreur de reprise:", e);
    try { await chrome.storage.local.remove("jarvis_pending_sequence"); } catch(ex) {}
  }
})();

// Demandes directes de JARVIS (via background.js) : médias de la page et texte de la page
chrome.runtime.onMessage.addListener((message, expediteur, repondre) => {
  if (!message || !message.ext) return false;
  if (message.ext === "media") {
    const lecteurs = [...document.querySelectorAll("video, audio")].filter((m) => m.readyState > 0 || !m.paused);
    const action = message.action;
    const enLecture = lecteurs.filter((m) => !m.paused);
    if (action === "pause" || (action === "toggle" && enLecture.length)) {
      enLecture.forEach((m) => m.pause());
    } else if (action === "play" || action === "toggle") {
      const cible = lecteurs.find((m) => m.paused);
      if (cible) cible.play().catch(() => {});
    } else if (action === "mute" || action === "unmute") {
      lecteurs.forEach((m) => { m.muted = action === "mute"; });
    }
    repondre({ nombre: lecteurs.length, action });
    return false;
  }
  if (message.ext === "read") {
    const bloc = document.querySelector("main, article");
    let texte = bloc && bloc.innerText && bloc.innerText.length > 400 ? bloc.innerText : (document.body ? document.body.innerText : "");
    texte = texte.replace(/\s+/g, " ").trim().slice(0, 8000);
    repondre({ titre: document.title, url: location.href, texte });
    return false;
  }
  return false;
});
