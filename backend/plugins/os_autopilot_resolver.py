import builtins
import re
import asyncio
from module.os_autopilot_agent import lancer_autopilote
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_os_autopilot(cmd):
    t = nettoyer_accent(cmd.lower().strip())
    
    # Nettoyage des variantes du mot-clé de réveil (VAD phonétique)
    t = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t)
    
    # Détection des mots-clés d'activation de l'autopilote OS
    mots_cles_autopilote = [
        "lance l'autopilote os", "lance l'autopilote", "lance l'auto pilote",
        "autopilote os", "autopilote", "mode autopilote", "controle os",
        "controle l'os", "commande l'os", "rpa systeme", "rpa"
    ]
    
    match = False
    declencheur = ""
    for kw in mots_cles_autopilote:
        # Mot entier : « rpa » était trouvé dans « carpaccio » (« recette du carpaccio »
        # lançait l'autopilote, qui prend la main sur la souris et le clavier).
        if re.search(rf"(?<![\w']){re.escape(kw)}(?![\w])", t):
            match = True
            declencheur = kw
            break
            
    if match or t.startswith("autopilote ") or t.startswith("rpa "):
        print(f"[OS RESOLVER] Commande d'autopilote OS détectée : {cmd}")
        
        # Extraction de la consigne (ce qui vient après le déclencheur)
        consigne = cmd
        if declencheur:
            # Recherche de la position d'origine du déclencheur dans la commande brute pour couper proprement
            idx = nettoyer_accent(cmd.lower()).find(declencheur)
            if idx != -1:
                consigne = cmd[idx + len(declencheur):].strip()
                
        # Si la consigne est vide, demander des précisions
        if not consigne or len(consigne) < 3:
            return f"Quelle tâche souhaitez-vous que je réalise avec l'autopilote OS{nom_virgule()} ?"
            
        # Nettoyage des premiers mots de liaison éventuels (ex: ":", "de", "pour")
        consigne = re.sub(r'^(\s*[:,-]\s*|\s*de\s*|\s*pour\s*|\s*a\s*)', '', consigne, flags=re.IGNORECASE).strip()
        
        # Appel de l'agent asynchrone pour la planification et l'exécution
        reponse = await lancer_autopilote(consigne)
        return reponse

    return None

# Injection globale dans builtins pour enregistrement dynamique
builtins.resoudre_os_autopilot = resoudre_os_autopilot
