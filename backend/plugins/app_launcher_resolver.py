import builtins
import subprocess
import os
import re
import asyncio
from core.interlocuteur import nom_espace, nom_virgule

# On importe les fonctions du fichier existant si possible
try:
    from controller.app_launcher import _APPS_CATALOGUE, _demarrer_appli_travail, mode_travail, mode_gaming, mode_rocket_league
except ImportError as _e_app:
    # Le repli ne définissait que _APPS_CATALOGUE : si l'import échouait,
    # « mode boulot » levait un NameError au lieu de retourner None, et
    # l'utilisateur n'avait qu'un silence sans explication.
    print(f"[APP LAUNCHER] Import du contrôleur impossible ({_e_app}) — modes désactivés.")
    _APPS_CATALOGUE = {}

    def _demarrer_appli_travail(*args, **kwargs):
        return False

    async def _mode_indisponible(*args, **kwargs):
        return ("Le module de lancement d'applications n'est pas disponible sur "
                f"cette installation{nom_virgule()}.")

    mode_travail = mode_gaming = mode_rocket_league = _mode_indisponible

async def resoudre_apps_localement(texte):
    """Gère l'ouverture et la fermeture des applications PC et les modes de travail/jeu."""
    t = texte.lower().strip()
    
    # S'il s'agit d'une commande complexe avec des enchaînements ou des actions DOM/saisie,
    # on renvoie None pour laisser le "cerveau" IA (LLM) s'en occuper de façon autonome.
    if any(k in t for k in ["saisis", "clique", "tape", "ecris", "remplace", "dans la", "barre de", " et ", " puis "]):
        return None
        
    # 1. GESTION DES MODES
    if any(k in t for k in ["mode boulot", "mode travail", "espace de travail"]):
        return await mode_travail()
    if any(k in t for k in ["mode gaming", "mode jeu", "lance un jeu"]):
        return await mode_gaming()
    if any(k in t for k in ["mode rocket league", "lance rocket league"]):
        return await mode_rocket_league()

    # 2. OUVERTURE D'APPLICATIONS (Via Catalogue)
    if any(k in t for k in ["ouvre", "lance", "demarre"]):
        for app_key, data in _APPS_CATALOGUE.items():
            # Mot entier : « ea » (EA App) était trouvé dans réseau, tableau, bureau,
            # beatles… (« lance le radar réseau » lançait EA App).
            if re.search(rf"(?<![\w-]){re.escape(app_key)}(?![\w-])", t):
                success = _demarrer_appli_travail(data["label"], data["noms"], data.get("hints"))
                if success: return f"J'ai lancé {data['label']} pour vous{nom_virgule()}."
                return f"Je n'ai pas pu localiser {data['label']} sur votre système."

    if any(m in t for m in ["musique", "playlist"]) and any(k in t for k in ["mets", "joue", "lance", "écoute", "ecoute", "play", "active", "démarre", "demarre"]):
        if any(w in t for w in ["remets", "remet", "reprends", "reprend", "relance", "suivant", "précédent", "precedent"]):
            return None
            
        # Extraire la requête spécifique de musique/playlist
        # Si l'utilisateur a spécifié un nom (ex: "joue ma playlist teenage dirtbag"),
        # on renvoie None pour laisser l'orchestrateur principal gérer la recherche sur Deezer.
        query_normalized = t
        for verb in ["joue", "jouer", "mets", "mettre", "lance", "lancer", "écoute", "ecoute", "écouter", "ecouter", "play", "active", "activer", "démarre", "demarre", "démarrer", "demarrer"]:
            query_normalized = re.sub(rf"\b{verb}\b", "", query_normalized)
        for article in ["ma", "la", "mon", "le", "un", "une", "des", "du", "de", "de la", "d'", "votre", "notre", "mes", "les", "moi"]:
            query_normalized = re.sub(rf"\b{article}\b", "", query_normalized)
        for noun in ["musique", "playlist", "chanson", "piste", "titre", "album", "artiste", "son"]:
            query_normalized = re.sub(rf"\b{noun}\b", "", query_normalized)
        # Formules d'envie et ponctuation : « j'ai envie d'écouter de la musique » donnait la
        # « requête » « j'ai envie d' . », partait en recherche puis à l'IA au lieu de la playlist
        query_normalized = re.sub(r"\b(j'ai envie|envie|je veux|j'aimerais|je voudrais|j'ai besoin|"
                                  r"bien|un peu|peu|s'il te pla[iî]t|stp|svp|jarvis|moi|nous)\b", "", query_normalized)
        query_normalized = re.sub(r"\b(d|de|l)'|[^\w\s'-]", " ", query_normalized)

        specific_query = query_normalized.strip()
        if specific_query:
            # Il y a un nom de playlist ou d'artiste spécifique, on délègue à la recherche Deezer
            print(f"[RESOLVER] Requête spécifique détectée : '{specific_query}'. Délégation à la recherche.")
            return None

        import webbrowser
        try:
            import pyautogui
        except ImportError:
            pyautogui = None
            
        import json as _j
        lien_perso = ""
        try:
            _p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "jarvis_config.json")  # backend/plugins/ -> racine projet
            with open(_p, "r", encoding="utf-8") as _f:
                lien_perso = _j.load(_f).get("musique_lien", "").strip()
        except: pass
        
        
        if "youtube" in t or (lien_perso and "youtube.com" in lien_perso):
            url = lien_perso if lien_perso else "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            if pyautogui:
                asyncio.create_task(asyncio.sleep(5)).add_done_callback(lambda _: pyautogui.press('f'))
            return f"C'est parti{nom_espace()}, votre musique démarre sur YouTube."
        elif lien_perso:
            webbrowser.open(lien_perso, new=2)
            return f"C'est parti{nom_espace()}, je lance votre musique personnalisée."
        elif "spotify" in t:
            try:
                subprocess.Popen(["explorer", "spotify:"], shell=False)
                return f"C'est parti{nom_espace()}, votre playlist démarre sur Spotify."
            except: pass
        else:
            # Par défaut, on lance la playlist sur Deezer
            try:
                from controller.deezer_controller import deezer_lancer_playlist
                asyncio.create_task(deezer_lancer_playlist())
                return f"C'est parti{nom_espace()}, je lance votre playlist sur Deezer."
            except Exception as e:
                print(f"[RESOLVER] Échec import/lancement Deezer : {e}")
                try:
                    subprocess.Popen(["explorer", "deezer:"], shell=False)
                    return f"C'est parti{nom_espace()}, votre musique démarre sur Deezer."
                except:
                    pass

    # 4. ACTIONS SYSTÈME RAPIDES
    # (« explorateur spatial / 3D » est la vue 3D de JARVIS, et « ferme ... » une
    #  fermeture : ces phrases sont laissées aux commandes locales.)
    if any(k in t for k in ["explorateur", "mes dossiers", "mes fichiers"])             and not any(k in t for k in ["spatial", "3d", "ferme", "quitte"]):
        subprocess.Popen(["explorer.exe"])
        return f"Explorateur de fichiers ouvert{nom_virgule()}."
    if any(k in t for k in ["notepad", "bloc-notes", "note rapide"]):
        subprocess.Popen(["notepad.exe"])
        return f"Bloc-notes ouvert pour vos notes{nom_virgule()}."

    return None

# Injection builtins
builtins.resoudre_apps_localement = resoudre_apps_localement
