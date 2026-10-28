const champJeton = document.getElementById("jeton");
const champSites = document.getElementById("sites");
const zoneEtat = document.getElementById("etat");

const TEXTES = {
  non_configure: ["Jeton manquant : collez celui de JARVIS puis enregistrez.", "attente"],
  connexion: ["Connexion à JARVIS… (JARVIS est-il lancé ?)", "attente"],
  connecte: ["Connecté à JARVIS.", "ok"],
  refuse: ["JARVIS refuse cette extension : jeton incorrect, ou JARVIS éteint.", "ko"],
};

async function afficherEtat() {
  try {
    const reponse = await chrome.runtime.sendMessage({ type: "statut" });
    const [texte, classe] = TEXTES[reponse && reponse.etat] || ["État inconnu.", ""];
    zoneEtat.textContent = texte;
    zoneEtat.className = classe;
  } catch {
    zoneEtat.textContent = "Extension en cours de démarrage…";
  }
}

(async () => {
  const r = await chrome.storage.local.get(["jeton", "sites_interdits"]);
  champJeton.value = r.jeton || "";
  champSites.value = r.sites_interdits || "";
  afficherEtat();
  setInterval(afficherEtat, 1500);
})();

document.getElementById("enregistrer").addEventListener("click", async () => {
  await chrome.storage.local.set({ jeton: champJeton.value.trim(), sites_interdits: champSites.value });
  zoneEtat.textContent = "Enregistré.";
  setTimeout(afficherEtat, 800);
});
