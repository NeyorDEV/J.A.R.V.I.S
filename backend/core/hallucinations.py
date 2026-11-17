"""Phrases que Whisper invente sur du silence ou du bruit de fond (sous-titres, « merci d'avoir regardé », « abonnez-vous »…).

Une telle « phrase » ne doit jamais être traitée comme une demande. Trois familles, toutes comparées sans accents ni ponctuation :
  - phrases ENTIÈRES (« merci », « merci à tous », « bonjour ») : écartées seulement si elles sont toute la transcription ;
  - marqueurs propres aux hallucinations (« amara.org », « merci d'avoir regardé ») : écartés où qu'ils apparaissent, en mots entiers ;
  - débuts génériques (« sous-titres », « abonnez-vous », « à la prochaine vidéo ») : écartés seulement EN DÉBUT de phrase, car une vraie demande peut les contenir
    (« active les sous-titres », « passe à la prochaine vidéo »).
Pur : aucun import du reste de JARVIS (testé dans tests/test_hallucinations.py).
"""
import re
import unicodedata


def _norm(texte) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9.]+", " ", t)).strip(" .")


EXACTES = frozenset(_norm(x) for x in (
    "merci", "merci beaucoup", "merci à tous", "je vous remercie", "merci de votre attention", "bonjour", "you", "thank you", "thanks for watching", "subtitles", "sous-titres", "sous-titrage", "sous-titres par",
    "sous-titres par amara.org", "subtitles by amara.org", "société radio-canada", "radio-canada",
))
MARQUEURS = tuple(_norm(x) for x in (
    "amara.org", "sous-titres réalisés par", "sous-titrage st", "sous-titres st", "société radio-canada", "merci d'avoir regardé", "merci d'avoir écouté", "n'oubliez pas de vous abonner", "pensez à vous abonner",
    "abonnez-vous à la chaîne", "à la prochaine pour une nouvelle vidéo", "à bientôt pour une nouvelle vidéo", "thanks for watching",
))
DEBUTS = tuple(_norm(x) for x in ("sous-titres", "sous-titrage", "abonnez-vous", "à la prochaine vidéo"))

_MARQUEURS = re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % "|".join(re.escape(m) for m in MARQUEURS))
_DEBUTS = re.compile(r"^(?:%s)(?![a-z0-9])" % "|".join(re.escape(d) for d in DEBUTS))


def est_hallucination(texte) -> bool:
    """Vrai si la transcription ressemble à une hallucination connue de Whisper."""
    n = _norm(texte)
    return bool(n and (n in EXACTES or _MARQUEURS.search(n) or _DEBUTS.match(n)))
