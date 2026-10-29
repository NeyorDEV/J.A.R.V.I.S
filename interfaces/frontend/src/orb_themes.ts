/**
 * Thèmes du cylindre : 21 catégories, chacune avec ses sous-catégories. La roue de recherche parcourt d'abord les
 * catégories puis les sous-catégories de celle qui est choisie. Le choix se fait ici d'après les mots de la phrase
 * (texte déjà sans accent, en minuscules) : il ne reflète pas le module réellement exécuté par le backend.
 * Chaque catégorie a des mots forts (`mots`, 2 points) et des mots faibles (`faibles`, 1 point : « salon », « cuisine »,
 * « ouvre », « code »… trop ambigus seuls) : la catégorie qui totalise le plus de points gagne.
 */

export interface Sous { nom: string; mots: RegExp }
export interface Categorie { nom: string; icone: string; mots: RegExp; faibles?: RegExp; sous: Sous[] }

const r = (motifs: string): RegExp => new RegExp(`\\b(${motifs})s?\\b`);
const s = (nom: string, motifs = "$^"): Sous => ({ nom, mots: r(motifs) });

export const CATEGORIES: Categorie[] = [
  { nom: "MUSIQUE", mots: r("musique|spotify|deezer|chanson|morceau|playlist|album|artiste|pause|suivant|precedent|joue|mets du|mets de la|mets des|mets moi du|mets moi de la|daft punk|flow"), faibles: r("volume|son"),
    icone: "M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0a3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0a3 3 0 0 1 6 0z",
    sous: [s("Deezer", "deezer"), s("Flow", "flow"), s("Spotify", "spotify"), s("Playlists", "playlist"), s("Albums", "album"), s("Artistes", "artiste|chante"),
      s("Volume", "volume|son|fort"), s("Pause", "pause|stop"), s("Titre suivant", "suivant|passe"), s("Titre précédent", "precedent|retour")] },
  { nom: "TÉLÉ", mots: r("tele|television|tv|chaine|netflix|youtube"),
    icone: "M2 7h20v13H2zM17 2l-5 5-5-5",
    sous: [s("Allumer", "allume|allumer"), s("Éteindre", "eteins|eteindre"), s("Chaîne", "chaine"), s("Muet", "muet|coupe"), s("Volume", "volume|son"),
      s("Applications", "application|appli"), s("Netflix", "netflix"), s("YouTube", "youtube")] },
  { nom: "JEUX", mots: r("steam|jeu|jeux|jouer|bibliotheque de jeux"),
    icone: "M6 11h4M8 9v4M15 12h.01M18 10h.01M17.32 5H6.68a4 4 0 0 0-3.98 3.59C2.6 9.42 2 14.46 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.41-1.41A2 2 0 0 1 9.83 16h4.34a2 2 0 0 1 1.41.59L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.55-.6-6.58-.68-7.26A4 4 0 0 0 17.32 5z",
    sous: [s("Steam", "steam"), s("Bibliothèque", "bibliotheque"), s("Boutique", "boutique|magasin"), s("Lancer un jeu", "lance|lancer|jouer"), s("Téléchargements", "telechargement|telecharge")] },
  { nom: "MAISON", mots: r("lumiere|lumieres|domotique|prise|prises|chauffage|radiateur|thermostat|capteur|capteurs"),
    icone: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 22V12h6v10",
    sous: [s("Lumières", "lumiere|lumieres|eclairage"), s("Prises", "prise|prises"), s("Chauffage", "chauffage|radiateur|thermostat"), s("Capteurs", "capteur|capteurs")] },
  { nom: "MÉTÉO", mots: r("meteo|temperature|pluie|soleil|temps|neige|orage|parapluie"),
    icone: "M12 2v2M4.93 4.93l1.41 1.41M20 12h2M19.07 4.93l-1.41 1.41M15.95 12.65a4 4 0 0 0-5.93-4.13M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6z",
    sous: [s("Aujourd'hui", "aujourd|maintenant"), s("Demain", "demain"), s("Semaine", "semaine|jours"), s("Température", "temperature|degres|chaud|froid"), s("Pluie", "pluie|parapluie|neige|orage")] },
  { nom: "ALARMES", mots: r("alarme|alarmes|minuteur|reveil|rappel|timer"),
    icone: "M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0",
    sous: [s("Minuteur", "minuteur|timer"), s("Annuler", "annule|supprime|arrete"), s("Liste", "liste|mes alarmes"), s("Alarme", "alarme|reveil"), s("Rappel", "rappel")] },
  { nom: "AGENDA", mots: r("agenda|calendrier|rendez-vous|rdv|evenement|reunion"),
    icone: "M8 2v4M16 2v4M3 6h18v15H3zM3 11h18",
    sous: [s("Calendrier", "calendrier|agenda"), s("Prochain RDV", "prochain"), s("Ajouter", "ajoute|cree|planifie"), s("Aujourd'hui", "aujourd"), s("Demain", "demain"), s("Cette semaine", "semaine"), s("Modifier", "modifie|deplace"), s("Supprimer", "supprime|annule")] },
  { nom: "MAIL", mots: r("mail|mails|email|emails|gmail|courriel"),
    icone: "M3 5h18v14H3zM3 6l9 7 9-7",
    sous: [s("Lire", "lis|lire|ouvre"), s("Non lus", "non lus|non lu"), s("Répondre", "reponds|repondre"), s("Envoyer", "envoie|envoyer|ecris"), s("Rechercher", "cherche|recherche")] },
  { nom: "DOCUMENTS", mots: r("document|documents|pdf|drive|word|excel|rapport|lettre|cv"),
    icone: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h8",
    sous: [s("Créer", "cree|redige|genere"), s("PDF", "pdf"), s("Drive", "drive"), s("Modifier", "modifie"), s("Résumer", "resume"), s("Traduire", "traduis|traduire")] },
  { nom: "SYSTÈME", mots: r("volume|veille|arret|redemarre|redemarrer|ordinateur|pc|fichier|fichiers|dossier|corbeille|capture|screenshot|verrouille"), faibles: r("application|appli|programme|lance|ouvre|ferme"),
    icone: "M2 4h20v13H2zM8 21h8M12 17v4",
    sous: [s("Volume", "volume|son"), s("Veille", "veille"), s("Arrêt", "arret|eteins|eteindre"), s("Redémarrage", "redemarre|redemarrer"), s("Fichiers", "fichier|fichiers|dossier"),
      s("Corbeille", "corbeille|vide"), s("Capture d'écran", "capture|screenshot"), s("Verrouiller", "verrouille|bloque"), s("Applications", "application|appli|programme|lance|ouvre|ferme")] },
  { nom: "LOGICIELS", mots: r("installe|installer|desinstalle|desinstaller|winget|mise a jour|mises a jour|met a jour|mets a jour|mettre a jour|logiciel"),
    icone: "M21 8v8l-9 5-9-5V8l9-5zM3.3 7.5 12 12l8.7-4.5M12 22V12",
    sous: [s("Installer", "installe|installer"), s("Mises à jour", "mise a jour|mises a jour|met a jour|mets a jour|mettre a jour|update"), s("Désinstaller", "desinstalle|desinstaller|supprime"), s("Rechercher", "cherche|recherche"), s("Liste installée", "liste|installes"), s("Résidus", "residu|residus|restes")] },
  { nom: "SÉCURITÉ", mots: r("antivirus|virus|scan|analyse|coffre|coffre-fort|mot de passe|reseau|wifi|intrus|journal|securite"),
    icone: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
    sous: [s("Antivirus", "antivirus|virus|scan|analyse"), s("Coffre-fort", "coffre|coffre-fort|mot de passe"), s("Journal", "journal|audit"), s("Appareils", "appareil|appareils|connectes"), s("Réseau", "reseau|wifi|radar")] },
  { nom: "INTERNET", mots: r("cherche|recherche|actualite|actu|infos|news|navigateur|chrome|firefox|edge|onglet|google|internet|page web|lis la page|resume la page"), faibles: r("site|web"),
    icone: "M12 2a10 10 0 1 0 0 20a10 10 0 0 0 0-20zM2 12h20M12 2a15 15 0 0 1 4 10a15 15 0 0 1-4 10a15 15 0 0 1-4-10a15 15 0 0 1 4-10z",
    sous: [s("Recherche", "cherche|recherche|google"), s("Actualités", "actualite|actualites|actu|infos|news"), s("Navigateur", "navigateur|chrome"), s("Onglets", "onglet|onglets"), s("Lire une page", "lis la page|resume la page"), s("Page web", "page|site")] },
  { nom: "IMAGES", mots: r("image|images|photo|photos|dessin|illustration"),
    icone: "M3 3h18v18H3zM8.5 10a1.5 1.5 0 1 0 0-3a1.5 1.5 0 0 0 0 3zM21 15l-5-5L5 21",
    sous: [s("Générer", "genere|cree|dessine"), s("Rechercher", "cherche|trouve"), s("Modifier", "modifie|retouche"), s("Afficher", "affiche|montre"), s("Fermer", "ferme"), s("Enregistrer", "enregistre|sauvegarde")] },
  { nom: "CRÉATION", mots: r("skill|competence|plugin|dev swarm|editeur|site web|application web|developpe"), faibles: r("code|script|projet"),
    icone: "M16 18l6-6-6-6M8 6l-6 6 6 6",
    sous: [s("Site web", "site|web"), s("Code", "code|script|programme"), s("Skills", "skill|skills"), s("Compétences", "competence|competences"), s("Plugins", "plugin|plugins"), s("Éditeur", "editeur"), s("Projet", "projet")] },
  { nom: "DISCORD", mots: r("discord|serveur|whatsapp"), faibles: r("salon"),
    icone: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2zM8 10h.01M12 10h.01M16 10h.01",
    sous: [s("Salon", "salon"), s("Message privé", "prive|mp|dm"), s("Serveur", "mes serveurs|liste des serveurs|ouvre le serveur|ouvre un serveur|change de serveur|rejoins le serveur|quitte le serveur"), s("WhatsApp", "whatsapp")] },
  { nom: "MÉMOIRE", mots: r("souviens|memoire|retiens|rappelle-toi|souvenir|oublie|prefere|preferences|historique"),
    icone: "M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zM9 9h6v6H9zM9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3",
    sous: [s("Souvenirs", "souviens|souvenir|souvenirs|retiens"), s("Préférences", "prefere|preferences"), s("Oublier", "oublie"), s("Historique", "historique|conversation")] },
  { nom: "CUISINE", mots: r("recette|ingredient|plat|courses|liste de courses"), faibles: r("cuisine"),
    icone: "M3 2v7a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V2M7 2v20M21 15V2a5 5 0 0 0-5 5v6a2 2 0 0 0 2 2h3zM21 15v7",
    sous: [s("Recettes", "recette|recettes|plat"), s("Liste de courses", "courses|liste|ajoute"), s("Ingrédients", "ingredient|ingredients"), s("Portions", "portion|portions|personnes"), s("Étapes", "etape|etapes|instructions")] },
  { nom: "JEUX ET 3D", mots: r("echecs|echiquier|explorateur|maison 3d|cortex|radar|globe|terre|carte|3d|mains|geste"),
    icone: "M21 16V8l-9-5-9 5v8l9 5zM3.3 7 12 12l8.7-5M12 22V12",
    sous: [s("Échecs", "echecs|echiquier"), s("Explorateur", "explorateur"), s("Maison 3D", "maison|3d"), s("Cortex", "cortex|cerveau"), s("Radar réseau", "radar"), s("Globe", "globe|terre|carte"), s("Gestes", "main|mains|geste|gestes")] },
  { nom: "JARVIS", mots: r("voix|micro|profil|parametre|parametres|theme|couleur|aide|mode local|hors ligne|sous-titre|sous-titres|paroles"),
    icone: "M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3zM19 10v2a7 7 0 0 1-14 0v-2M12 19v3",
    sous: [s("Voix", "voix"), s("Profil vocal", "profil|reconnais"), s("Thème", "theme|couleur"), s("Aide", "aide"), s("Mode local", "local|hors ligne|offline"), s("Sous-titres", "sous-titre|sous-titres|paroles"), s("Micro", "micro|ecoute")] },
  { nom: "ASSISTANT", mots: r("$^"),
    icone: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z",
    sous: [s("Question libre"), s("Calcul", "calcul|combien font"), s("Traduction", "traduis|en anglais|en espagnol"), s("Explication", "explique|pourquoi|comment"), s("Conseil", "conseil|recommande"), s("Définition", "definis|veut dire|signifie"), s("Blague", "blague|drole")] },
];

export const DEFAUT = CATEGORIES.length - 1;  // ASSISTANT

// Ordre dans lequel on teste les catégories : du plus spécifique au plus général (indices de CATEGORIES)
const PRIORITE = [16, 18, 14, 10, 1, 15, 7, 6, 13, 8, 5, 17, 4, 0, 2, 3, 11, 9, 12, 19];

const compte = (re: RegExp, texte: string): number => (texte.match(new RegExp(re.source, "g")) ?? []).length;
const points = (cat: Categorie, texte: string): number => Math.min(3, compte(cat.mots, texte)) * 2 + (cat.faibles ? Math.min(2, compte(cat.faibles, texte)) : 0);

/** Catégorie et sous-catégorie qui correspondent à la phrase (texte sans accent, minuscules). */
export function choisir(texte: string): [categorie: number, sous: number] {
  let meilleure = DEFAUT, record = 0;
  for (const i of PRIORITE) {  // à égalité, la première de la liste l'emporte
    const p = points(CATEGORIES[i], texte);
    if (p > record) { record = p; meilleure = i; }
  }
  return [meilleure, choisirSous(meilleure, texte)];
}

/** Sous-catégorie d'une catégorie donnée pour la phrase : la première est le choix par défaut, une autre ne gagne que
 *  si la phrase la désigne précisément. */
export function choisirSous(categorie: number, texte: string): number {
  const j = CATEGORIES[categorie].sous.findIndex((x, k) => k > 0 && x.mots.test(texte));
  return j < 0 ? 0 : j;
}
