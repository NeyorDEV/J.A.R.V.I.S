// Service worker (Manifest V3) : relie JARVIS (ws://localhost:8765) aux onglets.
// Chrome endort un service worker inactif : un « ping » régulier garde la connexion
// ouverte, et une alarme le réveille pour se reconnecter s'il a été arrêté.
let socket = null;
let pingTimer = null;

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  socket = new WebSocket("ws://localhost:8765");

  socket.onopen = () => {
    console.log("[JARVIS EXTENSION] Connecté au serveur local ws://localhost:8765");
    clearInterval(pingTimer);
    pingTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "extension_ping" }));
      }
    }, 20000);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      // Seules les séquences destinées aux pages web : les autres dom_action visent le HUD
      if (data.action === "dom_sequence") {
        // Envoyer la commande à tous les onglets actifs (pour éviter les problèmes de focus de fenêtre)
        chrome.tabs.query({ active: true }, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, data).catch(() => {});
          });
        });
      }
    } catch (e) {
      // Ignorer les messages non-JSON
    }
  };

  socket.onclose = () => {
    clearInterval(pingTimer);
    console.log("[JARVIS EXTENSION] Déconnecté. Tentative de reconnexion dans 3s...");
    setTimeout(connect, 3000);
  };

  socket.onerror = () => {
    socket.close();
  };
}

chrome.alarms.create("jarvis-reconnexion", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarme) => {
  if (alarme.name === "jarvis-reconnexion") connect();
});

// Lancer la connexion au démarrage de l'extension
connect();
