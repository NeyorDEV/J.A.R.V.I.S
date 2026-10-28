// Service worker (Manifest V3) : relie JARVIS (ws://localhost:8765) à l'onglet actif de la fenêtre au premier plan.
//
// Sécurité (v2) :
//  - la connexion doit s'authentifier par un jeton (collé dans les options de l'extension, affiché par JARVIS
//    dans Paramètres › Sécurité) : sans lui, JARVIS ignore cette extension et elle ne reçoit rien ;
//  - les ordres ne visent que l'onglet actif de la fenêtre au premier plan (plus tous les onglets actifs de
//    toutes les fenêtres) ;
//  - les sites listés dans les options (« sites interdits ») ne sont jamais ni lus ni pilotés.
//
// Chrome endort un service worker inactif : un « ping » régulier garde la connexion ouverte, et une alarme le
// réveille pour se reconnecter s'il a été arrêté.
let socket = null;
let pingTimer = null;
let etat = "non_configure"; // non_configure | connexion | connecte | refuse

function definirEtat(nouvelEtat) {
  etat = nouvelEtat;
  const textes = { non_configure: "!", connexion: "…", connecte: "", refuse: "X" };
  const couleurs = { non_configure: "#ffb020", connexion: "#7d95a6", connecte: "#3ddc97", refuse: "#ff5a5f" };
  chrome.action.setBadgeText({ text: textes[etat] || "" });
  chrome.action.setBadgeBackgroundColor({ color: couleurs[etat] || "#7d95a6" });
}

async function lireReglages() {
  const r = await chrome.storage.local.get(["jeton", "sites_interdits"]);
  const interdits = String(r.sites_interdits || "").split(/\r?\n/).map((s) => s.trim().toLowerCase()).filter(Boolean);
  return { jeton: String(r.jeton || "").trim(), interdits };
}

function siteInterdit(url, interdits) {
  try {
    const hote = new URL(url).hostname.toLowerCase();
    return interdits.some((s) => hote === s || hote.endsWith("." + s));
  } catch {
    return false;
  }
}

// Onglet actif de la fenêtre au premier plan (et lui seul)
async function ongletCible() {
  const fenetre = await chrome.windows.getLastFocused();
  const [onglet] = await chrome.tabs.query({ active: true, windowId: fenetre.id });
  return onglet || null;
}

function repondre(id, ok, donnees) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "extension_result", id, ok, data: donnees }));
  }
}

async function demanderAuContenu(onglet, message) {
  try {
    return await chrome.tabs.sendMessage(onglet.id, message);
  } catch {
    return null; // page sans script (page interne du navigateur, boutique d'extensions…)
  }
}

async function executerCommande(id, cmd, params) {
  const { interdits } = await lireReglages();
  try {
    if (cmd === "tabs_list") {
      const fenetre = await chrome.windows.getLastFocused();
      const onglets = await chrome.tabs.query({});
      repondre(id, true, onglets.filter((t) => !siteInterdit(t.url || "", interdits)).slice(0, 40).map((t) => ({
        id: t.id,
        titre: String(t.title || "").slice(0, 80),
        site: (() => { try { return new URL(t.url).hostname; } catch { return ""; } })(),
        actif: !!t.active && t.windowId === fenetre.id,
        sonore: !!t.audible,
      })));
      return;
    }
    if (cmd === "tab_activate") {
      const onglets = await chrome.tabs.query({});
      const cherche = String(params.recherche || "").toLowerCase();
      const trouve = onglets.find((t) => t.id === params.id) ||
        onglets.find((t) => cherche && (String(t.title || "").toLowerCase().includes(cherche) || String(t.url || "").toLowerCase().includes(cherche)));
      if (!trouve || siteInterdit(trouve.url || "", interdits)) return repondre(id, false, "onglet introuvable");
      await chrome.tabs.update(trouve.id, { active: true });
      await chrome.windows.update(trouve.windowId, { focused: true });
      return repondre(id, true, { titre: String(trouve.title || "").slice(0, 80) });
    }
    const onglet = await ongletCible();
    if (!onglet) return repondre(id, false, "aucun onglet actif");
    if (siteInterdit(onglet.url || "", interdits)) return repondre(id, false, "site interdit dans les options de l'extension");
    if (cmd === "tab_close") {
      await chrome.tabs.remove(onglet.id);
      return repondre(id, true, { titre: String(onglet.title || "").slice(0, 80) });
    }
    if (cmd === "media") {
      let reponse = await demanderAuContenu(onglet, { ext: "media", action: params.action });
      if (!reponse || !reponse.nombre) {
        // Pas de lecteur dans l'onglet actif : l'onglet qui joue du son, s'il y en a un
        const [sonore] = await chrome.tabs.query({ audible: true });
        if (sonore && !siteInterdit(sonore.url || "", interdits)) {
          reponse = await demanderAuContenu(sonore, { ext: "media", action: params.action });
        }
      }
      return repondre(id, !!(reponse && reponse.nombre), reponse || "aucun lecteur vidéo ou audio trouvé");
    }
    if (cmd === "page_read") {
      const reponse = await demanderAuContenu(onglet, { ext: "read" });
      return repondre(id, !!reponse, reponse || "page illisible");
    }
    repondre(id, false, "commande inconnue");
  } catch (e) {
    repondre(id, false, String(e).slice(0, 120));
  }
}

async function connecter() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const { jeton } = await lireReglages();
  if (!jeton) {
    definirEtat("non_configure");
    return; // rien à faire tant que le jeton n'est pas saisi dans les options
  }
  definirEtat("connexion");
  socket = new WebSocket("ws://localhost:8765");

  socket.onopen = () => {
    socket.send(JSON.stringify({ type: "extension_hello", token: jeton }));
    clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "extension_ping" }));
      }
    }, 20000);
  };

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "extension_ok") {
        definirEtat("connecte");
        return;
      }
      if (etat !== "connecte") return;
      if (data.action === "ext_cmd") {
        executerCommande(data.id, data.cmd, data.params || {});
      } else if (data.action === "dom_sequence") {
        // Séquences destinées aux pages web : l'onglet actif de la fenêtre au premier plan seulement
        const onglet = await ongletCible();
        const { interdits } = await lireReglages();
        if (onglet && !siteInterdit(onglet.url || "", interdits)) {
          chrome.tabs.sendMessage(onglet.id, data).catch(() => {});
        }
      }
    } catch (e) {
      // Ignorer les messages non-JSON
    }
  };

  socket.onclose = () => {
    clearInterval(pingTimer);
    if (etat === "connexion") definirEtat("refuse"); // fermée avant « extension_ok » : jeton refusé ou JARVIS éteint
    else if (etat === "connecte") definirEtat("connexion");
    setTimeout(connecter, 3000);
  };

  socket.onerror = () => {
    socket.close();
  };
}

chrome.alarms.create("jarvis-reconnexion", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarme) => {
  if (alarme.name === "jarvis-reconnexion") connecter();
});

// Jeton ou liste de sites modifiés dans les options : on repart d'une connexion propre
chrome.storage.onChanged.addListener((changements) => {
  if (changements.jeton) {
    if (socket) socket.close();
    socket = null;
    connecter();
  }
});

chrome.runtime.onMessage.addListener((message, expediteur, repondreOptions) => {
  if (message && message.type === "statut") {
    repondreOptions({ etat });
  }
});

definirEtat("non_configure");
connecter();
