"""Commandes locales sans IA (suite) : identité, aide, HUD 3D, apps, musique, coffre-fort."""

import asyncio
import json
import os
import re
import subprocess
import webbrowser

import pyautogui

import core.shared as shared
from controller.app_launcher import (
    _APPS_CATALOGUE, _demarrer_appli_travail, _arreter_appli, mode_travail, mode_gaming, mode_rocket_league,
)
from controller.deezer_controller import (
    deezer_lancer_playlist, deezer_basculer_lecture, deezer_demarrer, deezer_piste_precedente,
    deezer_chercher, deezer_arreter, deezer_piste_suivante, deezer_regler_volume,
)
from core.web_bridge import _safe_ws_send
from module.file_manager import disposer_fenetres_dossiers, afficher_dossier
from core.interlocuteur import nom_espace, nom_virgule

# Fermeture forcée permise si la demande de fermeture est ignorée au bout de 3 s : musique,
# messageries, lanceurs (ils se cachent dans la zone de notification au lieu de quitter).
# Les autres (Word, Excel, éditeurs…) ne sont jamais forcés : ils peuvent demander d'enregistrer.
_FERMETURE_FORCEE = {"deezer", "spotify", "discord", "steam", "epic", "epic games", "epic game", "origin",
                     "ea", "ea app", "ubisoft", "ubisoft connect", "uplay", "gog", "gog galaxy", "whatsapp",
                     "telegram", "teams", "microsoft teams", "zoom", "skype", "vlc", "obs", "obs studio",
                     "minecraft"}


_PAS_TROUVE = object()  # sentinelle : section sans résultat, on passe à la suivante

_MOTS_MUSIQUE = ("musique", "chanson", "piste", "morceau", "titre", "playlist", "album",
                 "artiste", "deezer", "son de", "le son", "single", "tube", "rap", "rock")
# Jamais une recherche Deezer : ces phrases relèvent d'autres commandes ou de l'IA.
_MOTS_NON_MUSICAUX = ("alarme", "minuteur", "réveil", "reveil", "rappel", "timer", "info",
                      "actualité", "actualite", "météo", "meteo", "heure", "lumière", "lumiere",
                      "chauffage", "volet", "télé", "tele", " tv", "vidéo", "video", "film",
                      "série", "serie", "youtube", "netflix", "site", "page", "mail", "message",
                      "application", "logiciel", "programme", "jeu ", "partie", "dossier",
                      "fichier", "document", "ordinateur", " pc", "recette", "photo", "image",
                      "recherche sur", "une recherche", "scan", "mise à jour", "mises à jour")


def _contexte_musical(t: str) -> bool:
    return any(m in t for m in _MOTS_MUSIQUE)


def _recherche_musicale(t: str):
    """Texte à chercher sur Deezer si la phrase est une demande de musique, sinon None."""
    if any(m in f" {t} " for m in _MOTS_NON_MUSICAUX):
        return None
    musical = _contexte_musical(t)
    for prefix in ("joue du ", "joue de la ", "joue des ", "joue ", "écoute ", "ecoute ",
                   "mets du ", "mets de la ", "mets des ", "mets ", "lance ", "recherche "):
        if not t.startswith(prefix):
            continue
        verbe_musical = prefix.startswith(("joue", "écoute", "ecoute")) \
            or prefix in ("mets du ", "mets de la ", "mets des ")
        if not (verbe_musical or musical):
            return None
        recherche = t[len(prefix):].replace(" sur deezer", "").strip()
        # « la chanson hello d'adele » → « hello d'adele » (« album » / « playlist » sont
        # gardés : deezer_chercher s'en sert pour choisir le type de recherche)
        recherche = re.sub(r"^(?:(?:la |le |l'|une |un |ma |mon )?(?:chanson|titre|morceau|musique|son)\s+(?:de |d')?)",
                           "", recherche).strip()
        return recherche if len(recherche) > 1 else None
    return None


async def _commandes_identite_hud(t):
    """Aide, dossiers, explorateur 3D, carte domotique, cortex, orbe, démo."""
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
            async def _orienter_aide():
                msg = json.dumps({"action": "help"})
                await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
            asyncio.create_task(_orienter_aide())

        # Le panneau d'aide s'affiche ; la réponse parlée est laissée à l'IA (personnalité
        # JARVIS, voir core/prompt_builder.py) plutôt qu'à une phrase toute faite.
        return None

    # --- DOSSIERS (Priorité 1) ---
    if any(k in t for k in ["mosaïque dossiers", "range mes dossiers", "range les dossiers", "range tous les dossiers", "range tous mes dossiers", "mosaïque"]):
        return disposer_fenetres_dossiers()

    # --- FERMETURE DES VUES 3D (explorateur, maison, cortex, radar) ---
    # Avant les commandes d'ouverture : « ferme le cortex » contient « cortex ».
    # (Les échecs ont leur propre « quitte les échecs », qui arrête aussi la partie.)
    if any(k in t for k in [
        "ferme le cortex", "ferme ton cortex", "quitte le cortex", "ferme l'explorateur spatial", "ferme l'explorateur 3d",
        "ferme la carte domotique", "ferme la carte 3d", "ferme la maison", "ferme ma maison", "ferme le radar",
        "ferme la vue 3d", "quitte la vue 3d", "ferme les vues 3d", "ferme la 3d", "retour jarvis",
        "ferme l'hologramme", "désactive l'hologramme", "desactive l'hologramme",
        "désactive le mode hologramme", "desactive le mode hologramme", "ferme le mode holo",
    ]):
        _safe_ws_send(json.dumps({"action": "close_3d_view"}))
        return f"Vue 3D fermée{nom_virgule()}."

    # --- MODE EXPLORATEUR SPATIAL 3D ---
    if any(k in t for k in [
        "ouvre tous les dossiers", "ouvre tous mes dossiers", "ouvre mes dossiers", "ouvre les dossiers", 
        "mes dossiers", "montre moi mes dossiers", "montre mes dossiers", "explorateur 3d", "explorateur spatial", 
        "dossier spatial", "explorateur spatial 3d", "mode explorer", "affiche l'explorateur", 
        "ouvre l'explorateur spatial", "affiche mes fichiers"
    ]):
        _safe_ws_send(json.dumps({"action": "open_spatial_explorer"}))
        return f"Déploiement de l'explorateur spatial 3D{nom_virgule()}."

    # --- MODE CARTE 3D DOMOTIQUE ---
    if any(k in t for k in [
        "affiche ma maison", "affiche la maison", "carte domotique", "mode carte 3d", "mode carte", 
        "carte 3d", "affiche la carte 3d", "affiche la carte de la maison", "affiche la carte domotique", 
        "ma maison 3d"
    ]):
        _safe_ws_send(json.dumps({"action": "open_domotic_map"}))
        return f"Déploiement de la carte domotique 3D{nom_virgule()}."

    # --- RECHERCHE SÉMANTIQUE VISUELLE CORTEX ---
    if any(p in t for p in ["cherche dans mon cortex", "cherche dans le cortex", "trouve dans mon cortex", "trouve dans le cortex"]):
        query = t
        for prefix in ["cherche dans mon cortex", "cherche dans le cortex", "trouve dans mon cortex", "trouve dans le cortex"]:
            if prefix in query:
                query = query.replace(prefix, "").strip()
        query = query.replace("?", "").strip()
        if len(query) > 1:
            _safe_ws_send(json.dumps({"action": "cortex_search", "query": query}))
            return f"Recherche de '{query}' initiée dans mon cortex neuronal{nom_virgule()}."
        return f"Que souhaitez-vous chercher dans votre cortex{nom_virgule()} ?"

    # --- MODE CORTEX 3D ---
    if any(k in t for k in [
        "cortex", "affiche ton cortex", "affiche le cortex", "mode cortex", "ouvre le cortex", 
        "ouvre ton cortex", "connexions neuronales", "cortex neuronal"
    ]):
        _safe_ws_send(json.dumps({"action": "open_cortex"}))
        return f"Déploiement du cortex neuronal 3D{nom_virgule()}."

    # --- NARRATION VOCALE DE SOUVENIR ---
    if any(p in t for p in ["lis ce souvenir", "raconte ce souvenir", "lis la mémoire", "raconte cette mémoire", "lis le souvenir"]):
        _safe_ws_send(json.dumps({"action": "cortex_vocal_speak_request"}))
        return f"C'est entendu{nom_virgule()}. Lecture du souvenir actif..."

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
        return f"Très bien{nom_espace()}, je reconfigure l'orbe pour dessiner le mot : {word}."

    # --- DECLENCHEMENT PROTOCOLE DEMONSTRATION ORBE ---
    if any(k in t for k in ["démonstration", "demonstration", "démo", "demo", "lance la démo", "lance une démo", "lance une démonstration", "lance la démonstration", "protocole de démo", "fais une démo", "fais une demo"]):
        _safe_ws_send(json.dumps({"action": "demo"}))
        return f"Initialisation du protocole de démonstration visuelle{nom_virgule()}."

    # (« mets » n'ouvre pas de dossier : « mets en pause le téléchargement » y passait)
    prefixes_dossiers = ["ouvre le dossier ", "ouvre mon dossier ", "ouvre le répertoire ", "ouvre le repertoire ", "ouvre dossier ", "ouvre "]
    # On vérifie d'abord si c'est un dossier connu
    mots_cles_dossiers = ["bureau", "document", "téléchargement", "image", "photo", "vidéo", "musique", "corbeille"]
    # --- LOGIQUE MULTIMÉDIA (TV/YouTube) MIGRÉE VERS plugins/system_resolver.py ---

    # --- DOSSIERS (Priorité 1) ---
    for prefix in prefixes_dossiers:
        if t.startswith(prefix):
            potentiel_dossier = t[len(prefix):].strip()
            # « ouvre la musique », « ouvre mes documents » : l'article empêchait de
            # reconnaître le dossier (« la musique » n'est pas un raccourci connu).
            nom_dossier = re.sub(r"^(?:le |la |les |l'|mon |ma |mes |du |des )", "", potentiel_dossier).strip()
            if any(k in nom_dossier for k in mots_cles_dossiers):
                ok, msg = afficher_dossier(nom_dossier)
                if ok: return f"J'ouvre le dossier {nom_dossier}{nom_virgule()}."
    return _PAS_TROUVE


async def _commandes_apps_musique(t):
    """Modes boulot/gaming, applications, musique/Deezer, coffre-fort, dossiers, demandes inconnues."""
    # --- MODE BOULOT (Priorité 1 bis) ---
    if any(k in t for k in ["au boulot", "mode boulot", "mode travail", "on bosse", "mode bureau", "commence le boulot"]):
        return await mode_travail()

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
    # « ouvre la calculatrice », « ouvre le bloc-notes » : l'article était refusé
    # (seul « ouvre calculatrice » marchait).
    verbes_ouvrir = "|".join(re.escape(m) for m in mots_ouvrir)
    for nom, cmd in apps_standard.items():
        if re.search(rf"\b(?:{verbes_ouvrir})\s+(?:le |la |les |l'|un |une |mon |ma |mes )?{re.escape(nom)}\b", t):
            try:
                subprocess.Popen(cmd)
                return f"J'ouvre {nom}{nom_virgule()}."
            except Exception:
                return f"Désolé{nom_espace()}, je n'ai pas réussi à lancer {nom}."

    # Deezer (piloté par controller/deezer_controller, hors catalogue) peut aussi être fermé
    catalogue = dict(_APPS_CATALOGUE)
    catalogue["deezer"] = {"label": "Deezer", "noms": ["Deezer.exe"], "fermeture_seule": True}
    for cle in sorted(catalogue, key=len, reverse=True):  # « ea app » avant « ea »
        info = catalogue[cle]
        # On vérifie que la clé est un mot entier pour éviter "ea" dans "Billie Jean"
        if not re.search(rf"\b{re.escape(cle)}\b", t):
            continue

        if any(re.search(rf"\b{re.escape(m)}\b", t) for m in mots_fermer):
            if getattr(shared, "ACTIVE_SPEAKER", "guest") == "guest":
                return "Je ne ferme pas d'application pour une voix que je ne reconnais pas."
            ok = await asyncio.to_thread(_arreter_appli, info["noms"], cle in _FERMETURE_FORCEE)
            if ok:
                return f"J'ai fermé {info['label']}{nom_virgule()}."
            if ok is None:
                return f"{info['label']} n'est pas ouvert{nom_virgule()}."
            return f"{info['label']} n'a pas voulu se fermer : il attend peut-être une réponse de votre part{nom_virgule()}."
        if info.get("fermeture_seule"):
            continue
        if any(m in t for m in mots_ouvrir):
            _demarrer_appli_travail(info["label"], info["noms"], chemins_hints=info["hints"])
            return f"Je lance {info['label']}{nom_virgule()}."

    # (Bloc YouTube PC supprimé pour éviter les conflits avec la TV)

    # --- SPOTIFY / MUSIQUE (Priorité 3) ---
    # YouTube music spécifique — doit être AVANT le check Spotify
    if any(k in t for k in ["musique sur youtube", "met de la musique sur youtube", "mets de la musique sur youtube"]):
        url = shared.YOUTUBE_MUSIQUE_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
        webbrowser.open(url, new=2)
        await asyncio.sleep(5)
        pyautogui.press('f')
        return f"C'est parti{nom_espace()}, votre musique démarre sur YouTube."

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
                    await asyncio.sleep(5)
                    pyautogui.press('f')
                    return f"C'est parti{nom_espace()}, votre musique démarre sur YouTube."
                elif "spotify" in musique_lien_lower or musique_lien_lower.startswith("spotify:"):
                    try:
                        from controller.spotify_controller import spotify_jouer_playlist
                        ok = spotify_jouer_playlist(musique_lien)
                        if ok:
                            return f"C'est parti{nom_espace()}, je lance votre musique sur Spotify."
                    except: pass
                    return f"Je n'ai pas réussi à ouvrir Spotify{nom_virgule()}."
                elif "deezer" in musique_lien_lower:
                    ok = await deezer_lancer_playlist(musique_lien)
                    if ok:
                        return f"C'est parti{nom_espace()}, je lance votre musique sur Deezer."
                    return f"Je n'ai pas réussi à ouvrir Deezer{nom_virgule()}."
                else:
                    # Lien générique
                    webbrowser.open(musique_lien, new=2)
                    return f"C'est parti{nom_espace()}, je lance votre lien de musique personnalisé dans le navigateur."
            else:
                # Fallback par défaut sur Deezer
                ok = await deezer_lancer_playlist()
                if ok:
                    return f"C'est parti{nom_espace()}, je lance votre playlist sur Deezer."
                return f"Je n'ai pas réussi à ouvrir Deezer{nom_virgule()}."

    if any(k in t for k in ["ouvre deezer", "lance deezer"]):
        return await deezer_demarrer()

    # Ces mots (« suivant », « précédent », « pause », « lecture ») ne valent commande
    # musicale que dans une phrase courte ou qui parle de musique : « le jour précédent »
    # ou « fais-moi la lecture de ce mail » changeaient de morceau / relançaient Deezer.
    musical = _contexte_musical(t)
    courte = len(t.split()) <= 4
    # « passe la musique », « change de chanson », « zappe ce morceau » : morceau suivant
    # (« passe la musique » relançait la playlist, via l'aiguillage IA)
    passer = re.search(r"\b(passe|passer|zappe|zapper|change|changer)\b.*\b(musique|chanson|morceau|titre|son)\b", t)
    if passer or ((musical or courte) and any(k in t for k in ["suivante", "suivant", "musique d'après", "musique d'apres"])):
        return await deezer_piste_suivante()
    if (musical or courte) and any(k in t for k in ["précédente", "précédent", "precedente", "precedent", "reviens en arrière", "retour en arrière", "musique d'avant"]):
        return await deezer_piste_precedente()
    if any(k in t for k in ["stop la musique", "arrête la musique", "arrete la musique", "arrête la playlist", "arrete la playlist"]) \
            or ((musical or courte) and "pause" in t):
        return await deezer_arreter()
    if any(k in t for k in ["remets la musique", "remet la musique", "reprends la musique", "reprend la musique", "relance la musique", "relance la playlist", "lance la musique", "joue la musique", "remets la playlist", "remet la playlist"]) \
            or ((musical or courte) and "lecture" in t):
        return await deezer_basculer_lecture()
    # Volume de Deezer seulement s'il est question de musique ; sinon le volume du PC
    # (system_resolver) : « baisse le volume » tout court réglait l'un ou l'autre selon
    # le verbe employé, et « le volume du HomePod » finissait dans Deezer.
    if musical and not any(k in t for k in ["homepod", "enceinte", "télé", "tele", " tv"]):
        if any(k in t for k in ["monte le volume", "monte le son", "augmente le son", "augmente le volume", "plus fort"]):
            return await deezer_regler_volume("monter")
        if any(k in t for k in ["baisse le son", "baisse le volume", "moins fort"]):
            return await deezer_regler_volume("baisser")

    # Recherche Deezer générique — en dernier pour ne pas avaler les commandes apps.
    # « joue / écoute » sont des verbes musicaux ; « mets / lance / recherche » ne le sont
    # que s'il est question de musique : sinon « mets une alarme à 7 h », « lance une
    # recherche sur Napoléon »… partaient dans Deezer au lieu d'atteindre l'IA.
    recherche_deezer = _recherche_musicale(t)
    if recherche_deezer:
        return await deezer_chercher(recherche_deezer)

    # --- COFFRE-FORT CRYPTÉ (VOICE VAULT) ---
    if any(k in t for k in ["coffre fort", "coffre-fort", "coffre"]) and getattr(shared, "ACTIVE_SPEAKER", "guest") == "guest":
        # Mode invité : une voix inconnue voyait la liste des fichiers d'un coffre déverrouillé
        return f"Le coffre-fort est réservé aux utilisateurs reconnus{nom_virgule()}."
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
            return f"Le coffre-fort a été verrouillé avec succès{nom_virgule()}."
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
                return f"Le coffre-fort est ouvert et vos fichiers sont accessibles{nom_virgule()}."
            elif not voice_vault.is_vault_configured():
                return f"J'ouvre le coffre-fort. Veuillez créer votre code PIN ou mot de passe de protection{nom_virgule()}."
            else:
                return f"J'ouvre le coffre-fort. Entrez votre code PIN pour déverrouiller vos fichiers{nom_virgule()}."

    raccourcis_dossiers = {
        "bureau": "bureau", "documents": "documents",
        "téléchargements": "downloads", "téléchargement": "downloads",
        "images": "images", "vidéos": "videos", "musique": "musique"
    }
    for cle, chemin in raccourcis_dossiers.items():
        if f"ouvre mon {cle}" in t or f"ouvre le {cle}" in t or t == f"ouvre {cle}":
            afficher_dossier(chemin)
            return f"J'ouvre votre dossier {cle}{nom_virgule()}."

    # Application / dossier inconnu : plus de phrase toute faite, l'IA répond elle-même
    # (consigne dédiée dans core/prompt_builder.py).

    return None
