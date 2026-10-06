import { helpOverlayEl } from "./dom_refs";

const HELP_COMMANDS = [
  // Heure & Date
  "Quelle heure est-il ?",
  "On est quel jour ?",
  "Quelle date sommes-nous ?",
  "C'est quel mois ?",
  "Quelle année est-ce ?",
  "J'ai quel âge ?",
  
  // Système PC
  "Niveau de la batterie",
  "Niveau de charge du PC",
  "Utilisation du CPU",
  "Charge du processeur",
  "Utilisation de la RAM",
  "Mémoire vive disponible",
  "Allumé depuis combien de temps ?",
  "PC allumé depuis quand ?",
  "Uptime système",
  "Volume monte",
  "Volume baisse",
  "Coupe le son",
  "Volume à 50%",
  "Remets le son",
  "Prends une capture d'écran",
  "Prends un screenshot",
  "Vide la corbeille",
  "Nettoie la corbeille",
  "Éteins le PC dans 5 minutes",
  "Redémarre le PC",
  "Mets le PC en veille",
  "Verrouille le PC",
  "Annule l'arrêt",

  // Gestion des Fichiers & Dossiers
  "Ouvre mon Bureau",
  "Ouvre mes Documents",
  "Ouvre mes Téléchargements",
  "Ouvre mes Images",
  "Ouvre le dossier Documents",
  "Ouvre le fichier photo.jpg",
  "Range mes dossiers",
  "Mosaïque dossiers",
  "Trie mes fichiers par type",
  "Trie mes fichiers par date",
  "Crée le dossier Projets",
    "Renomme ancien_dossier en nouveau_dossier",
  "Déplace photo.jpg vers Images",
  "Analyse le fichier de notes",

  // Applications & Jeux
  "Ouvre la calculatrice",
  "Ouvre Notepad",
  "Ouvre Paint",
  "Ouvre Chrome",
  "Ouvre le gestionnaire de tâches",
  "Ferme la calculatrice",
  "Mode Boulot !",
  "Mode Gaming",
  "On joue !",
  "On joue à Rocket League",

  // Contrôle de l'Interface Graphique (HUD)
  "Ouvre les paramètres",
  "Ferme les paramètres",
  "Active les sous-titres",
  "Active le clavier",
  "Ferme la météo",
  "Montre le widget Calendrier",
  "Active le mode hologramme",
  "Active le mode AR",
  "Active le miroir holo",

  // Minuteurs Interactifs
  "Mets un minuteur de 10 minutes",
  "Lance un timer de 5 minutes",
  "Ajoute 2 minutes au minuteur",
  "Retire 1 minute au minuteur",
  "Annule le minuteur",
  "Combien de temps reste-t-il ?",

  // Explorateur Spatial 3D & Carte 3D
  "Ouvre l'explorateur spatial",
  "Affiche mes fichiers en 3D",
  "Affiche ma maison en 3D",
  "Affiche la carte domotique 3D",
  
  // Cortex Neuronal 3D
  "Affiche ton cortex",
  "Ouvre le cortex neuronal",
  "Cherche dans mon cortex la musique",
  "Trouve dans le cortex la météo",
  "Lis ce souvenir",
  "Raconte cette mémoire",

  // Échecs 3D
  "On joue aux échecs",
  "Lance une partie d'échecs",
  "Lance la partie avec les noirs",
  "Réinitialise la partie d'échecs",
  "Quitte les échecs",
  "Lance la partie niveau moyen",
  "Lance la partie sans chrono",

  // Globe Terrestre 3D
  "Affiche la Terre",
  "Vue depuis l'espace",
  "Zoom sur la Terre",
  "Vol vers Tokyo",
  "Affiche ma position",
  "Où suis-je ?",
  "Trajet de Paris à Lyon",
  "Ferme le globe",

  // Télévision & Multimédia
  "Allume la télé",
  "Éteins la télé",
  "Lance Netflix sur la télé",
  "Mets du rock sur YouTube (Télé)",
  "Pause la télé",
  "Reprends la télé",
  "Monte le son de la télé",

    // Musique Spotify & Deezer
  "Lance Spotify",
  "Joue Billie Jean sur Spotify",
  "Suivant sur Spotify",
  "Volume Spotify monte",
  "Ouvre Deezer",
  "Recherche Michael Jackson sur Deezer",
  "Mets de la musique sur YouTube (PC)",

  // HomePod Mini & Audio Casque
  "Passe ta voix sur le HomePod",
  "Bascule sur le casque",
  "Règle le volume du HomePod à 50%",
  "Pause le HomePod",

  // Autopilote Web & Vision IA
  "Cherche un hôtel à Annecy sur Booking",
  "Cherche une PS5 moins de 400€ à Lyon",
  "Cherche les vols Paris-Barcelone sur Kayak",
  "Ferme le navigateur",
  "Lance l'autopilote OS",

  // Domotique Home Assistant
  "Allume la lumière du Salon",
  "Éteins la lumière du Bureau",
  "Mets la lumière en Bleu",
  "Règle la luminosité à 80%",
  "Quelle est la température dans le Salon ?",
  "Quel est le taux d'humidité dans le Bureau ?",
  "Combien d'abonnés sur TikTok ?",
  "Anniversaires du jour",
  "Active la scène Cinéma",
  "Désactive l'alarme",
  "Verrouille la porte",
  "Aspire la maison",
  "Retour à la base de l'aspirateur",

    // Intelligence & Assistance IA
  "Recherche approfondie sur l'intelligence artificielle",
  "Analyse mon écran",
  "Aide-moi",
  "Lance la caméra",
  "Regarde-moi",
  "Génère une image d'un coucher de soleil",
  "Dessine-moi une voiture de sport",
  "Tape le texte dicté",
  "Souviens-toi que j'aime le café",
  "Qu'est-ce que tu sais sur moi ?",
  "Liste ma mémoire",
  "Cherche dans mes souvenirs l'anniversaire",

  // Google Workspace
  "Crée un Google Doc intitulé Réunion",
  "Lis le contenu de mon Google Doc",
  "Lis mes nouveaux emails",
  "Lis le détail du dernier email",
  "Envoie un email à neyor@example.com",
  "Montre mon agenda",
  "Quels sont mes événements ?",
  "Ouvre mon Google Drive",
  "Ajoute une tâche faire les courses",

  // Sécurité & Mises à Jour
  "Analyse mon PC",
  "Lance le scan antivirus",
  "Active la protection en temps réel",
  "Mets à jour mes logiciels",
  "Lance winget",

  // Compétences Dynamiques / Démonstrations
  "Crée la compétence recherche_web",
  "Liste toutes tes compétences",
  "Lance la démo",
  "Écris le mot JARVIS",

    // Configuration & Flux
  "Prends la voix d'homme",
  "Prends la voix de femme",
  "Active le mode Iron Man",
  "Silence !",
  "Tais-toi !"
];

// ── Help HUD Logic ───────────────────────────────────────────────────────────
// Handle du masquage automatique de la liste des commandes (voir showHelpHUD)
let helpAutoHideTimer: number | null = null;

export function hideHelpHUD() {
  if (!helpOverlayEl) return;
  if (helpAutoHideTimer !== null) {
    clearTimeout(helpAutoHideTimer);
    helpAutoHideTimer = null;
  }
  // On pilote la classe : le CSS #help-overlay.visible porte un display !important
  // qu'un simple style.display = "none" inline ne peut pas battre.
  helpOverlayEl.classList.remove("visible");
  helpOverlayEl.classList.add("hidden");
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
}

export function showHelpHUD() {
  if (!helpOverlayEl) return;
  ["display", "opacity", "visibility", "z-index"].forEach(p => helpOverlayEl.style.removeProperty(p));
  helpOverlayEl.classList.remove("hidden");
  helpOverlayEl.classList.add("visible");
  helpOverlayEl.innerHTML = "";
    // Select 16 random commands (8 on each side) to keep them visible within the viewport
  const shuffled = [...HELP_COMMANDS].sort(() => 0.5 - Math.random());
  const selected = shuffled.slice(0, 16);

  selected.forEach((cmd, i) => {
    const isRight = i % 2 === 1;
    const widget = document.createElement("div");
    widget.className = `help-widget ${isRight ? 'right' : ''}`;

    // Grid-like positioning with absolute geometric alignment (no overlap)
    const row = Math.floor(i / 2);
    const top = 120 + (row * 84);
    widget.style.top = `${top}px`;

    // Position them on the left or right side with identical margins
    const sideOffset = 45;
    if (isRight) widget.style.right = `${sideOffset}px`;
    else widget.style.left = `${sideOffset}px`;

    // Cinematic reveal delay (shorter timeout for faster entrance)
    widget.style.transitionDelay = `${(i % 5) * 0.15}s`;

    widget.innerHTML = `
      <div class="help-widget-title" style="display:flex; justify-content: space-between;">
        <span>CAPACITÉ ${Math.floor(Math.random() * 999)}</span>
        <span style="opacity:0.3">[SYNC]</span>
      </div>
      <div class="help-widget-cmd">"${cmd}"</div>
    `;

    helpOverlayEl.appendChild(widget);

    // Cinematic reveal (set transition visible immediately or on next tick)
    requestAnimationFrame(() => {
      setTimeout(() => widget.classList.add("visible"), 50);
    });
  });

  // Masquage automatique au bout de 20 s.
  // Le handle est mémorisé et annulé à chaque ouverture/fermeture : sans cela,
  // ouvrir puis refermer puis rouvrir la liste faisait survivre le timer du
  // PREMIER clic, qui refermait 20 s plus tard l'overlay fraîchement rouvert.
  if (helpAutoHideTimer !== null) clearTimeout(helpAutoHideTimer);
  helpAutoHideTimer = window.setTimeout(() => {
    const widgets = document.querySelectorAll(".help-widget");
    widgets.forEach((w, i) => {
      setTimeout(() => w.classList.remove("visible"), i * 100);
    });
    helpAutoHideTimer = window.setTimeout(() => hideHelpHUD(), 2000);
  }, 20000);
}
