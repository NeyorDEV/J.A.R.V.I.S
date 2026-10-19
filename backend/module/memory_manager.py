import os
import json
import shutil
import threading
import time
from google.genai import types

# MEMOIRE PERSISTANTE
# ==========================================
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # racine projet (backend/module/ -> N:\JARVIS)
MEMOIRE_FILE = os.path.join(_ROOT_DIR, "data", "jarvis_memoire.json")

# Verrou : la mémoire est écrite depuis plusieurs threads (boucle vocale,
# handler WebSocket, consolidation en arrière-plan). Sans lui, deux
# lecture-modification-écriture concurrentes se écrasent l'une l'autre.
_VERROU_MEMOIRE = threading.RLock()


def _ecrire_json_atomique(chemin, donnees):
    """Écrit un JSON sans jamais laisser le fichier à moitié écrit.

    On écrit dans un fichier temporaire voisin puis on le renomme : os.replace
    est atomique. Avant, un plantage (ou une coupure) au milieu du open("w")
    tronquait le fichier, et au démarrage suivant le JSON illisible était
    silencieusement remplacé par un dictionnaire vide — toute la mémoire perdue.
    """
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    temporaire = chemin + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporaire, chemin)


def _sauvegarder_fichier_corrompu(chemin, erreur):
    """Met de côté un fichier illisible au lieu de l'écraser en silence."""
    try:
        secours = f"{chemin}.corrompu-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(chemin, secours)
        print(f"[MEMOIRE] ⚠ Fichier illisible ({erreur}). Copie de sécurité : {secours}")
    except Exception as e:
        print(f"[MEMOIRE] ⚠ Fichier illisible ({erreur}), sauvegarde impossible : {e}")


def relire_memoire():
    with _VERROU_MEMOIRE:
        if os.path.exists(MEMOIRE_FILE):
            try:
                with open(MEMOIRE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                # On conserve une copie : sans elle, la première écriture qui
                # suivait remplaçait définitivement le contenu par « {} ».
                _sauvegarder_fichier_corrompu(MEMOIRE_FILE, e)
                return {}
        return {}

def ecrire_memoire(memoire):
    with _VERROU_MEMOIRE:
        try:
            _ecrire_json_atomique(MEMOIRE_FILE, memoire)
        except Exception as e:
            print(f"Erreur sauvegarde memoire : {e}")

def noter_en_memoire(cle, valeur):
    # Le verrou couvre lecture ET écriture : sinon deux ajouts simultanés
    # repartaient de la même copie et le second écrasait le premier.
    with _VERROU_MEMOIRE:
        memoire      = relire_memoire()
        memoire[cle] = {"valeur": valeur, "timestamp": time.strftime("%d/%m/%Y %H:%M")}
        ecrire_memoire(memoire)

def oublier_memoire(cle):
    with _VERROU_MEMOIRE:
        memoire = relire_memoire()
        if cle in memoire:
            del memoire[cle]
            ecrire_memoire(memoire)
            return True
        return False

def composer_contexte_memoire():
    memoire = relire_memoire()
    if not memoire:
        return ""
    lignes = ["MEMOIRE PERSISTANTE :"]
    for cle, data in memoire.items():
        lignes.append(f"  - {cle} : {data['valeur']} (note le {data['timestamp']})")
    return "\n".join(lignes)

# ==========================================
# HISTORIQUE CONVERSATIONS PERSISTANT
# ==========================================
HISTORIQUE_CONV_FILE = os.path.join(_ROOT_DIR, "data", "jarvis_conversations.json")
MAX_ECHANGES_FICHIER = 200   # max échanges stockés sur disque
MAX_ECHANGES_CHARGE  = 30    # échanges rechargés au démarrage (contexte IA)

_NB_ECHANGES_CONSOLIDES = 0   # nombre d'échanges déjà vus par la dernière consolidation


def _archiver_echange(user_text: str, model_text: str):
    """Ajoute un échange user/model au fichier JSON persistant."""
    # Verrou + écriture atomique : deux requêtes qui se chevauchent partaient
    # sinon de la même liste et la seconde écrasait l'échange de la première.
    with _VERROU_MEMOIRE:
        try:
            echanges = []
            if os.path.exists(HISTORIQUE_CONV_FILE):
                try:
                    with open(HISTORIQUE_CONV_FILE, "r", encoding="utf-8") as f:
                        echanges = json.load(f)
                except Exception as e_lect:
                    _sauvegarder_fichier_corrompu(HISTORIQUE_CONV_FILE, e_lect)
                    echanges = []
            if not isinstance(echanges, list):
                echanges = []
            import core.shared as _shared
            echanges.append({
                "date":  time.strftime("%d/%m/%Y"),
                "heure": time.strftime("%H:%M"),
                "user":  user_text[:2000],
                "model": model_text[:3000],
                "locuteur": getattr(_shared, "ACTIVE_SPEAKER", "guest"),
            })
            if len(echanges) > MAX_ECHANGES_FICHIER:
                echanges = echanges[-MAX_ECHANGES_FICHIER:]
            _ecrire_json_atomique(HISTORIQUE_CONV_FILE, echanges)
        except Exception as e:
            print(f"[CONV] Erreur sauvegarde historique: {e}")

def _relire_historique_recent():
    """Charge les derniers échanges et retourne une liste types.Content."""
    if not os.path.exists(HISTORIQUE_CONV_FILE):
        return []
    try:
        with open(HISTORIQUE_CONV_FILE, "r", encoding="utf-8") as f:
            echanges = json.load(f)
        recents = echanges[-MAX_ECHANGES_CHARGE:]
        hist = []
        for e in recents:
            date_str = f"[{e.get('date','?')} {e.get('heure','?')}] "
            hist.append(types.Content(role="user",  parts=[types.Part(text=date_str + e["user"])]))
            hist.append(types.Content(role="model", parts=[types.Part(text=e["model"])]))
        # print(f"[CONV] {len(recents)} echanges passes rechargees en memoire.")
        return hist
    except Exception as e:
        print(f"[CONV] Erreur chargement historique: {e}")
        return []

async def consolider_memoire_ia():
    """Analyse l'historique récent des conversations avec Gemini pour en extraire des faits marquants et mettre à jour la mémoire persistante."""
    import builtins
    from core.config import CHOSEN_MODEL
    
    # 1. Charger l'historique
    if not os.path.exists(HISTORIQUE_CONV_FILE):
        return False
    try:
        with open(HISTORIQUE_CONV_FILE, "r", encoding="utf-8") as f:
            echanges = json.load(f)
    except Exception:
        return False
        
    if not echanges:
        return False
        
    # Prendre les 30 derniers échanges pour la consolidation
    # Les propos d'une voix invitée ne deviennent pas des faits durables sur l'utilisateur
    echanges = [e for e in echanges if e.get("locuteur") != "guest"]
    # Relancée à chaque fin de session vocale, la consolidation renvoyait les 30 mêmes
    # échanges à Gemini à chaque fois : on attend au moins 5 nouveaux échanges.
    global _NB_ECHANGES_CONSOLIDES
    if len(echanges) - _NB_ECHANGES_CONSOLIDES < 5:
        return False
    _NB_ECHANGES_CONSOLIDES = len(echanges)

    recents = echanges[-30:]
    
    # Formater les échanges
    conv_text = ""
    for e in recents:
        conv_text += f"[{e.get('date')} {e.get('heure')}] User: {e.get('user')}\nAssistant: {e.get('model')}\n\n"
        
    # Charger la mémoire actuelle
    memoire_actuelle = relire_memoire()
    mem_formatted = json.dumps(memoire_actuelle, ensure_ascii=False, indent=2)
    
    prompt = f"""Analyse l'historique récent des conversations ci-dessous pour extraire les faits persistants importants ou les préférences de l'utilisateur (le plus souvent Neyor, ton créateur). 
Mets à jour ou ajoute les informations dans la mémoire. Ne conserve que les informations durables (goûts, outils préférés, prénoms de proches, choix technologiques) et ignore les détails transitoires (timers, météo d'aujourd'hui, requêtes système ponctuelles).

MÉMOIRE ACTUELLE :
{mem_formatted}

CONVERSATIONS RÉCENTES :
{conv_text}

Renvoie OBLIGATOIREMENT un objet JSON respectant ce format :
{{
  "updates": {{
    "clé": "valeur de l'information extraite avec son contexte"
  }},
  "deletes": ["clés devenues obsolètes ou fausses à supprimer"]
}}
Chaque valeur dans "updates" DOIT être une chaîne de texte simple — jamais un objet imbriqué,
même si la mémoire actuelle ci-dessus t'en montre sous cette forme (c'est un détail de stockage interne).
Ne renvoie rien d'autre que le JSON brut. Si aucune nouvelle information n'est détectée, renvoie un objet vide pour updates et deletes.
"""

    print("[MEMORY MANAGER] Déclenchement de la consolidation de mémoire via Gemini...")
    try:
        client = getattr(builtins, "client", None)
        if not client:
            import google.genai as genai
            from core.config import GEMINI_API_KEY
            client = genai.Client(api_key=GEMINI_API_KEY)
            
        response = await client.aio.models.generate_content(
            model=CHOSEN_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        data = {}
        if response and response.text:
            try:
                data = json.loads(response.text)
            except Exception as je:
                print(f"[MEMORY MANAGER] Erreur lors du décodage du JSON de la réponse : {je}")
        
        updates = data.get("updates", {}) if isinstance(data, dict) else {}
        deletes = data.get("deletes", []) if isinstance(data, dict) else []
        
        if updates or deletes:
            mem = relire_memoire()
            timestamp = time.strftime("%d/%m/%Y %H:%M")
            for k, v in updates.items():
                # Filet de sécurité : si le LLM échoue malgré la consigne et renvoie
                # l'entrée imbriquée telle quelle ({"valeur": ..., "timestamp": ...}),
                # on désimbrique plutôt que de stocker un objet dans "valeur" (ce qui
                # cassait ensuite l'affichage dans composer_contexte_memoire()).
                if isinstance(v, dict) and "valeur" in v:
                    v = v["valeur"]
                if not isinstance(v, str):
                    v = str(v)
                mem[k] = {"valeur": v, "timestamp": timestamp}
                print(f"[MEMORY MANAGER] Fait mémorisé : {k} -> {v}")
            from core.audit_log import consigner
            for k in [d for d in deletes if isinstance(d, str)][:3]:   # au plus 3 par passage
                if k in mem:
                    consigner("memoire_fait_supprime_par_ia", cle=k, valeur=str(mem[k])[:200])
                    del mem[k]
                    print(f"[MEMORY MANAGER] Fait supprimé : {k}")
            ecrire_memoire(mem)
            return True
            
    except Exception as e:
        print(f"[MEMORY MANAGER] Erreur lors de la consolidation de mémoire : {e}")
        
    return False

# Injection builtins
import builtins
builtins.consolider_memoire_ia = consolider_memoire_ia

