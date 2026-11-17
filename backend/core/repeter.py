"""« Répète » : mémoire de ce que JARVIS vient de dire, pour le redire à la demande.

Chaque commande de l'utilisateur ouvre un nouveau « tour » (`nouveau_tour()`, appelé au début du traitement d'une commande) ; `noter()` (appelé par speech.parler pour chaque phrase prononcée)
range la phrase dans le tour courant. `derniere_reponse()` rend les phrases du DERNIER TOUR QUI A PARLÉ avant celui en cours : une réponse diffusée en plusieurs phrases est redite en entier,
sans la mélanger à la réponse d'avant. Les annonces système (« Voix de Neyor détectée… », « Que puis-je pour vous ? ») ne comptent pas comme une réponse.
`est_demande_repetition()` reconnaît « répète », « redis », « j'ai pas compris »…
Pur (aucune dépendance au reste de JARVIS) : testé dans tests/test_repeter.py.
"""
import re
import time
import unicodedata
from collections import deque

MAX_CARACTERES = 500
_historique = deque(maxlen=60)   # (heure, texte, tour)
_a_ignorer = set()               # textes qu'on vient de répéter : ne pas les noter à nouveau (sinon « A B A B »)
_tour = 0


def _norm(texte) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


# Annonces et politesses de JARVIS qui ne sont pas « la réponse » : jamais redites.
_SANS_INTERET = re.compile(r"^(?:[a-z]+ )?(?:que puis je pour vous|je vous ecoute|a votre service|voix (?:de .+ detectee|inconnue detectee)|j ecoute pendant|dites oui pour confirmer|oui|d accord|tres bien)\b")


def nouveau_tour() -> None:
    """Une nouvelle commande de l'utilisateur commence : ce qui sera dit appartient à ce tour."""
    global _tour
    _tour += 1


def noter(texte, maintenant=None) -> None:
    texte = str(texte or "").strip()
    if not texte:
        return
    if texte in _a_ignorer:
        _a_ignorer.discard(texte)
        return
    if _SANS_INTERET.match(_norm(texte)):
        return
    _historique.append((time.time() if maintenant is None else maintenant, texte, _tour))


def oublier() -> None:
    global _tour
    _historique.clear()
    _a_ignorer.clear()
    _tour = 0


def derniere_reponse(maintenant=None, delai_max_s: float = 600.0) -> str:
    """Les phrases du dernier tour ayant parlé AVANT le tour en cours, jointes (500 caractères au plus, coupées à une phrase) ; vide si rien de récent."""
    now = time.time() if maintenant is None else maintenant
    if not _historique or now - _historique[-1][0] > delai_max_s:
        return ""
    tours = sorted({t for _h, _x, t in _historique})
    avant = [t for t in tours if t < _tour]
    choisi = avant[-1] if avant else tours[-1]
    phrases = [x for _h, x, t in _historique if t == choisi]
    sortie = ""
    for p in phrases:
        suite = (sortie + " " + p).strip()
        if len(suite) > MAX_CARACTERES and sortie:
            break
        sortie = suite
    return sortie[:MAX_CARACTERES]


def ignorer_prochaine(texte) -> None:
    """Le texte qu'on s'apprête à dire (une répétition) ne sera pas noté comme une nouvelle réponse."""
    _a_ignorer.add(str(texte or "").strip())


_DEMANDE = re.compile(
    r"^(?:jarvis )?(?:"
    r"(?:peux tu |tu peux |pourrais tu |tu pourrais )?(?:repete|repeter|redis|redire|repetes)(?: moi)?(?: ca| cela| ce que tu as dit| ce que tu viens de dire| ta derniere phrase| la derniere phrase| ta reponse| la reponse)?|"
    r"(?:j ai|je n ai) pas (?:bien )?(?:compris|entendu)(?: ce que tu as dit)?|"
    r"(?:j ai|je n ai) pas (?:bien )?(?:compris|entendu) (?:peux tu |tu peux )?(?:repeter|redire)|"
    r"(?:dis|redis) (?:le |ca )?encore(?: une fois)?"
    r")(?: s il te plait| stp| svp)?$"
)


def est_demande_repetition(texte) -> bool:
    return bool(_DEMANDE.match(_norm(texte)))
