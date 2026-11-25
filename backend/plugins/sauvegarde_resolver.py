"""sauvegarde_resolver.py — « fais une sauvegarde », « restaure la sauvegarde d'hier » (core/sauvegarde.py). La restauration passe par une confirmation voix et HUD."""
import builtins
import datetime
import re
import unicodedata

from core import sauvegarde
from core.interlocuteur import nom_virgule

_MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def jour_demande(t: str, aujourdhui: datetime.date):
    """(jour précis, « avant » ce jour) lus dans la phrase : « d'hier » → avant aujourd'hui ; « du 12 novembre » → ce jour ; sinon la plus récente."""
    if re.search(r"\b(?:d'hier|de hier|de la veille|hier)\b", t):
        return None, aujourdhui
    m = re.search(r"\bdu\s+(\d{1,2})(?:er)?\s+(" + "|".join(_MOIS) + r")\b", t)
    if m:
        try:
            return datetime.date(aujourdhui.year, _MOIS.index(m.group(2)) + 1, int(m.group(1))), None
        except ValueError:
            return None, None
    return None, None


async def resoudre_sauvegarde(cmd: str):
    t = _norm(cmd.strip())
    if re.search(r"\b(?:fais|lance|cree|prepare)\b.*\bsauvegarde\b", t) and not re.search(r"\b(?:restaure|restaurer|recupere|remets?)\b", t):
        dossier = sauvegarde.sauvegarder(forcer=True)
        return f"Sauvegarde faite{nom_virgule()}." if dossier else f"Rien à sauvegarder pour l'instant{nom_virgule()}."
    if re.search(r"\b(?:quelles?|liste)\b.*\bsauvegardes?\b", t):
        jours = sauvegarde.lister()
        if not jours:
            return f"Aucune sauvegarde pour l'instant{nom_virgule()}."
        return f"{len(jours)} sauvegarde{'s' if len(jours) > 1 else ''}, la dernière date du {jours[0].day} {_MOIS[jours[0].month - 1]}."
    if not re.search(r"\b(?:restaure|restaurer|recupere|remets?|reviens)\b.*\bsauvegarde\b", t):
        return None
    jour, avant = jour_demande(t, datetime.date.today())
    choix = sauvegarde.choisir(jour, avant)
    if not choix:
        return f"Je n'ai pas de sauvegarde pour cette date{nom_virgule()}."
    from core.confirmation import demander_confirmation
    quand = f"du {choix.day} {_MOIS[choix.month - 1]}"
    if not await demander_confirmation(None, f"Restaurer la sauvegarde {quand} ? Mémoire, alarmes, routines et macros reviendront à cet état (l'état actuel est gardé à part)."):
        return f"D'accord{nom_virgule()}, je ne touche à rien."
    fichiers = sauvegarde.restaurer(choix)
    return f"Sauvegarde {quand} restaurée{nom_virgule()}." if fichiers else f"La sauvegarde {quand} est vide{nom_virgule()}."


builtins.resoudre_sauvegarde = resoudre_sauvegarde
