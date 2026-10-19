import builtins
import json
import asyncio
from module.image_search import images_par_moteur
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

async def resoudre_images_locales(texte):
    t = nettoyer_accent(texte.lower().strip())
    
    # Liste des expressions régulières ou préfixes de recherche d'images
    _images_prefixes = [
        "montre-moi des images de ", "montre moi des images de ",
        "montre-moi des photos de ", "montre moi des photos de ",
        "montre-moi une photo de ", "montre moi une photo de ",
        "montre-moi un dessin de ", "montre moi un dessin de ",
        "montre-moi un visuel de ", "montre moi un visuel de ",
        "affiche des images de ", "cherche des images de ",
        "cherche des photos de ", "affiche des photos de ",
        "affiche une image de ", "affiche une photo de ",
        "affiche-moi une image de ", "affiche-moi une photo de ",
        "affiche moi des images de ", "affiche moi des photos de ",
        "je veux voir des images de ", "je veux voir des photos de ",
        "montre des images de ", "montre des photos de ",
        "trouve des images de ", "trouve des photos de ",
        "trouve une photo de ", "trouve une image de ",
        "recherche des images de ", "recherche des photos de ",
        "affiche-moi des images de ", "affiche-moi des photos de ",
    ]
    
    for pref in _images_prefixes:
        pref_cleaned = nettoyer_accent(pref)
        if t.startswith(pref_cleaned):
            query = texte[len(pref):].strip().rstrip(".")
            if len(query) > 1:
                print(f"[IMAGE RESOLVER] Demande de recherche d'images pour : {query}")
                
                async def _pousser_images(q=query):
                    # (builtins._lire_config n'existe pas : le moteur réglé dans les
                    #  Paramètres était ignoré, toujours serpapi)
                    from core.micro import _lire_config
                    cfg = _lire_config()
                    engine = cfg.get("image_search_engine", "serpapi")
                    
                    urls = images_par_moteur(q, nb_images=6, engine=engine)
                    if urls:
                        msg_json = json.dumps({
                            "type": "show_images",
                            "query": q,
                            "images": urls
                        })
                        if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
                            try:
                                await asyncio.gather(*[ws.send(msg_json) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)
                            except Exception as e:
                                print(f"[ERREUR WS] Broadcast images: {e}")
                
                # Lancement asynchrone en tâche de fond pour ne pas bloquer la synthèse vocale
                if hasattr(builtins, "demarrer_tache_fond"):
                    builtins.demarrer_tache_fond(_pousser_images())
                elif hasattr(builtins, "WS_LOOP") and builtins.WS_LOOP:
                    asyncio.run_coroutine_threadsafe(_pousser_images(), builtins.WS_LOOP)
                else:
                    asyncio.create_task(_pousser_images())
                    
                return f"Je recherche des images de {query} et je les affiche sur votre interface{nom_virgule()}."
                
    return None

# Enregistrement dans builtins pour appel dynamique
builtins.resoudre_images_locales = resoudre_images_locales
