import os
import re
import asyncio
import builtins
import webbrowser
import unicodedata
# NB : import sans le préfixe « backend. » — main.py ajoute backend/ au
# sys.path. Mélanger les deux formes chargeait le MÊME fichier deux fois
# comme deux modules distincts, avec des états globaux dupliqués.
from core.interlocuteur import nom_espace, nom_virgule
def nettoyer_accent(texte: str) -> str:
    """Supprime les accents et met en minuscules pour faciliter la comparaison."""
    return "".join(c for c in unicodedata.normalize('NFD', texte.lower().strip()) if unicodedata.category(c) != 'Mn')
async def resoudre_lancer_enigme(cmd: str):
    """
    Résout la commande vocale ou écrite pour lancer le jeu d'énigmes secret d'anniversaire.
    Exemples:
    - "JARVIS lance l'énigme"
    - "JARVIS lance l'enigme"
    - "démarre l'énigme"
    - "ouvre l'énigme"
    - "lance le jeu des énigmes"
    """
    t_clean = nettoyer_accent(cmd)
    t_clean = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t_clean)
    
    mots_cles = [
        "lance l'enigme", "lance l enigme", "lance lenigme", "lance enigme",
        "demarre l'enigme", "demarre l enigme", "demarre lenigme", "demarre enigme",
        "ouvre l'enigme", "ouvre l enigme", "ouvre lenigme", "ouvre enigme",
        "lance le jeu des enigmes", "lance les enigmes", "active l'enigme", "lance le site enigme"
    ]
    
    if not any(kw in t_clean for kw in mots_cles):
        return None
        
    print(f"[bold magenta]🔮 [ENIGME RESOLVER][/bold magenta] [bold yellow]✨ Lancement du protocole d'énigme secret :[/bold yellow] [bold green]'{cmd}'[/bold green]")
    
    _dir_courant = os.path.dirname(os.path.abspath(__file__))
    site_path = os.path.abspath(os.path.join(_dir_courant, "..", "sandbox", "surprise_disney", "index.html"))
    # Le site n'est pas versionné : sans lui, un navigateur s'ouvrait en plein écran sur
    # une page introuvable.
    if not os.path.exists(site_path):
        print(f"[ENIGME RESOLVER] Site introuvable : {site_path}")
        return f"Le site de l'énigme est introuvable sur cet ordinateur{nom_virgule()}."
    file_url = f"file:///{site_path.replace('\\', '/')}"
    http_url = "http://localhost:8088"
    launched = False
    local_app = os.environ.get("LOCALAPPDATA", "")
    browsers = [
        os.path.join(local_app, "Programs", "Opera GX", "opera.exe"),
        os.path.join(local_app, "Programs", "Opera", "opera.exe"),
        r"C:\Program Files\Opera GX\opera.exe",
        r"C:\Program Files\Opera\opera.exe",
        r"C:\Program Files (x86)\Opera GX\opera.exe",
        r"C:\Program Files (x86)\Opera\opera.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    
    import subprocess
    for b_path in browsers:
        if os.path.exists(b_path):
            try:
                subprocess.Popen([b_path, "--start-fullscreen", file_url])
                launched = True
                break
            except Exception as e:
                print(f"[ENIGME FULLSCREEN LAUNCH ERROR] {e}")
                
    if not launched:
        try:
            webbrowser.open(http_url)
        except Exception as e:
            print(f"[ENIGME RESOLVER ERROR] {e}")
    
    # (send_web_action n'accepte pas title / type / icon : la carte n'apparaissait jamais)
    if hasattr(builtins, "envoyer_carte_contextuelle"):
        try:
            await builtins.envoyer_carte_contextuelle("PROTOCOLE ÉNIGME", "Lancement du coffre-fort d'énigmes d'anniversaire.",
                                                      type_carte="info", icon="🔐")
        except Exception:
            pass
    return f"Très bien{nom_espace()}, activation immédiate du protocole d'énigme secret. Bonne chance !"
async def resoudre_creation_site_web(cmd: str):
    """
    Résout les commandes vocales et écrites liées à la création de sites internet.
    """
    t_clean = nettoyer_accent(cmd)
    t_clean = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t_clean).strip()
    
    verbes = ["cree", "creer", "genere", "generer", "fais", "fabrique", "concois", "construis", "developpe"]
    noms = ["site", "page web", "application web", "app web", "projet web"]

    # Mots entiers seulement : « visite » contient « site » (« fais une visite guidée du
    # château » lançait l'essaim de 6 agents).
    has_verbe = any(re.search(rf'\b{v}\b', t_clean) for v in verbes)
    has_nom = any(re.search(rf'\b{n}\b', t_clean) for n in noms)

    if not (has_verbe and has_nom):
        return None

    # Sécurité mode invité : lancer le swarm de développement est une action
    # lourde et coûteuse (6 agents LLM, écriture de fichiers sur le disque,
    # plusieurs minutes de traitement). Contrairement aux actions JSON de l'IA
    # conversationnelle, ce chemin par resolver n'était couvert par AUCUN
    # contrôle — une voix non reconnue (« guest ») pouvait le déclencher.
    if getattr(builtins, "ACTIVE_SPEAKER", "neyor") == "guest":
        print("🔒 [WEBSITE RESOLVER] Création de site refusée : locuteur non authentifié (invité).")
        return f"Désolé, la création de site web est réservée aux utilisateurs authentifiés. Veuillez vous identifier{nom_virgule()}."

    print(f"[WEBSITE RESOLVER] Mobilisation de l'Essaim d'IA (Dev Swarm) pour : '{cmd}'")
    
    consigne = cmd
    consigne = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', consigne, flags=re.IGNORECASE).strip()
    
    from plugins.dev_swarm_resolver import run_dev_swarm_process
    asyncio.create_task(run_dev_swarm_process(consigne))
    return "Très bien, je mobilise les agents pour coder votre projet. Suivi actif sur le HUD."
async def resoudre_ouvrir_site_web(cmd: str):
    """
    Résout les commandes vocales/écrites d'ouverture des sites web créés (ex: "ouvre moi le site apexmind").
    """
    t_clean = nettoyer_accent(cmd.lower())
    t_clean = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t_clean).strip()
    
    mots_ouverture = ["ouvre", "ouvrir", "lance", "lancer", "affiche", "afficher", "montre", "montrer", "visite", "visiter"]
    mots_site = ["site", "projet", "application", "app", "page"]
    
    if not (any(v in t_clean for v in mots_ouverture) and any(s in t_clean for s in mots_site)):
        return None
        
    _dir_courant = os.path.dirname(os.path.abspath(__file__))
    sandbox_dir = os.path.abspath(os.path.join(_dir_courant, "..", "sandbox"))
    
    if not os.path.exists(sandbox_dir):
        return None
        
    matched_dir = None
    matched_name = None
    
    for item in os.listdir(sandbox_dir):
        full_p = os.path.join(sandbox_dir, item)
        if os.path.isdir(full_p):
            item_tokens = [t for t in item.lower().replace('_', ' ').split() if len(t) >= 4]
            if item.lower() in t_clean or any(token in t_clean for token in item_tokens):
                matched_dir = full_p
                matched_name = item
                break
    if matched_dir:
        index_file = os.path.join(matched_dir, "index.html")
        if not os.path.exists(index_file):
            html_files = [os.path.join(r, f) for r, _, fs in os.walk(matched_dir) for f in fs if f.endswith('.html')]
            index_file = html_files[0] if html_files else None
            
        if index_file:
            file_url = f"file:///{index_file.replace('\\', '/')}"
            local_app = os.environ.get("LOCALAPPDATA", "")
            browsers = [
                os.path.join(local_app, "Programs", "Opera GX", "opera.exe"),
                os.path.join(local_app, "Programs", "Opera", "opera.exe"),
                r"C:\Program Files\Opera GX\opera.exe",
                r"C:\Program Files\Opera\opera.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
            ]
            import subprocess
            launched = False
            for b_path in browsers:
                if os.path.exists(b_path):
                    try:
                        subprocess.Popen([b_path, "--start-fullscreen", file_url])
                        launched = True
                        break
                    except Exception as e:
                        print(f"[WEBSITE OPEN LAUNCH ERROR] {e}")
                        
            if not launched:
                import webbrowser
                webbrowser.open(file_url)
                
            print(f"[WEBSITE RESOLVER] Ouverture du site '{matched_name}' -> {file_url}")
            return f"Très bien{nom_espace()}, ouverture immédiate du site '{matched_name}' en plein écran."
            
    return None
# Enregistrement dans builtins pour découverte automatique par main.py
builtins.resoudre_lancer_enigme = resoudre_lancer_enigme
builtins.resoudre_creation_site_web = resoudre_creation_site_web
builtins.resoudre_ouvrir_site_web = resoudre_ouvrir_site_web