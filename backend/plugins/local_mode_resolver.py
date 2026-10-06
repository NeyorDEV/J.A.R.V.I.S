import builtins
import re
import time
from core.interlocuteur import nom_espace

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_local_mode(cmd):
    t = nettoyer_accent(cmd.lower().strip())
    
    # Nettoyage de l'appel de réveil
    t = re.sub(r'^(jarvis|jervis|jarvys|jervys|gervis)(,)?\s*', '', t)
    
    # Détection des commandes d'activation du mode local
    mots_activation = [
        "active le mode local", "active le mode hors ligne", "active le mode hors-ligne",
        "active le mode offline", "active le mode off-line", "passe en mode local",
        "passe en mode hors ligne", "passe en mode hors-ligne", "passe en mode offline",
        "force le mode local", "force le mode hors ligne"
    ]
    
    # Détection des commandes de désactivation
    mots_desactivation = [
        "desactive le mode local", "desactive le mode hors ligne", "desactive le mode hors-ligne",
        "desactive le mode offline", "repasse en mode hybride", "passe en mode hybride",
        "desactive le mode off-line", "desactive le mode offline"
    ]
    
    # 1. ESSAI D'ACTIVATION
    if any(m in t for m in mots_activation) or t == "mode local" or t == "mode offline":
        print("[LOCAL RESOLVER] Commande d'activation du Mode Local détectée")
        builtins.FORCE_LOCAL_MODE = True
        
        # Réinitialiser le timeout de session
        builtins.dernier_message = time.time()
        
        # Envoyer une carte de succès néon sur le HUD
        if hasattr(builtins, "envoyer_carte_contextuelle"):
            await builtins.envoyer_carte_contextuelle(
                "Mode Local Forcé",
                "Mon cortex Ollama est désormais actif pour toutes vos demandes de réflexion.",
                type_carte="info",
                icon="⚙"
            )
            
        return f"Bien reçu{nom_espace()}, j'active le mode local. Toutes vos requêtes de réflexion seront désormais traitées hors-ligne par mon cortex Ollama."

    # 2. ESSAI DE DÉACTIVATION
    if any(m in t for m in mots_desactivation) or t == "mode hybride":
        print("[LOCAL RESOLVER] Commande de désactivation du Mode Local détectée")
        builtins.FORCE_LOCAL_MODE = False
        
        # Réinitialiser le timeout de session
        builtins.dernier_message = time.time()
        
        # Envoyer une carte de succès néon sur le HUD
        if hasattr(builtins, "envoyer_carte_contextuelle"):
            await builtins.envoyer_carte_contextuelle(
                "Mode Hybride Actif",
                "Bascule automatique sur mes cortex cloud ultra-puissants (Gemini, Claude, Groq).",
                type_carte="info",
                icon="◈"
            )
            
        return f"Bien reçu{nom_espace()}, je désactive le mode local. Je repasse en mode hybride avec mes cortex cloud."

    return None

# Enregistrement global dynamique dans builtins pour main2.py
builtins.resoudre_local_mode = resoudre_local_mode
