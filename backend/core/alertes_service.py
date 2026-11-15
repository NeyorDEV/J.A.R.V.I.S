"""
alertes_service.py — Cartes d'erreur du HUD quand un service tombe.

Sans cela, un moteur LLM en pause ou un Home Assistant injoignable ne se voyaient que dans
le journal : l'utilisateur n'entendait qu'un silence ou une réponse de secours. Une carte
« alert » est envoyée au HUD (message ctx_card, déjà géré par le front).

Chaque panne a une clé ; une même clé ne produit pas deux cartes de suite avant `delai_min`
secondes (une rafale d'erreurs ne doit pas empiler des cartes). Utilisable depuis n'importe
quel thread (core.web_bridge.diffuser_web_sync).
"""

import time

_derniere_carte = {}   # {clé: horodatage monotone de la dernière carte envoyée}


def signaler_panne(cle: str, titre: str, texte: str, delai_min: float = 120.0,
                   duree_ms: int = 12000) -> bool:
    """Envoie une carte d'erreur au HUD. Renvoie True si elle est partie, False si elle a
    été retenue (même panne signalée il y a moins de `delai_min` s) ou sans HUD connecté."""
    maintenant = time.monotonic()
    precedente = _derniere_carte.get(cle)
    if precedente is not None and maintenant - precedente < delai_min:
        return False
    try:
        from core import web_bridge
        web_bridge.diffuser_web_sync({
            "action": "ctx_card",
            "title": titre,
            "text": texte,
            "type": "alert",
            "priorite": "alarme",   # ambre ; « critique » (rose, pulsant) serait trop fort pour une pause
            "icon": "",
            "duration": duree_ms,
        })
    except Exception as e:
        print(f"[ALERTE] Carte « {titre} » non envoyée : {e}")
        return False
    _derniere_carte[cle] = maintenant
    return True


def signaler_moteur_en_pause(api_name: str, secondes: int) -> bool:
    """Carte « moteur en pause » pour un fournisseur LLM (clé de l'API, ex. « gemini »)."""
    if api_name.startswith("gemini_"):
        return False   # un seul modèle Gemini : les autres prennent le relais, rien à dire
    etiquettes = {"gemini": "Gemini", "groq": "Groq", "claude": "Claude", "grok": "Grok",
                  "mistral": "Mistral", "ollama": "Ollama"}
    nom = etiquettes.get(api_name, api_name.capitalize())
    return signaler_panne(
        f"quota_{api_name}",
        f"{nom} en pause",
        f"Limite d'utilisation atteinte. Reprise dans {secondes} s ; "
        "JARVIS répond avec un autre moteur en attendant.",
        delai_min=max(60.0, float(secondes)),
    )


def signaler_home_assistant_injoignable() -> bool:
    """Carte « Home Assistant injoignable »."""
    return signaler_panne(
        "home_assistant",
        "Home Assistant injoignable",
        "La commande domotique n'a pas pu être envoyée. Vérifiez que le serveur est allumé "
        "et que l'adresse est correcte, puis réessayez.",
    )
