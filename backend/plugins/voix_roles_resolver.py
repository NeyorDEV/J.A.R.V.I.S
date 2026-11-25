"""voix_roles_resolver.py — « voix de lecture féminine », « voix des alertes masculine », « teste les voix », « réinitialise les voix » (core/voix_roles.py)."""
import builtins
import re
import unicodedata

from core import voix_roles
from core.interlocuteur import nom_virgule

_NOMS = {"alerte": "des alertes", "quotidien": "du quotidien", "lecture": "de lecture"}


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def analyser(t: str):
    """('test', None) | ('reinit', None) | ('regler', (role, genre)) | None, pour la phrase normalisée."""
    if not re.search(r"\bvoix\b", t):
        return None
    if re.search(r"\b(?:teste|essaie|fais ecouter|montre)\b.*\b(?:les|des|tes)\s+(?:trois\s+)?voix\b", t):
        return "test", None
    if re.search(r"\b(?:reinitialise|remets?|reset)\b.*\bvoix\b", t):
        return "reinit", None
    role = "alerte" if re.search(r"\balertes?\b", t) else "lecture" if re.search(r"\blectures?\b", t) else "quotidien" if re.search(r"\b(?:quotidien\w*|habituelle|normale)\b", t) else None
    genre = "femme" if re.search(r"\b(?:femme|feminine|feminin)\b", t) else "homme" if re.search(r"\b(?:homme|masculine|masculin)\b", t) else None
    return ("regler", (role, genre)) if role and genre else None


async def resoudre_voix_roles(cmd: str):
    a = analyser(_norm(cmd.strip()))
    if a is None:
        return None
    action, valeur = a
    if action == "reinit":
        voix_roles.reinitialiser()
        return f"Les trois voix sont revenues à leurs réglages d'origine{nom_virgule()}."
    if action == "test":
        from core import speech
        speech.parler("Voici la voix du quotidien.", role="quotidien")
        speech.parler("Alerte, voici la voix des alertes.", role="alerte")
        speech.parler("Et voici la voix de lecture, plus posée, pour les textes longs.", role="lecture")
        return f"Voilà les trois voix{nom_virgule()}."
    role, genre = valeur
    if not voix_roles.definir(role, genre):
        return f"Je n'ai pas pu enregistrer ce réglage{nom_virgule()}."
    return f"La voix {_NOMS[role]} est maintenant {'féminine' if genre == 'femme' else 'masculine'}{nom_virgule()}."


builtins.resoudre_voix_roles = resoudre_voix_roles
