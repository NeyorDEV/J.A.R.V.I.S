"""habitudes_resolver.py — « quelles sont mes habitudes », « qu'as-tu remarqué », « transforme l'habitude 2 en routine » (module/habitudes.py)."""
import asyncio
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule
from module import habitudes

_derniere_liste: list = []   # numérotation de la dernière liste dite : « l'habitude 2 » désigne la deuxième de CETTE liste


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def _liste_demandee(t: str) -> bool:
    return bool(re.search(r"\b(?:mes|tes|les) habitudes\b|\bquelles habitudes\b|\bqu'as[- ]tu remarque\b|\bqu'est[- ]ce que tu as remarque\b|\bpropose[- ]moi des routines\b|\broutines? a creer\b", t))


async def resoudre_habitudes(cmd: str):
    global _derniere_liste
    t = _norm(cmd.strip())
    m = re.search(r"\b(?:transforme|convertis|fais|cree|programme)\b.*\bhabitude\s*(?:numero\s*|n°\s*)?(\d+|un|une|deux|trois|quatre|cinq)\b.*\broutine\b", t) \
        or re.search(r"\bhabitude\s*(?:numero\s*|n°\s*)?(\d+|un|une|deux|trois|quatre|cinq)\b.*\ben routine\b", t)
    if m:
        n = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5}.get(m.group(1)) or int(m.group(1))
        if not _derniere_liste:
            _derniere_liste = await asyncio.to_thread(habitudes.detecter)
        if not 1 <= n <= len(_derniere_liste):
            return f"Je n'ai pas d'habitude numéro {n}{nom_virgule()}. Demandez d'abord : quelles sont mes habitudes ?"
        cree = await asyncio.to_thread(habitudes.en_routine, _derniere_liste[n - 1])
        return f"Routine créée{nom_virgule()} : {cree}." if cree else f"Cette routine existe déjà, ou la liste est pleine{nom_virgule()}."
    if not _liste_demandee(t):
        return None
    _derniere_liste = await asyncio.to_thread(habitudes.detecter)
    if not _derniere_liste:
        return (f"Je n'ai pas encore assez de recul{nom_virgule()} : il me faut une même commande à peu près à la même heure sur trois jours. "
                "Je note vos commandes depuis aujourd'hui.")
    lignes = [f"{i}. {habitudes.decrire(h)}" for i, h in enumerate(_derniere_liste, 1)]
    return (f"J'ai remarqué {len(lignes)} habitude{'s' if len(lignes) > 1 else ''} : " + " ; ".join(lignes)
            + ". Dites « transforme l'habitude 1 en routine » pour que je la lance tout seul.")


builtins.resoudre_habitudes = resoudre_habitudes
