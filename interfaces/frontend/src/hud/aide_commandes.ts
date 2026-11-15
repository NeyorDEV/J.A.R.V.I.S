// Index de l'aide et de la palette de commandes : les phrases qu'on peut dire à JARVIS, rangées à la main dans l'une des 21 catégories
// du cylindre (orb_themes.ts). Chaque phrase est un exemple qui marche (resolvers de backend/plugins, commandes locales, actions de
// l'IA), écrits comme des phrases complètes. Pour ajouter une commande : l'écrire dans la bonne catégorie.
// La sous-catégorie est celle que la roue de recherche choisirait pour la phrase (même `choisir`), si elle tombe dans la même catégorie.
import { CATEGORIES, choisir } from "../orb_themes";

export interface CommandeAide { texte: string; cat: string; sous: string }

const PAR_CATEGORIE: Record<string, string[]> = {
  "MUSIQUE": [
    "Lance Spotify", "Mets de la musique", "Joue du Daft Punk", "Pause", "Reprends la musique", "Morceau suivant", "Morceau précédent",
    "Monte le volume de Spotify", "Ouvre Deezer", "Mets de la musique sur Deezer", "Lance ma playlist Deezer", "Recherche Stromae sur Deezer", 
    "Mets de la musique sur YouTube", "Montre la musique", "Cache la musique",
    "Passe ta voix sur le HomePod", "Repasse sur le casque", "Règle le volume du HomePod à 30", "Pause le HomePod", "Musique suivante sur le HomePod",
  ],
  "TÉLÉ": [
    "Allume la télé", "Éteins la télé", "Lance Netflix sur la télé", "Lance YouTube sur la télé", "Lance Disney+ sur la télé", "Mets Squeezie sur YouTube sur la télé",
    "Pause la télé", "Reprends la télé", "Monte le son de la télé", "Baisse un peu le son de la télé", "Retour à l'accueil de la télé",
  ],
  "JEUX": [
    "Lance Portal sur Steam", "Mes jeux Steam", "Ouvre ma bibliothèque Steam", "On joue à Rocket League", "Ouvre Steam", "Mode gaming",
  ],
  "MAISON": [
    "Allume la lumière du salon", "Éteins la lumière de la chambre", "Mets la lumière en bleu", "Règle la luminosité à 50 %",
    "Allume la prise du bureau", "Éteins la prise du sapin", "Quelle est la température dans le salon ?", "Quel est le taux d'humidité dans le bureau ?",
    "Règle le thermostat à 20 degrés", "Active la scène cinéma", "Verrouille la porte", "Déverrouille la porte",
    "Active la simulation de présence", "Lance le nettoyage", "Aspire la maison", "Arrête l'aspirateur", "Retour à la base",
    "Quelle est la puissance consommée à la maison ?", "Combien ai-je consommé d'énergie ce mois-ci ?", "Quelle est la batterie de mon téléphone ?",
    "Quand a eu lieu le dernier ramassage des œufs ?", "Ferme le panneau température",
  ],
  "MÉTÉO": [
    "Quel temps fait-il ?", "Montre-moi la météo", "Quelle est la météo de demain ?", "Quelle est la météo de la semaine ?", "Va-t-il pleuvoir demain ?",
    "Faut-il un parapluie ?", "Quelle température fait-il dehors ?", "Cache la météo", "Ferme la météo",
  ],
  "ALARMES": [
    "Mets un minuteur de 10 minutes", "Annule le minuteur", "Combien de temps reste-t-il ?",
    "Combien de minuteurs sont actifs ?", "Rappelle-moi d'appeler Léo à 18 heures", "Réveille-moi à 7 heures", "Liste mes alarmes",
    "Annule l'alarme de 7 heures", "Annule toutes les alarmes",
  ],
  "AGENDA": [
    "Montre mon agenda", "Quels sont mes prochains rendez-vous ?", "Quels sont mes événements ?", "Crée un événement dentiste demain à 14 heures",
    "Modifie l'événement dentiste", "Supprime l'événement dentiste", "Montre le calendrier", "Cache le calendrier",
    "Ajoute une tâche dans mes tâches : appeler Léo", "Liste mes tâches Google Tasks", "Valide la tâche appeler Léo", "Supprime la tâche appeler Léo",
    "Ajoute une tâche : acheter du pain", "Mes tâches", "Efface mes tâches", "Qui a son anniversaire aujourd'hui ?",
  ],
  "MAIL": [
    "Lis mes nouveaux emails", "Lis le détail du dernier email", "Envoie un email à Léo au sujet de la réunion", "Réponds au dernier email",
    "Archive le dernier email", "Supprime le dernier email",
  ],
  "DOCUMENTS": [
    "Crée un Google Doc intitulé Réunion", "Écris dans mon Google Doc", "Lis le contenu de mon Google Doc", "Crée un Google Sheet intitulé Budget",
    "Ajoute une ligne dans mon Google Sheet", "Lis les données de mon Google Sheet de A1 à C10", "Ouvre mon Google Drive", "Cherche sur mon Drive le CV",
    "Téléverse un fichier sur mon Drive", "Partage le document Budget avec Léo", "Crée un dossier sur mon Drive",
    "Crée une présentation PowerPoint sur le climat", "Rédige un rapport Word sur la sécurité", "Crée un tableau Excel des dépenses", "Génère un PDF sur les volcans",
    "Fusionne les PDF de mon bureau", "Analyse le fichier notes",
  ],
  "SYSTÈME": [
    "Niveau de la batterie", "Utilisation du processeur", "Utilisation de la RAM", "Depuis combien de temps le PC est allumé ?",
    "Monte le volume", "Baisse le volume", "Coupe le son", "Volume à 50 %", "Remets le son", "Prends une capture d'écran", "Vide la corbeille",
    "Éteins le PC dans 5 minutes", "Redémarre le PC", "Mets le PC en veille", "Verrouille le PC", "Annule l'arrêt",
    "Ouvre mon Bureau", "Ouvre mes Documents", "Ouvre mes Téléchargements", "Ouvre mes Images", "Ouvre le dossier Projets", "Ouvre le fichier notes",
    "Range mes dossiers", "Trie complet", "Crée le dossier Projets",
    "Renomme ancien en nouveau", "Déplace photo vers Images",
    "Ouvre la calculatrice", "Ouvre Notepad", "Ouvre Paint", "Ouvre le gestionnaire de tâches", "Ferme Chrome", "Mode boulot",
    "Lance l'autopilote OS : ouvre le bloc-notes",
  ],
  "LOGICIELS": [
    "Mets à jour mes logiciels", "Lance les mises à jour", "Lance winget", "Ouvre le désinstallateur", "Désinstalle un logiciel",
  ],
  "SÉCURITÉ": [
    "Analyse mon PC", "Lance le scan antivirus", "Active la protection en temps réel", "Désactive la protection antivirus",
  ],
  "INTERNET": [
    "Recherche approfondie sur l'intelligence artificielle", "Ouvre Chrome", "Ouvre Firefox", "Ouvre YouTube et recherche Stromae",
    "Ouvre Amazon, cherche un clavier et clique sur le premier article", "Cherche un hôtel avec spa à Annecy sur Booking",
    "Va sur Leboncoin et cherche une PS5", "Cherche les vols Paris-Barcelone sur Kayak", "Ferme le navigateur", "Stop l'autopilote",
    "Mets la vidéo en pause", "Reprends la vidéo", "Coupe le son de la vidéo", "Quels sont mes onglets ?", "Va sur l'onglet YouTube", "Ferme cet onglet",
    "Résume cette page", "Combien d'abonnés sur TikTok ?",
  ],
  "IMAGES": [
    "Génère une image d'un coucher de soleil", "Dessine-moi une voiture de sport", "Montre-moi des images de chats", "Cherche des photos de Paris",
    "Modifie une image de mon PC", "Retouche une photo",
  ],
  "CRÉATION": [
    "Crée la compétence météo pour dire la météo", "Liste mes compétences", "Supprime la compétence météo", "Exécute la compétence météo",
    "Mes skills", "Autorise le skill espace disque", "Lance le skill espace disque",
    "Crée un site web de portfolio", "Crée une application de notes", "Lance l'essaim", "Crée un plugin pour Notion",
  ],
  "DISCORD": [
    "Envoie salut à tous dans le salon annonces", "Écris à Léo sur Discord que je suis en retard", "Appelle Léo sur WhatsApp",
  ],
  "MÉMOIRE": [
    "Souviens-toi que j'aime le café", "Oublie mon adresse", "Qu'est-ce que tu sais sur moi ?", "Liste ma mémoire", "Cherche dans mes souvenirs l'anniversaire",
    "Cherche dans mon cortex les vacances", "Lis ce souvenir", "Note ça : acheter des piles", "Lis mes notes", "Efface mes notes",
  ],
  "CUISINE": [
    "Recette de la ratatouille", "Recette de crêpes pour 6 personnes", "Ajoute du lait à ma liste de courses", "Affiche ma liste de courses",
    "Vide la liste de courses", "Ferme la recette",
  ],
  "JEUX ET 3D": [
    "Affiche l'explorateur spatial", "Affiche ma maison en 3D", "Ouvre le cortex", "Affiche le radar réseau", "Ferme la vue 3D",
    "On joue aux échecs", "Lance la partie avec les blancs niveau moyen", "Recommence la partie", "Quitte les échecs",
    "Affiche la Terre", "Montre-moi Tokyo", "Où suis-je ?", "Trace un itinéraire de Paris à Lyon", "Ferme le globe",
    "Active la vue de Dieu", "Mets à jour la vue de Dieu", "Ferme la vue de Dieu", "Active le mode AR", "Active le miroir AR",
  ],
  "JARVIS": [
    "Ouvre les paramètres", "Ferme les paramètres", "Active les sous-titres", "Désactive les sous-titres", "Active le clavier", "Ferme le clavier",
    "Active l'accélération graphique", "Prends la voix d'homme", "Prends la voix de femme", "Silence", "Tais-toi",
    "Active le mode local", "Repasse en mode hybride", "Liste tes commandes",
  ],
  "ASSISTANT": [
    "Quelle heure est-il ?", "On est quel jour ?", "Quelle date sommes-nous ?", "C'est quel mois ?", "On est en quelle année ?", "J'ai quel âge ?",
    "Quelle heure est-il à Tokyo ?", "Quelle est la capitale du Japon ?", "Quelle est la monnaie du Japon ?",
    "Raconte-moi une blague", "Donne-moi une citation", "Qui es-tu ?", "Qui est ton créateur ?", "Bonjour", "Traduis bonjour en anglais",
    "Lance une pièce", "Lance un dé", "Épelle bonjour",
    "Combien de jours avant Noël ?", "Analyse mon écran", "Aide-moi", "Regarde mon écran", "Lance la caméra", "Regarde-moi",
    "Clique sur le bouton Valider", "Tape le texte bonjour",
  ],
};

const sansAccent = (t: string): string => t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[’]/g, "'");

let index: CommandeAide[] | null = null;

/** Toutes les commandes de l'aide avec leur catégorie (nom de CATEGORIES) et leur sous-catégorie. */
export function commandesAide(): CommandeAide[] {
  if (index) return index;
  index = Object.entries(PAR_CATEGORIE).flatMap(([cat, phrases]) => phrases.map((texte) => {
    const [c, s] = choisir(sansAccent(texte));
    return { texte, cat, sous: CATEGORIES[c].nom === cat ? CATEGORIES[c].sous[s].nom : "" };
  }));
  return index;
}
