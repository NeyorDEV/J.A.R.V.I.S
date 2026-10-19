import os
import time
import chromadb
from chromadb.utils import embedding_functions

# Ajout manuel des répertoires DLL pour Windows (CUDA + cuDNN)
if os.name == 'nt':
    cuda_bin = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"
    cudnn_bin = r"C:\Program Files\NVIDIA\CUDNN\v9.23\bin\12.9\x64"
    if os.path.exists(cuda_bin):
        try: os.add_dll_directory(cuda_bin)
        except: pass
        os.environ["PATH"] = cuda_bin + os.pathsep + os.environ["PATH"]
    if os.path.exists(cudnn_bin):
        try: os.add_dll_directory(cudnn_bin)
        except: pass
        os.environ["PATH"] = cudnn_bin + os.pathsep + os.environ["PATH"]

# Chemin vers la DB vectorielle
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "chroma_db")

# Variable globale pour le client et la collection afin d'éviter de les recharger à chaque fois
_client = None
_collection = None
on_souvenir_added = []

# Monkey-patch de la fonction d'embedding par défaut de ChromaDB pour exclure TensorRT et éviter les warnings
def _patched_default_call(self, input):
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2
    import onnxruntime as ort
    try:
        ort.set_default_logger_severity(3) # 3 = Error
    except:
        pass
    # Utiliser uniquement CUDA et CPU pour éviter les avertissements et crashs TensorRT
    return ONNXMiniLM_L6_V2(preferred_providers=["CUDAExecutionProvider", "CPUExecutionProvider"])(input)

embedding_functions.DefaultEmbeddingFunction.__call__ = _patched_default_call

def _get_collection():
    """Initialise le client ChromaDB et retourne la collection d'historique."""
    global _client, _collection
    if _collection is None:
        try:
            if not os.path.exists(CHROMA_PATH):
                os.makedirs(CHROMA_PATH)
            
            _client = chromadb.PersistentClient(path=CHROMA_PATH)
            
            # Utilisation de la fonction d'embedding par défaut (qui utilise désormais notre patch)
            emb_fn = embedding_functions.DefaultEmbeddingFunction()
            
            _collection = _client.get_or_create_collection(
                name="jarvis_deep_memory",
                embedding_function=emb_fn,
                metadata={"hnsw:space": "cosine"} # Utilisation de la similarité cosinus
            )
            print(f"[VECTOR DB] Mémoire vectorielle chargée : {_collection.count()} souvenirs.")
        except Exception as e:
            print(f"[VECTOR DB] Erreur initialisation ChromaDB : {e}")
            return None
    return _collection

def ajouter_souvenir(user_text, model_text):
    """Ajoute un échange à la base de données vectorielle pour un rappel futur."""
    # Les échanges d'une voix invitée ne sont pas mémorisés
    import core.shared as _shared
    if getattr(_shared, "ACTIVE_SPEAKER", "guest") == "guest":
        return
    # Exclure les échanges qui sont des commandes système, des actions ou du contenu dynamique transitoire
    u_lower = user_text.lower()
    m_lower = model_text.lower()
    
    # Détecter le JSON / Actions
    if "{" in model_text or "action" in m_lower:
        return
        
    # Liste de mots-clés dynamiques transitoires
    mots_exclus = [
        "alarme", "alarm", "minuteur", "réveil", "reveil",
        "spotify", "deezer", "chanson", "musique", "volume", "playlist", "pause", "play", "stop",
        "ordinateur", "application", "éteindre", "redémarrer", "fermer", "ouvrir", "luminosité", "luminosite",
        "navigateur", "web", "recherche", "google", "site", "browser",
        "liste", "mémoire locale", "memo",
        "heure", "date", "météo", "meteo", "température", "temperature",
        "agenda", "calendrier", "calendar",
        "oublie", "oublier", "supprime", "supprimer", "efface", "effacer", "vide", "vider", "annule", "annuler", "retire", "retirer",
        "retiens", "retienne", "enregistre", "enregistrer", "mémorise", "memorise", "mémoriser", "memoriser", "note", "noter", "rappelle", "rappeler"
    ]
    
    if any(w in u_lower for w in mots_exclus) or any(w in m_lower for w in mots_exclus):
        return

    coll = _get_collection()
    if coll is None: return

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    full_content = f"Date: {timestamp}\nUser: {user_text}\nAssistant: {model_text}"
    
    # ID réellement unique. Avant, la résolution était à la seconde : deux
    # échanges dans la même seconde produisaient le même identifiant, ChromaDB
    # rejetait le doublon et le second souvenir était perdu (exception avalée).
    import uuid as _uuid
    entry_id = f"msg_{int(time.time())}_{_uuid.uuid4().hex[:8]}"
    
    try:
        coll.add(
            documents=[full_content],
            metadatas=[{"timestamp": timestamp, "type": "conversation"}],
            ids=[entry_id]
        )
        # Déclencher les callbacks enregistrés
        for cb in on_souvenir_added:
            try:
                cb(user_text, model_text)
            except Exception as cb_err:
                print(f"[VECTOR DB] Erreur callback souvenir_added: {cb_err}")
    except Exception as e:
        print(f"[VECTOR DB] Erreur ajout souvenir : {e}")

def rechercher_souvenirs(query_text, n_results=4, seuil=0.55):
    """Recherche des souvenirs pertinents basés sur la requête.

    seuil: distance cosinus max acceptable (0=identique, 1=sans rapport).
    Les souvenirs trop éloignés sont écartés plutôt que forcés dans le prompt.
    """
    coll = _get_collection()
    if coll is None or coll.count() == 0:
        return ""

    try:
        actual_n = min(n_results, coll.count())
        results = coll.query(
            query_texts=[query_text],
            n_results=actual_n,
            include=["documents", "distances"]
        )

        if not results or not results['documents'] or not results['documents'][0]:
            return ""

        docs      = results['documents'][0]
        distances = results.get('distances', [[]])[0]

        # Ne garder que les souvenirs réellement proches de la requête
        pertinents = [
            doc for doc, dist in zip(docs, distances)
            if dist <= seuil
        ]

        if not pertinents:
            print(f"[VECTOR DB] Aucun souvenir pertinent (meilleure distance: {distances[0]:.3f} > seuil {seuil})")
            return ""

        print(f"[VECTOR DB] {len(pertinents)}/{len(docs)} souvenir(s) pertinent(s) injecté(s) (distances: {[round(d,3) for d in distances[:len(pertinents)]]})")
        formatted = "\n---\n".join(pertinents)
        return f"\n[SOUVENIRS DU PASSÉ RETROUVÉS]\n{formatted}\n"

    except Exception as e:
        print(f"[VECTOR DB] Erreur recherche souvenirs : {e}")
        return ""

def rechercher_souvenir_semantique(query_text, threshold=0.4):
    """Recherche un souvenir extrêmement proche sémantiquement.
    Retourne la réponse de l'assistant si le score de distance est inférieur ou égal au threshold."""
    # Éviter les requêtes dynamiques ou d'apprentissage qui ne doivent pas utiliser de cache statique
    q_lower = query_text.lower().strip()
    mots_exclus = [
        "alarme", "alarm", "minuteur", "réveil", "reveil",
        "spotify", "deezer", "chanson", "musique", "volume", "playlist", "pause", "play", "stop",
        "ordinateur", "application", "éteindre", "redémarrer", "fermer", "ouvrir", "luminosité", "luminosite",
        "navigateur", "web", "recherche", "google", "site", "browser",
        "liste", "mémoire locale", "memo",
        "heure", "date", "météo", "meteo", "température", "temperature",
        "agenda", "calendrier", "calendar",
        "oublie", "oublier", "supprime", "supprimer", "efface", "effacer", "vide", "vider", "annule", "annuler", "retire", "retirer",
        "retiens", "retienne", "enregistre", "enregistrer", "mémorise", "memorise", "mémoriser", "memoriser", "note", "noter", "rappelle", "rappeler",
        # Sujets dont la réponse change dans le temps : un ancien échange donnerait
        # une réponse périmée (score, actualité, cours de bourse…)
        "score", "résultat", "resultat", "match", "gagné", "gagne", "actualité", "actualite", "actu",
        "news", "prix", "coûte", "coute", "cours", "bourse", "bitcoin", "aujourd'hui", "demain",
        "hier", "maintenant", "ce soir", "ce matin", "cette semaine", "en ce moment", "dernier",
        "dernière", "récent", "recent", "combien", "quel jour", "élection", "election",
        # Demandes créatives : on en attend une nouvelle à chaque fois (« raconte-moi une
        # histoire » redonnait mot pour mot l'histoire précédente)
        "raconte", "histoire", "blague", "poème", "poeme", "invente", "imagine", "idée", "idee",
        "propose", "suggère", "suggere", "devinette", "anecdote", "chante", "au hasard", "une autre", "encore"
    ]
    if any(w in q_lower for w in mots_exclus):
        return None

    coll = _get_collection()
    if coll is None or coll.count() == 0:
        return None

    try:
        results = coll.query(
            query_texts=[query_text],
            n_results=1
        )
        
        if not results or not results['documents'] or not results['documents'][0]:
            return None
            
        # Vérifier la distance
        if 'distances' in results and results['distances'] and results['distances'][0]:
            dist = results['distances'][0][0]
            if dist <= threshold:
                doc = results['documents'][0][0]
                # Le document est sous la forme:
                # "Date: YYYY-MM-DD HH:MM:SS\nUser: ...\nAssistant: ..."
                # On extrait la partie Assistant
                if "Assistant:" in doc:
                    parts = doc.split("Assistant:")
                    assistant_reply = parts[-1].strip()
                    
                    # S'assurer qu'on ne renvoie pas une action JSON
                    if "{" in assistant_reply or "action" in assistant_reply.lower():
                        print(f"[VECTOR DB] Hit sémantique local ignoré car il contient une action ou du JSON.")
                        return None
                        
                    print(f"[VECTOR DB] Hit sémantique local (dist={dist:.3f}) : {assistant_reply}")
                    return assistant_reply
    except Exception as e:
        print(f"[VECTOR DB] Erreur recherche sémantique : {e}")
    return None

def supprimer_souvenir_semantique(query_text, seuil=0.35):
    """Recherche et supprime les souvenirs dans ChromaDB qui sont sémantiquement trop proches de la requête.

    Seuil de distance cosinus resserré (0,5 → 0,35) : à 0,5, « oublie mon chat »
    pouvait effacer des souvenirs qui ne parlaient que vaguement d'animaux."""
    coll = _get_collection()
    if coll is None or coll.count() == 0:
        return False
    try:
        # Recherche des documents les plus proches
        results = coll.query(
            query_texts=[query_text],
            n_results=5,
            include=["distances"]
        )
        if not results or not results['ids'] or not results['ids'][0]:
            return False
        
        ids_to_delete = []
        if 'distances' in results and results['distances'] and results['distances'][0]:
            for entry_id, dist in zip(results['ids'][0], results['distances'][0]):
                # Si le souvenir est à moins de `seuil` (ex. 0.5 similarité élevée)
                if dist <= seuil:
                    ids_to_delete.append(entry_id)
        
        if ids_to_delete:
            coll.delete(ids=ids_to_delete)
            print(f"[VECTOR DB] Supprimé {len(ids_to_delete)} souvenir(s) sémantique(s) de la DB vectorielle.")
            return True
    except Exception as e:
        print(f"[VECTOR DB] Erreur lors de la suppression sémantique : {e}")
    return False

SEUIL_DECLENCHEMENT_CONSOLIDATION = 60  # nb min. de souvenirs bruts avant de consolider
GARDER_RECENTS_CONSOLIDATION      = 20  # toujours laisser les N plus récents intacts
MAX_LOT_CONSOLIDATION             = 40  # nb max. de souvenirs bruts envoyés au LLM par passage

async def consolider_memoire_vectorielle_ia():
    """Résume par lots les plus anciens souvenirs bruts de ChromaDB via Gemini.

    Sans ça, chaque échange (hors mots-clés transitoires déjà filtrés par
    ajouter_souvenir) s'accumule indéfiniment en base : la recherche
    sémantique devient de plus en plus bruitée avec le temps et l'espace
    disque croît sans fin. On synthétise donc les plus anciens souvenirs
    « conversation » en quelques souvenirs « consolidated_summary » plus
    denses, et on supprime les originaux. Les souvenirs déjà consolidés ne
    sont jamais repris (filtre type="conversation"), pour éviter la perte
    d'information en cascade sur plusieurs passages.
    """
    import builtins
    import json as _json
    from google.genai import types
    from core.config import CHOSEN_MODEL

    coll = _get_collection()
    if coll is None:
        return False

    try:
        bruts = coll.get(where={"type": "conversation"}, include=["documents", "metadatas"])
    except Exception as e:
        print(f"[VECTOR DB] Erreur lecture souvenirs bruts pour consolidation : {e}")
        return False

    ids   = bruts.get("ids", [])
    docs  = bruts.get("documents", [])
    metas = bruts.get("metadatas", [])
    if len(ids) < SEUIL_DECLENCHEMENT_CONSOLIDATION:
        return False

    # Tri chronologique croissant (le timestamp "%Y-%m-%d %H:%M:%S" se trie lexicalement)
    entrees = sorted(
        zip(ids, docs, metas),
        key=lambda t: (t[2] or {}).get("timestamp", "")
    )

    a_consolider = entrees[:-GARDER_RECENTS_CONSOLIDATION] if len(entrees) > GARDER_RECENTS_CONSOLIDATION else []
    if not a_consolider:
        return False
    a_consolider = a_consolider[:MAX_LOT_CONSOLIDATION]

    lot_ids  = [e[0] for e in a_consolider]
    lot_text = "\n---\n".join(e[1] for e in a_consolider)

    prompt = f"""Voici un lot d'anciens échanges de conversation entre Neyor (ou un autre membre du foyer) et son assistant JARVIS, stockés en mémoire vectorielle.

Résume-les en un nombre RÉDUIT de souvenirs autonomes et denses (un souvenir par fait, préférence, décision ou évènement marquant durable). Ignore le bavardage transitoire et les détails sans valeur de rappel futur. Chaque souvenir doit rester compréhensible seul, avec assez de détails concrets (noms, dates, choix) pour qu'une recherche sémantique future le retrouve.

ÉCHANGES :
{lot_text}

Renvoie OBLIGATOIREMENT un objet JSON de ce format :
{{"souvenirs": ["souvenir autonome 1", "souvenir autonome 2", ...]}}
Si rien de durable ne ressort du lot, renvoie {{"souvenirs": []}}.
"""

    print(f"[VECTOR DB] Consolidation de {len(lot_ids)} souvenir(s) brut(s) via Gemini...")
    try:
        client = getattr(builtins, "client", None)
        if not client:
            import google.genai as genai
            from core.config import GEMINI_API_KEY
            client = genai.Client(api_key=GEMINI_API_KEY)

        response = await client.aio.models.generate_content(
            model=CHOSEN_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        data = {}
        if response and response.text:
            try:
                data = _json.loads(response.text)
            except Exception as je:
                print(f"[VECTOR DB] Erreur décodage JSON de consolidation : {je}")
                return False

        resumes = data.get("souvenirs", []) if isinstance(data, dict) else []
        resumes = [r.strip() for r in resumes if isinstance(r, str) and r.strip()]

        # Les originaux sont supprimés même si aucun résumé n'en ressort (bavardage
        # jugé sans valeur) : sinon un lot vide serait retenté indéfiniment sans jamais
        # réduire la base ni changer d'issue.
        coll.delete(ids=lot_ids)

        if resumes:
            import uuid as _uuid
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            new_ids  = [f"summary_{int(time.time())}_{_uuid.uuid4().hex[:8]}_{i}" for i in range(len(resumes))]
            new_meta = [{"timestamp": timestamp, "type": "consolidated_summary", "source_count": len(lot_ids)} for _ in resumes]
            coll.add(documents=resumes, metadatas=new_meta, ids=new_ids)

        print(f"[VECTOR DB] Consolidation terminée : {len(lot_ids)} souvenir(s) brut(s) -> {len(resumes)} résumé(s).")
        return True

    except Exception as e:
        print(f"[VECTOR DB] Erreur lors de la consolidation vectorielle : {e}")
        return False

def lister_souvenirs_complets():
    """Retourne la liste de tous les souvenirs complets avec ids et documents."""
    coll = _get_collection()
    if coll is None: return []
    try:
        results = coll.get()
        souvenirs = []
        ids = results.get('ids', [])
        docs = results.get('documents', [])
        metas = results.get('metadatas', [])
        for i in range(len(ids)):
            souvenirs.append({
                "id": ids[i],
                "document": docs[i],
                "metadata": metas[i] if i < len(metas) else {}
            })
        return souvenirs
    except Exception as e:
        print(f"[VECTOR DB] Erreur lister_souvenirs_complets: {e}")
        return []

if __name__ == "__main__":
    # Petit test si lancé seul
    ajouter_souvenir("J'adore le café Blue Mountain de Jamaïque.", "C'est noté, Neyor. C'est un excellent choix très raffiné.")
    print("Test de recherche : 'café'")
    print(rechercher_souvenirs("Quel type de café j'aime ?"))
