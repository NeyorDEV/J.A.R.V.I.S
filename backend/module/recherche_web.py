"""Recherche web via SerpAPI : résultats bruts (pour le navigateur agent) et résumé parlé (pour JARVIS)."""

import os

import requests

_URL = "https://serpapi.com/search.json"


def _cle():
    cle = os.getenv("SERPAPI_API_KEY") or ""
    return "" if (not cle.strip() or "VOTRE" in cle.upper()) else cle.strip()


def serpapi_donnees_brutes(requete):
    """Interroge SerpAPI (Google, français) et renvoie le JSON, ou None si la clé est absente,
    désactivée dans les Paramètres, ou si la requête échoue."""
    from core.ai_clients import api_activee
    cle = _cle()
    if not cle or not api_activee("serpapi"):
        return None
    try:
        rep = requests.get(_URL, params={"engine": "google", "q": requete, "api_key": cle, "hl": "fr", "gl": "fr"}, timeout=10)
        return rep.json()
    except Exception as e:
        print(f"[WEB] SerpAPI indisponible : {e}")
        return None


def resume_recherche_web(requete):
    """Résumé en texte des trois premiers résultats (actualités d'abord, sinon résultats classiques)."""
    data = serpapi_donnees_brutes(requete)
    if not data:
        return "La recherche sur internet a échoué."
    try:
        actus = data.get("news_results") or []
        if actus:
            lignes = [f"- {a.get('title', '')} (via {a.get('source', 'source inconnue')})" for a in actus[:3]]
            return f"Dernières actualités sur {requete} :\n" + "\n".join(lignes) + "\n"
        resultats = data.get("organic_results") or []
        if resultats:
            lignes = [f"- {r.get('title', '')} : {r.get('snippet', '')}" for r in resultats[:3]]
            return f"Résultats du web pour {requete} :\n" + "\n".join(lignes) + "\n"
        return f"Rien trouvé de pertinent sur le web pour : {requete}."
    except Exception as e:
        print(f"[WEB] Résultats SerpAPI illisibles : {e}")
        return "Une erreur est survenue lors de l'analyse des résultats de recherche."
