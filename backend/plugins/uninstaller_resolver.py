import builtins
import json
import asyncio
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_uninstaller_localement(texte):
    t = nettoyer_accent(texte.lower().strip())
    
    mots_cles = [
        "ouvre le desinstallateur", "ouvre le desinstalleur",
        "desinstalle un logiciel", "desinstaller un logiciel",
        "desinstalle un programme", "desinstaller un programme",
        "lance le desinstallateur", "lance le desinstalleur",
        "desinstallation de programme"
    ]
    
    if any(k in t for k in mots_cles):
        print("[UNINSTALLER RESOLVER] Commande d'ouverture du désinstallateur reçue.")
        
        if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
            msg = json.dumps({"type": "uninstaller_open"})
            try:
                await asyncio.gather(*[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)
            except Exception as e:
                print(f"[ERREUR WS] Broadcast uninstaller_open: {e}")
                
        return f"Très bien, j'ouvre la console du désinstallateur de programmes{nom_virgule()}."
        
    return None

# Injection globale dynamique
builtins.resoudre_uninstaller_localement = resoudre_uninstaller_localement
