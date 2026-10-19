import builtins
import unicodedata

from core.interlocuteur import nom_virgule

# Clés sans accents (la phrase est comparée sans accents : « états-unis », « algérie »,
# « égypte » n'étaient jamais reconnus) ; valeur : (complément du nom, capitale)
_CAPITALES = {
    "france": ("de la France", "Paris"), "espagne": ("de l'Espagne", "Madrid"),
    "italie": ("de l'Italie", "Rome"), "allemagne": ("de l'Allemagne", "Berlin"),
    "royaume-uni": ("du Royaume-Uni", "Londres"), "portugal": ("du Portugal", "Lisbonne"),
    "belgique": ("de la Belgique", "Bruxelles"), "suisse": ("de la Suisse", "Berne"),
    "etats-unis": ("des États-Unis", "Washington"), "canada": ("du Canada", "Ottawa"),
    "japon": ("du Japon", "Tokyo"), "chine": ("de la Chine", "Pékin"),
    "russie": ("de la Russie", "Moscou"), "bresil": ("du Brésil", "Brasilia"),
    "maroc": ("du Maroc", "Rabat"), "algerie": ("de l'Algérie", "Alger"),
    "tunisie": ("de la Tunisie", "Tunis"), "egypte": ("de l'Égypte", "Le Caire"),
}

_MONNAIES = {
    "france": ("de la France", "l'euro"), "etats-unis": ("des États-Unis", "le dollar américain"),
    "royaume-uni": ("du Royaume-Uni", "la livre sterling"), "japon": ("du Japon", "le yen"),
    "suisse": ("de la Suisse", "le franc suisse"), "canada": ("du Canada", "le dollar canadien"),
}


def _sans_accent(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


async def traiter_extras_locaux(texte):
    """Culture générale locale (capitales, monnaies).

    Salutations, « comment tu vas », blagues, citations et questions d'identité ne
    sont plus traitées ici avec des phrases toutes faites : elles passent par l'IA,
    qui répond avec la personnalité de JARVIS (voir core/prompt_builder.py).
    """
    t = _sans_accent(texte.lower().strip())

    # CULTURE GÉNÉRALE (Capitales / Monnaies)
    if "capitale d" in t:
        for pays, (complement, cap) in _CAPITALES.items():
            if pays in t: return f"La capitale {complement} est {cap}{nom_virgule()}."
    if "monnaie d" in t or "devise d" in t:
        for pays, (complement, mon) in _MONNAIES.items():
            if pays in t: return f"La monnaie {complement} est {mon}{nom_virgule()}."

    return None

# Injection builtins
builtins.traiter_extras_locaux = traiter_extras_locaux
