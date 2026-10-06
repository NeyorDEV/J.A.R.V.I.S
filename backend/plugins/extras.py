import builtins

_CAPITALES = {
    "france": "Paris", "espagne": "Madrid", "italie": "Rome", "allemagne": "Berlin",
    "royaume-uni": "Londres", "portugal": "Lisbonne", "belgique": "Bruxelles",
    "suisse": "Berne", "etats-unis": "Washington", "canada": "Ottawa",
    "japon": "Tokyo", "chine": "Pekin", "russie": "Moscou", "bresil": "Brasilia",
    "maroc": "Rabat", "algerie": "Alger", "tunisie": "Tunis", "egypte": "Le Caire"
}

_MONNAIES = {
    "france": "Euro", "etats-unis": "Dollar americain", "royaume-uni": "Livre sterling",
    "japon": "Yen", "suisse": "Franc suisse", "canada": "Dollar canadien"
}

async def resoudre_extras_locaux(texte):
    """Culture générale locale (capitales, monnaies).

    Salutations, « comment tu vas », blagues, citations et questions d'identité ne
    sont plus traitées ici avec des phrases toutes faites : elles passent par l'IA,
    qui répond avec la personnalité de JARVIS (voir core/prompt_builder.py).
    """
    t = texte.lower().strip()

    # CULTURE GÉNÉRALE (Capitales / Monnaies)
    if "capitale de" in t or "capitale du" in t:
        for pays, cap in _CAPITALES.items():
            if pays in t: return f"La capitale de {pays.capitalize()} est {cap}, Monsieur."
    if "monnaie de" in t or "monnaie du" in t:
        for pays, mon in _MONNAIES.items():
            if pays in t: return f"La monnaie officielle en {pays.capitalize()} est le {mon}, Monsieur."

    return None

# Injection builtins
builtins.resoudre_extras_locaux = resoudre_extras_locaux
