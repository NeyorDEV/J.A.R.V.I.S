"""Commandes locales sans IA (suite) : identité, aide, HUD 3D, apps, musique, coffre-fort."""

import asyncio
import json
import os
import subprocess
import time
import webbrowser

import pyautogui

import core.shared as shared
from controller.app_launcher import (
    _APPS_CATALOGUE, _boulot_lancer, _fermer_app, mode_boulot, mode_gaming, mode_rocket_league,
)
from controller.deezer_controller import (
    deezer_lancer_playlist, deezer_lecture_pause, deezer_ouvrir, deezer_precedent,
    deezer_rechercher, deezer_stop, deezer_suivant, deezer_volume,
)
from core.web_bridge import _safe_ws_send
from module.file_manager import arranger_fenetres_dossiers, ouvrir_dossier


_PAS_TROUVE = object()  # sentinelle : section sans résultat, on passe à la suivante


async def _commandes_identite_hud(t):
    """Identité/créateur, aide, dossiers, explorateur 3D, carte domotique, cortex, orbe, démo."""
    # --- IDENTITE / CREATEUR (Priorite 0) ---
    _createur_questions = [
        "qui est ton créateur", "qui est ton createur",
        "qui t'a créé", "qui t'a cree", "qui t'a crée",
        "qui ta créé", "qui ta cree", "qui ta crée",
        "qui t'a fabriqué", "qui t'a fabrique",
        "qui t'a inventé", "qui t'a invente",
        "qui t'a construit", "qui ta construit",
        "qui t'a développé", "qui t'a developpe",
        "qui t'a programmé", "qui t'a programme",
        "qui t'a codé", "qui t'a code",
        "qui t'a conçu", "qui t'a concu",
        "qui ta développé", "qui ta developpe",
        "qui ta programmé", "qui ta programme",
        "qui ta codé", "qui ta code",
        "qui ta conçu", "qui ta concu",
        "c'est qui ton créateur", "c'est qui ton createur",
        "t'as été créé par qui", "t'as ete cree par qui",
        "t'es fait par qui", "tu es fait par qui",
        "tu viens d'où", "tu viens d'ou", "tu viens de ou",
        "d'où tu viens", "d'ou tu viens",
        "qui est derrière toi", "qui est derriere toi",
        "qui est ton père", "qui est ton pere",
        "qui est ton papa",
        "qui est ton développeur", "qui est ton developpeur",
        "qui est ton dev",
        "ton créateur c'est qui", "ton createur c'est qui",
    ]
    if any(q in t for q in _createur_questions):
        import random as _rnd
        _reponses_createur = [
            "J'ai été créé par mylane. C'est grâce à lui que j'existe aujourd'hui.",
            "Mon créateur, c'est Mylane. Il m'a conçu de A à Z pour être votre assistant personnel.",
            "Je suis le fruit du travail de Mylane. Tout mon code, ma voix, mon intelligence, c'est lui.",
            "Mylane est mon créateur. C'est lui qui m'a donné vie, et je dois dire qu'il a fait du bon boulot.",
            "C'est Mylane qui m'a développé. Un développeur passionné qui voulait créer l'assistant ultime.",
            "Mon père numérique, c'est Mylane. Il m'a programmé avec passion pour vous aider au quotidien.",
            "Mylane, c'est le génie derrière mon existence.",
            "Je suis né dans les lignes de code de Mylane. Sans lui, je ne serais qu'un écran noir.",
            "Mylane m'a créé. C'est un développeur français qui a voulu rendre l'intelligence artificielle accessible à tous.",
            "Mon créateur s'appelle Mylane. Il a mis tout son savoir-faire pour me construire, et je lui en suis reconnaissant.",
        ]
        return _rnd.choice(_reponses_createur)

    # --- AIDE / CAPACITES (Priorite 0) ---
    _aide_questions = [
        "que peux-tu faire", "que peux tu faire", "que sais-tu faire", "que sais tu faire",
        "quelles sont tes capacités", "quelles sont tes capacites",
        "montre moi tes capacités", "montre-moi tes capacités",
        "montre moi ce que tu sais faire", "aide moi", "aide-moi",
        "montre moi tes commandes", "liste tes commandes", "qu'est-ce que tu peux faire"
    ]
    if any(q in t for q in _aide_questions):
        # Envoi IMMEDIAT de l'action help au frontend
        if shared.CONNECTED_CLIENTS:
            async def _dispatch_help():
                msg = json.dumps({"action": "help"})
                await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
            asyncio.create_task(_dispatch_help())

        import random as _rnd
        _reponses_aide = [
            "J'affiche mes systèmes de bord, mylane. Je peux gérer votre musique, lancer des recherches, naviguer sur le globe 3D, ou encore ouvrir vos dossiers personnels. Que souhaitez-vous tester ?",
            "Déploiement des protocoles d'assistance. Voici mes modules actifs : contrôle média, navigation satellite, recherche intelligente et gestionnaire de fichiers. Je suis à vos ordres.",
            "Bien sûr. Je suis capable de localiser n'importe quel point sur Terre, de piloter vos applications, et de répondre à vos questions complexes. Jetez un œil aux suggestions à l'écran.",
            "Initialisation de l'interface d'aide. Je peux aussi bien prendre une capture d'écran que vous donner la météo à l'autre bout du monde. Dites-moi simplement ce qu'il vous faut.",
            "Accès aux bases de données. Je peux automatiser vos tâches répétitives, gérer vos rappels et même vous raconter une blague si l'ambiance est trop sérieuse.",
        ]
        return _rnd.choice(_reponses_aide)

    # --- DOSSIERS (Priorité 1) ---
    if any(k in t for k in ["mosaïque dossiers", "range mes dossiers", "range les dossiers", "range tous les dossiers", "range tous mes dossiers", "mosaïque"]):
        return arranger_fenetres_dossiers()

    # --- MODE EXPLORATEUR SPATIAL 3D ---
    if any(k in t for k in [
        "ouvre tous les dossiers", "ouvre tous mes dossiers", "ouvre mes dossiers", "ouvre les dossiers", 
        "mes dossiers", "montre moi mes dossiers", "montre mes dossiers", "explorateur 3d", "explorateur spatial", 
        "dossier spatial", "explorateur spatial 3d", "mode explorer", "affiche l'explorateur", 
        "ouvre l'explorateur spatial", "affiche mes fichiers"
    ]):
        _safe_ws_send(json.dumps({"action": "open_spatial_explorer"}))
        return "Déploiement de l'explorateur spatial 3D, mylane."

    # --- MODE CARTE 3D DOMOTIQUE ---
    if any(k in t for k in [
        "affiche ma maison", "affiche la maison", "carte domotique", "mode carte 3d", "mode carte", 
        "carte 3d", "affiche la carte 3d", "affiche la carte de la maison", "affiche la carte domotique", 
        "ma maison 3d"
    ]):
        _safe_ws_send(json.dumps({"action": "open_domotic_map"}))
        return "Déploiement de la carte domotique 3D, mylane."

    # --- RECHERCHE SÉMANTIQUE VISUELLE CORTEX ---
    if any(p in t for p in ["cherche dans mon cortex", "cherche dans le cortex", "trouve dans mon cortex", "trouve dans le cortex"]):
        query = t
        for prefix in ["cherche dans mon cortex", "cherche dans le cortex", "trouve dans mon cortex", "trouve dans le cortex"]:
            if prefix in query:
                query = query.replace(prefix, "").strip()
        query = query.replace("?", "").strip()
        if len(query) > 1:
            _safe_ws_send(json.dumps({"action": "cortex_search", "query": query}))
            return f"Recherche de '{query}' initiée dans mon cortex neuronal, mylane."
        return "Que souhaitez-vous chercher dans votre cortex, mylane ?"

    # --- MODE CORTEX 3D ---
    if any(k in t for k in [
        "cortex", "affiche ton cortex", "affiche le cortex", "mode cortex", "ouvre le cortex", 
        "ouvre ton cortex", "connexions neuronales", "cortex neuronal"
    ]):
        _safe_ws_send(json.dumps({"action": "open_cortex"}))
        return "Déploiement du cortex neuronal 3D, mylane."

    # --- NARRATION VOCALE DE SOUVENIR ---
    if any(p in t for p in ["lis ce souvenir", "raconte ce souvenir", "lis la mémoire", "raconte cette mémoire", "lis le souvenir"]):
        _safe_ws_send(json.dumps({"action": "cortex_vocal_speak_request"}))
        return "C'est entendu, mylane. Lecture du souvenir actif..."

    # --- TRANSFORMATION DE L'ORBE EN MOT ---
    _mots_orbe = ["écrit le mot", "écris le mot", "ecris le mot", "écrit moi", "écris moi", "ecris moi", "écris-moi", "ecris-moi", "orbe écrit", "orbe ecris"]
    word = ""
    if any(m in t for m in _mots_orbe):
        for prefix in _mots_orbe:
            if prefix in t:
                parts = t.split(prefix, 1)
                if len(parts) > 1:
                    word = parts[1].strip()
                    if word.startswith("le mot "):
                        word = word[7:].strip()
                break
    else:
        # Forme naturelle "écris X" / "écrit X" (sans "le mot"/"moi") → orbe,
        # uniquement si X est court : on évite de détourner une vraie dictée
        # (mail, message, long texte) qui doit partir vers le cloud.
        for prefix in ("écris ", "écrit ", "ecris ", "ecrit "):
            if t.startswith(prefix):
                candidat = t[len(prefix):].strip().rstrip(".?! ")
                _mots_dictee = ("mail", "email", "e-mail", "message", "sms", "code",
                                "document", "lettre", "texte", " dans ", " sur ", " à ")
                if candidat and len(candidat.split()) <= 3 and len(candidat) <= 25 \
                   and not any(a in candidat for a in _mots_dictee):
                    word = candidat
                break
    if word:
        word = word.rstrip(".?! ")
        _safe_ws_send(json.dumps({"action": "orb_write_word", "word": word}))
        return f"Très bien monsieur, je reconfigure l'orbe pour dessiner le mot : {word}."

    # --- DECLENCHEMENT PROTOCOLE DEMONSTRATION ORBE ---
    if any(k in t for k in ["démonstration", "demonstration", "démo", "demo", "lance la démo", "lance une démo", "lance une démonstration", "lance la démonstration", "protocole de démo", "fais une démo", "fais une demo"]):
        _safe_ws_send(json.dumps({"action": "demo"}))
        return "Initialisation du protocole de démonstration visuelle, mylane."

    prefixes_dossiers = ["ouvre le dossier ", "ouvre mon dossier ", "ouvre le répertoire ", "ouvre le repertoire ", "ouvre dossier ", "ouvre ", "mets "]
    # On vérifie d'abord si c'est un dossier connu
    mots_cles_dossiers = ["bureau", "document", "téléchargement", "image", "photo", "vidéo", "musique", "corbeille"]
    # --- LOGIQUE MULTIMÉDIA (TV/YouTube) MIGRÉE VERS plugins/system_resolver.py ---

    # --- DOSSIERS (Priorité 1) ---
    for prefix in prefixes_dossiers:
        if t.startswith(prefix):
            potentiel_dossier = t.replace(prefix, "").strip()
            if any(k in potentiel_dossier for k in mots_cles_dossiers):
                ok, msg = ouvrir_dossier(potentiel_dossier)
                if ok: return f"J'ouvre le dossier {potentiel_dossier}, mylane."
    return _PAS_TROUVE


async def _commandes_apps_musique(t):
    """Modes boulot/gaming, applications, musique/Deezer, coffre-fort, dossiers, demandes inconnues."""
    # --- MODE BOULOT (Priorité 1 bis) ---
    if any(k in t for k in ["au boulot", "mode boulot", "mode travail", "on bosse", "mode bureau", "commence le boulot"]):
        return await mode_boulot()

    # (Le bloc TV est désormais en haut)

    if any(k in t for k in ["mode gaming", "mode jeu", "on joue", "session gaming", "lance le gaming", "mode gamer"]):
        return await mode_gaming()

    if any(k in t for k in ["mode rocket league", "lance rocket league", "joue à rocket league", "on joue à rocket league"]):
        return await mode_rocket_league()

    # --- APPLICATIONS STANDARD & CATALOGUE (Priorité 2) ---
    # IMPORTANT : ces checks doivent être AVANT la détection Spotify car
    # "lance " est aussi un préfixe Spotify → "lance steam" partirait sinon vers Spotify.
    mots_ouvrir = ["ouvre", "lance", "démarre", "démarres", "ouvrir", "lancer"]
    mots_fermer = ["ferme", "quitte", "stoppe", "éteins", "coupe", "fermer", "quitter"]

    apps_standard = {
        "calculatrice":            "calc",
        "notepad":                 "notepad",
        "bloc-notes":              "notepad",
        "bloc notes":              "notepad",
        "paint":                   "mspaint",
        "gestionnaire de tâches":  "taskmgr",
        "gestionnaire de taches":  "taskmgr",
        "task manager":            "taskmgr",
        "panneau de configuration": "control",
        "paramètres":              "ms-settings:",
        "parametres":              "ms-settings:",
        "réglages":                "ms-settings:",
        "reglages":                "ms-settings:",
        "explorateur":             "explorer",
        "explorateur de fichiers": "explorer",
        "invite de commande":      "cmd",
        "cmd":                     "cmd",
        "snipping tool":           "SnippingTool",
        "outil capture":           "SnippingTool",
        "capture d'écran":         "SnippingTool",
        "capture d'ecran":         "SnippingTool",
        "enregistreur vocal":      "SoundRecorder",
        "magnétophone":            "SoundRecorder",
        "table des caractères":    "charmap",
        "caractères spéciaux":     "charmap",
        "nettoyage de disque":     "cleanmgr",
        "informations système":    "msinfo32",
        "info système":            "msinfo32",
        "info systeme":            "msinfo32",
    }
    for nom, cmd in apps_standard.items():
        if any(f"{m} {nom}" in t for m in mots_ouvrir):
            try:
                subprocess.Popen(cmd)
                return f"J'ouvre {nom}, mylane."
            except Exception:
                return f"Désolé mylane, je n'ai pas réussi à lancer {nom}."

    import re
    for cle, info in _APPS_CATALOGUE.items():
        # On vérifie que la clé est un mot entier pour éviter "ea" dans "Billie Jean"
        if not re.search(rf"\b{re.escape(cle)}\b", t):
            continue

        if any(m in t for m in mots_fermer):
            ok = _fermer_app(info["noms"])
            if ok:
                return f"J'ai fermé {info['label']}, mylane."
            return f"Je n'ai pas trouvé {info['label']} en cours d'exécution."
        if any(m in t for m in mots_ouvrir):
            _boulot_lancer(info["label"], info["noms"], chemins_hints=info["hints"])
            return f"Je lance {info['label']}, mylane."

    # (Bloc YouTube PC supprimé pour éviter les conflits avec la TV)

    # --- SPOTIFY / MUSIQUE (Priorité 3) ---
    # YouTube music spécifique — doit être AVANT le check Spotify
    if any(k in t for k in ["musique sur youtube", "met de la musique sur youtube", "mets de la musique sur youtube"]):
        url = shared.YOUTUBE_MUSIQUE_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
        webbrowser.open(url, new=2)
        time.sleep(5)
        pyautogui.press('f')
        return "C'est parti mylane, je lance votre musique sur YouTube."

    # Playlist de musique par défaut — intelligente (Deezer, YouTube, Spotify ou personnalisé)
    if any(k in t for k in [
        "met de la musique", "mets de la musique",
        "lance ma playlist", "ma playlist"
    ]):
        # Extraire la requête spécifique de musique/playlist
        # Si l'utilisateur a spécifié un nom (ex: "joue ma playlist teenage dirtbag"),
        # on ne traite pas cela comme le lancement de la playlist par défaut.
        query_normalized = t
        for verb in ["joue", "jouer", "mets", "mettre", "lance", "lancer", "écoute", "ecoute", "écouter", "ecouter", "play", "active", "activer", "démarre", "demarre", "démarrer", "demarrer"]:
            query_normalized = re.sub(rf"\b{verb}\b", "", query_normalized)
        for article in ["ma", "la", "mon", "le", "un", "une", "des", "du", "de", "de la", "d'", "votre", "notre", "mes", "les", "moi"]:
            query_normalized = re.sub(rf"\b{article}\b", "", query_normalized)
        for noun in ["musique", "playlist", "chanson", "piste", "titre", "album", "artiste", "son"]:
            query_normalized = re.sub(rf"\b{noun}\b", "", query_normalized)

        specific_query = query_normalized.strip()
        if not specific_query:
            import json as _j
            musique_lien = None
            try:
                _p = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
                if os.path.exists(_p):
                    with open(_p, "r", encoding="utf-8") as _f:
                        cfg_temp = _j.load(_f)
                        musique_lien = cfg_temp.get("musique_lien")
            except: pass

            if musique_lien:
                musique_lien_lower = musique_lien.lower()
                if "youtube.com" in musique_lien_lower or "youtu.be" in musique_lien_lower:
                    webbrowser.open(musique_lien, new=2)
                    time.sleep(5)
                    pyautogui.press('f')
                    return "C'est parti mylane, je lance votre musique sur YouTube."
                elif "spotify" in musique_lien_lower or musique_lien_lower.startswith("spotify:"):
                    try:
                        from controller.spotify_controller import spotify_lancer_playlist
                        ok = spotify_lancer_playlist(musique_lien)
                        if ok:
                            return "C'est parti mylane, je lance votre musique sur Spotify."
                    except: pass
                    return "Je n'ai pas réussi à ouvrir Spotify, mylane."
                elif "deezer" in musique_lien_lower:
                    ok = await deezer_lancer_playlist(musique_lien)
                    if ok:
                        return "C'est parti mylane, je lance votre musique sur Deezer."
                    return "Je n'ai pas réussi à ouvrir Deezer, mylane."
                else:
                    # Lien générique
                    webbrowser.open(musique_lien, new=2)
                    return "C'est parti mylane, je lance votre lien de musique personnalisé dans le navigateur."
            else:
                # Fallback par défaut sur Deezer
                ok = await deezer_lancer_playlist()
                if ok:
                    return "C'est parti mylane, je lance votre playlist sur Deezer."
                return "Je n'ai pas réussi à ouvrir Deezer, mylane."

    if any(k in t for k in ["ouvre deezer", "lance deezer"]):
        return await deezer_ouvrir()

    if any(k in t for k in ["suivante", "suivant", "chanson suivante", "piste suivante", "morceau suivant", "musique suivante", "musique d'après", "musique d'apres"]):
        return await deezer_suivant()
    if any(k in t for k in ["précédente", "précédent", "precedente", "precedent", "chanson précédente", "morceau précédent", "reviens en arrière", "retour en arrière", "musique d'avant"]):
        return await deezer_precedent()
    if any(k in t for k in ["mets en pause", "stop la musique", "arrête la musique", "arrete la musique", "arrête la playlist", "arrete la playlist", "mets sur pause", "met en pause", "met sur pause", "met pause", "mets pause", "pause"]):
        return await deezer_stop()
    if any(k in t for k in ["lecture", "remets la musique", "remet la musique", "reprends la musique", "reprend la musique", "relance la musique", "relance la playlist", "lance la musique", "joue la musique", "remets la playlist", "remet la playlist"]):
        return await deezer_lecture_pause()
    if any(k in t for k in ["monte le volume", "augmente le son", "plus fort"]):
        return await deezer_volume("monter")
    if any(k in t for k in ["baisse le son", "baisse le volume", "moins fort"]):
        return await deezer_volume("baisser")

    # Recherche Deezer générique — en dernier pour ne pas avaler les commandes apps
    prefixes_recherche = ["joue du ", "joue de la ", "mets du ", "mets de la ", "joue ", "recherche ", "mets ", "lance ", "écoute ", "ecoute "]
    for prefix in prefixes_recherche:
        # On évite de chercher sur Deezer si c'est manifestement une recherche de fichier local
        if t.startswith(prefix) and not any(k in t for k in ["dossier", "fichier", "document", "ordinateur", "pc"]):
            recherche = t.replace(prefix, "").replace(" sur deezer", "").strip()
            if len(recherche) > 1:
                return await deezer_rechercher(recherche)

    # --- COFFRE-FORT CRYPTÉ (VOICE VAULT) ---
    if any(k in t for k in ["coffre fort", "coffre-fort", "coffre"]):
        # Import sans le préfixe « backend. » — cohérent avec le handler WebSocket
        # des boutons du panneau (ws_handler) et avec le reste du fichier. Les deux
        # formes chargeaient sinon le même fichier comme deux modules Python
        # distincts, chacun avec son propre état _is_unlocked : déverrouiller via
        # la voix ne déverrouillait pas la version vue par les boutons du HUD.
        from module import voice_vault
        async def _bc_vault(msg):
            if shared.CONNECTED_CLIENTS:
                try:
                    await asyncio.gather(*[ws.send(json.dumps(msg)) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
                except Exception:
                    pass

        if any(m in t for m in ["verrouille", "ferme", "bloque"]):
            voice_vault.lock_vault()
            m_out = {"type": "vault_lock_result", "is_unlocked": False}
            asyncio.create_task(_bc_vault(m_out))
            return "Le coffre-fort a été verrouillé avec succès, mylane."
        else:
            m_out = {
                "type": "vault_status",
                "is_configured": voice_vault.is_vault_configured(),
                "is_unlocked": voice_vault.is_vault_unlocked(),
                "files": voice_vault.list_vault_files() if voice_vault.is_vault_unlocked() else [],
                "force_open_hud": True
            }
            asyncio.create_task(_bc_vault(m_out))
            if voice_vault.is_vault_unlocked():
                return "Le coffre-fort est ouvert et vos fichiers sont accessibles, mylane."
            elif not voice_vault.is_vault_configured():
                return "J'ouvre le coffre-fort. Veuillez créer votre code PIN ou mot de passe de protection, mylane."
            else:
                return "J'ouvre le coffre-fort. Entrez votre code PIN pour déverrouiller vos fichiers, mylane."

    raccourcis_dossiers = {
        "bureau": "bureau", "documents": "documents",
        "téléchargements": "downloads", "téléchargement": "downloads",
        "images": "images", "vidéos": "videos", "musique": "musique"
    }
    for cle, chemin in raccourcis_dossiers.items():
        if f"ouvre mon {cle}" in t or f"ouvre le {cle}" in t or t == f"ouvre {cle}":
            ouvrir_dossier(chemin)
            return f"J'ouvre votre dossier {cle}, mylane."

    # --- DOSSIER / APPLICATION INCONNU(E) ---
    # Si l'utilisateur demande d'ouvrir/lancer quelque chose qu'on ne connait pas
    _mots_action = ["ouvre ", "lance ", "démarre ", "démarres ", "ouvrir ", "lancer ", "ouvre le ", "ouvre la ",
                     "ouvre mon ", "ouvre ma ", "lance le ", "lance la ", "lance mon ", "lance ma ",
                     "ouvre le dossier ", "ouvre mon dossier ", "ouvre l'application ", "lance l'application ",
                     "ouvre l'appli ", "lance l'appli ", "ouvre le logiciel ", "lance le logiciel "]
    for mot in _mots_action:
        if t.startswith(mot):
            nom_demande = t.replace(mot, "").strip().rstrip(".")
            if len(nom_demande) > 1:
                import random as _rnd
                _reponses_inconnu = [
                    f"Désolé mylane mon créateur n'a pas encore ajouté \"{nom_demande}\" dans mes fonctionnalités. Mais vous pouvez l'ajouter vous-même gratuitement avec le logiciel Antigravity de chez Google.",
                    f"Je ne connais pas \"{nom_demande}\" pour l'instant, mylane, mon développeur, n'a pas intégré cette fonction. Cependant, vous pouvez la créer facilement avec Antigravity de Google, c'est gratuit.",
                    f"Hmm, \"{nom_demande}\" ne fait pas partie de mes compétences actuelles. Mon créateur Mylane pourra peut-être l'ajouter dans une future mise à jour. En attendant, essayez Antigravity de Google pour personnaliser vos commandes gratuitement.",
                    f"\"{nom_demande}\" n'est pas dans ma base de données, mylane, n'a pas encore programmé cette action. Bonne nouvelle : avec Antigravity de chez Google, vous pouvez l'ajouter vous-même sans frais.",
                    f"Je ne suis pas encore capable d'ouvrir \"{nom_demande}\", mylane, mon créateur travaille constamment à m'améliorer. En attendant, le logiciel Antigravity de Google vous permet d'étendre mes fonctionnalités gratuitement.",
                    f"Cette fonctionnalité n'a pas été ajoutée par Mylane, mon créateur. Mais ne vous inquiétez pas, mylane, vous pouvez utiliser Antigravity de chez Google pour ajouter \"{nom_demande}\" gratuitement.",
                ]
                return _rnd.choice(_reponses_inconnu)

    return None
