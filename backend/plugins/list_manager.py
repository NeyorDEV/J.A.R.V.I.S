import os
import json
import builtins
import asyncio

_LISTES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "jarvis_listes.json")  # backend/plugins/ -> racine projet

def _charger_listes():
    if os.path.exists(_LISTES_PATH):
        try:
            with open(_LISTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {"courses": [], "notes": [], "todo": []}

def _sauvegarder_listes(data):
    try:
        # data/ n'existe pas encore sur une installation neuve (dossier non versionné)
        os.makedirs(os.path.dirname(_LISTES_PATH), exist_ok=True)
        with open(_LISTES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except: pass

async def _notifier_web():
    """Notifie le frontend d'ouvrir le panneau courses et lui envoie la liste à jour."""
    if hasattr(builtins, "CONNECTED_CLIENTS") and builtins.CONNECTED_CLIENTS:
        listes = _charger_listes()
        msg_open = json.dumps({"type": "shopping_open"})
        msg_list = json.dumps({"type": "shopping_list", "items": listes.get("courses", [])})
        await asyncio.gather(*[ws.send(msg_open) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)
        await asyncio.gather(*[ws.send(msg_list) for ws in builtins.CONNECTED_CLIENTS], return_exceptions=True)

async def resoudre_listes_locales(texte):
    """Gère les listes de courses, notes et tâches localement."""
    # Nettoyage des guillemets parfois envoyés par l'interface clavier
    t = texte.strip().strip('"').strip("'").lower().strip()
    if "google" in t or "tasks" in t:
        return None
    data = _charger_listes()
    
    # 1. AJOUT
    if "ajoute" in t or "ajouter" in t or "mets" in t or "rajoute" in t or "rajouter" in t:
        cible = None
        if "course" in t: cible = "courses"
        elif "note" in t: cible = "notes"
        # On accepte les deux orthographes : selon le chemin d'entrée, le texte
        # peut arriver dé-accentué (« tache ») et ne matchait alors jamais.
        elif "tâche" in t or "tache" in t or "todo" in t: cible = "todo"
        
        if cible:
            # Nettoyage et extraction de l'article de façon robuste
            item = t
            for pattern in ["ajoute", "ajouter", "rajoute", "rajouter", "mets", "met"]:
                if item.startswith(pattern):
                    item = item[len(pattern):].strip()
            
            # Nettoyage des suffixes de listes
            for pattern in [
                "sur ma liste de courses", "à ma liste de courses", "a ma liste de courses", "dans ma liste de courses", "ma liste de courses", "la liste de courses",
                "sur ma liste de notes", "à ma liste de notes", "a ma liste de notes", "dans ma liste de notes", "ma liste de notes", "la liste de notes",
                "sur ma liste de tâches", "à ma liste de tâches", "a ma liste de taches", "sur ma liste de taches", "dans ma liste de tâches", "dans ma liste de taches",
                "ma liste de tâches", "ma liste de taches", "la liste de tâches", "la liste de taches", "todo", "ma to-do", "tâches", "tâche", "taches", "tache"
            ]:
                item = item.replace(pattern, "")
            
            # Nettoyage des liaisons
            item = item.strip().strip('"').strip("'").strip()
            for prep in ["de la ", "du ", "des ", "de ", "d'"]:
                if item.lower().startswith(prep):
                    item = item[len(prep):].strip()
            
            if item:
                data[cible].append(item.capitalize())
                _sauvegarder_listes(data)
                if cible == "courses":
                    await _notifier_web()
                return f"C'est fait, j'ai ajouté {item} à votre liste de {cible}, Monsieur."

    # 2. LECTURE
    is_course = "course" in t or t in ["courses", "mes courses"]
    is_note = "note" in t
    is_read = any(k in t for k in ["qu'est-ce qu'il y a", "affiche", "montre", "lire", "ouvre", "y'a quoi", "y a quoi", "qu'est-ce que j'ai", "quoi dans", "contenu", "liste"])
    
    if is_course and (is_read or t in ["courses", "mes courses"]):
        await _notifier_web()
        items = data.get("courses", [])
        if not items: return "Votre liste de courses est vide, Monsieur."
        items_propres = [i.replace("[x] ", "✓ ") if i.startswith("[x] ") else f"• {i}" for i in items]
        return f"Voici votre liste de courses : " + ", ".join(items_propres)
    elif is_note and is_read:
        items = data.get("notes", [])
        if not items: return "Vous n'avez aucune note enregistrée, Monsieur."
        return f"Voici vos notes : {', '.join(items)}."

    # 3. VIDAGE
    if "vide" in t or "supprime" in t or "efface" in t:
        if "course" in t:
            data["courses"] = []
            _sauvegarder_listes(data)
            await _notifier_web()
            return "La liste de courses a été vidée, Monsieur."

    return None

# Injection builtins
builtins.resoudre_listes_locales = resoudre_listes_locales
