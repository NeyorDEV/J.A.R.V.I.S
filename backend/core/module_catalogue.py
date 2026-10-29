"""Annonce au HUD le module réellement exécuté (catégorie et sous-catégorie du cylindre).

La roue de recherche de l'orbe (interfaces/frontend/src/orb_themes.ts) devine d'abord la catégorie par mots-clés d'après la
phrase ; ce module envoie ensuite `module_trouve`, et la roue s'arrête sur ce que JARVIS fait vraiment, même pour une
phrase mal transcrite ou une formulation imprévue.

Trois sources, de la plus précise à la moins précise :
  1. le code qui exécute la commande appelle `annoncer(categorie, sous)` (ex. Deezer : « Albums », « Playlists ») ;
  2. le nom du resolver qui a répondu (RESOLVEUR_VERS_CATEGORIE) ;
  3. le nom de l'action JSON produite par l'IA (ACTION_VERS_CATEGORIE).
Sans sous-catégorie, le HUD la devine d'après la phrase, à l'intérieur de la catégorie annoncée.
Les noms doivent être exactement ceux de orb_themes.ts (vérifié par scratch/outils_test/test_module_catalogue.py).
"""

import json

from core import module_ecrans
from core.web_bridge import _safe_ws_send

_annonce = None   # (catégorie, sous-catégorie) annoncée pour la commande en cours


def reinitialiser():
    """Début d'une nouvelle commande."""
    global _annonce
    _annonce = None


def annoncer(categorie, sous=None):
    """Envoie au HUD la catégorie (et sous-catégorie) exécutée. Sans effet si identique à la dernière annonce."""
    global _annonce
    if not categorie or _annonce == (categorie, sous):
        return
    _annonce = (categorie, sous)
    _safe_ws_send(json.dumps({"action": "module_trouve", "categorie": categorie, "sous": sous}, ensure_ascii=False))
    module_ecrans.declencher(categorie, sous)   # contenu de l'écran du cylindre pour les catégories qui en ont un


def deja_annonce():
    return _annonce is not None


def annoncer_pour_resolveur(nom):
    """Après la réponse d'un resolver : sa catégorie, sauf si le code exécuté a déjà annoncé plus précis."""
    if _annonce is None and nom in RESOLVEUR_VERS_CATEGORIE:
        annoncer(*RESOLVEUR_VERS_CATEGORIE[nom])


def annoncer_pour_action(action):
    """Au début de l'exécution d'une action JSON de l'IA."""
    if action in ACTION_VERS_CATEGORIE:
        annoncer(*ACTION_VERS_CATEGORIE[action])


# Resolver -> (catégorie, sous-catégorie ou None). Les resolvers généraux (commandes_locales, dom_hud) ne figurent pas ici :
# leur code annonce lui-même ce qu'il exécute.
RESOLVEUR_VERS_CATEGORIE = {
    "echecs": ("JEUX ET 3D", "Échecs"),
    "alarmes": ("ALARMES", None),
    "resoudre_developpement": ("CRÉATION", "Code"),
    "resoudre_uninstaller_localement": ("LOGICIELS", "Désinstaller"),
    "resoudre_local_mode": ("JARVIS", "Mode local"),
    "resoudre_lancer_enigme": ("ASSISTANT", None),
    "resoudre_os_autopilot": ("SYSTÈME", "Applications"),
    "resoudre_creation_plugin": ("CRÉATION", "Plugins"),
    "resoudre_generation_document": ("DOCUMENTS", "Créer"),
    "resoudre_images_locales": ("IMAGES", "Rechercher"),
    "resoudre_modifier_image": ("IMAGES", "Modifier"),
    "resoudre_recipe": ("CUISINE", "Recettes"),
    "resoudre_connexions_reseau": ("SÉCURITÉ", "Réseau"),
    "resoudre_dev_swarm": ("CRÉATION", "Projet"),
    "resoudre_lance_sandbox": ("CRÉATION", "Code"),
    "resoudre_creation_site_web": ("CRÉATION", "Site web"),
    "resoudre_ouvrir_site_web": ("INTERNET", "Page web"),
    "resoudre_tv_localement": ("TÉLÉ", None),
    "resoudre_steam_jeux": ("JEUX", "Steam"),
    "resoudre_navigateur": ("INTERNET", "Navigateur"),
    "resoudre_discord": ("DISCORD", None),
    "resoudre_skills": ("CRÉATION", "Skills"),
    "resoudre_commandes_systeme": ("SYSTÈME", None),
    "traiter_infos_systeme": ("SYSTÈME", None),
    "resoudre_listes_locales": ("CUISINE", "Liste de courses"),
    "resoudre_temps_localement": ("ASSISTANT", None),
    "traiter_conversion_locale": ("ASSISTANT", "Calcul"),
    "traiter_traduction_locale": ("ASSISTANT", "Traduction"),
    "traiter_question_francais": ("ASSISTANT", "Explication"),
    "traiter_extras_locaux": ("ASSISTANT", None),
    "traiter_globe_local": ("JEUX ET 3D", "Globe"),
    "resoudre_apps_localement": ("SYSTÈME", "Applications"),
    "resoudre_memoire_locale": ("MÉMOIRE", None),
}

# Action JSON de l'IA -> (catégorie, sous-catégorie ou None)
ACTION_VERS_CATEGORIE = {
    "afficher_dossier": ("SYSTÈME", "Fichiers"), "enumerer_dossier": ("SYSTÈME", "Fichiers"),
    "classer_par_date": ("SYSTÈME", "Fichiers"), "classer_par_type": ("SYSTÈME", "Fichiers"),
    "trier_complet": ("SYSTÈME", "Fichiers"), "creer_dossier": ("SYSTÈME", "Fichiers"),
    "changer_nom_fichier": ("SYSTÈME", "Fichiers"), "transferer_fichier": ("SYSTÈME", "Fichiers"),
    "rechercher_fichier": ("SYSTÈME", "Fichiers"), "ouvrir_element": ("SYSTÈME", "Fichiers"),
    "analyser_fichier": ("SYSTÈME", "Fichiers"),
    "antivirus_scan": ("SÉCURITÉ", "Antivirus"),
    "alarme_set": ("ALARMES", "Alarme"), "alarme_list": ("ALARMES", "Liste"), "alarme_cancel": ("ALARMES", "Annuler"),
    "meteo": ("MÉTÉO", None), "alerte_meteo": ("MÉTÉO", None),
    "voir_ecran": ("SYSTÈME", "Capture d'écran"),
    "vision_chercher_sur_site": ("INTERNET", "Navigateur"), "vision_ecrire": ("INTERNET", "Navigateur"),
    "vision_navigateur": ("INTERNET", "Navigateur"), "web_agent_task": ("INTERNET", "Navigateur"),
    "fermer_navigateur_agent": ("INTERNET", "Navigateur"), "analyse_live": ("INTERNET", "Navigateur"),
    "recherche_web": ("INTERNET", "Recherche"), "recherche_approfondie": ("INTERNET", "Recherche"),
    "chess_start": ("JEUX ET 3D", "Échecs"), "chess_play": ("JEUX ET 3D", "Échecs"), "chess_stop": ("JEUX ET 3D", "Échecs"),
    "create_doc": ("DOCUMENTS", "Créer"), "write_doc": ("DOCUMENTS", "Modifier"), "read_doc": ("DOCUMENTS", "Drive"),
    "create_sheet": ("DOCUMENTS", "Drive"), "read_sheet": ("DOCUMENTS", "Drive"), "append_sheet": ("DOCUMENTS", "Drive"),
    "open_drive": ("DOCUMENTS", "Drive"), "search_drive": ("DOCUMENTS", "Drive"), "upload_file": ("DOCUMENTS", "Drive"),
    "share_file": ("DOCUMENTS", "Drive"), "create_folder": ("DOCUMENTS", "Drive"),
    "read_emails": ("MAIL", "Lire"), "read_full_email": ("MAIL", "Lire"), "archive_email": ("MAIL", "Lire"),
    "delete_email": ("MAIL", "Lire"), "send_email": ("MAIL", "Envoyer"), "reply_email": ("MAIL", "Répondre"),
    "read_calendar": ("AGENDA", "Calendrier"), "create_event": ("AGENDA", "Ajouter"),
    "update_event": ("AGENDA", "Modifier"), "delete_event": ("AGENDA", "Supprimer"),
    "create_task": ("AGENDA", "Ajouter"), "list_tasks": ("AGENDA", "Calendrier"),
    "complete_task": ("AGENDA", "Modifier"), "delete_task": ("AGENDA", "Supprimer"),
    "memoriser": ("MÉMOIRE", "Souvenirs"), "oublier": ("MÉMOIRE", "Oublier"), "lister_memoire": ("MÉMOIRE", "Souvenirs"),
    "ha_action": ("MAISON", None),
    "homepod_action": ("MUSIQUE", None),
    "lance_camera": ("JEUX ET 3D", "Gestes"),
    "github_action": ("CRÉATION", "Projet"),
    "whatsapp_appel": ("DISCORD", "WhatsApp"),
    "spotify_ouvrir": ("MUSIQUE", None), "spotify_rechercher": ("MUSIQUE", None), "spotify_lecture_pause": ("MUSIQUE", "Pause"),
    "spotify_stop": ("MUSIQUE", "Pause"), "spotify_suivant": ("MUSIQUE", "Titre suivant"),
    "spotify_precedent": ("MUSIQUE", "Titre précédent"), "spotify_volume": ("MUSIQUE", "Volume"),
    "deezer_demarrer": ("MUSIQUE", "Deezer"), "deezer_chercher": ("MUSIQUE", None), "deezer_basculer_lecture": ("MUSIQUE", "Pause"),
    "deezer_arreter": ("MUSIQUE", "Pause"), "deezer_reprendre": ("MUSIQUE", "Pause"),
    "deezer_piste_suivante": ("MUSIQUE", "Titre suivant"), "deezer_piste_precedente": ("MUSIQUE", "Titre précédent"),
    "deezer_regler_volume": ("MUSIQUE", "Volume"), "deezer_flow": ("MUSIQUE", "Flow"), "deezer_fermer": ("MUSIQUE", "Deezer"),
}
