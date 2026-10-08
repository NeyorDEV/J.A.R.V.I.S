"""Resolver local des alarmes, minuteurs et rappels (sans IA).

Appelé tôt dans core/traitement.py : sans lui, « mets une alarme à 7 heures » ou
« mets un minuteur de 5 minutes » étaient happés par la recherche Deezer de
secours (toute phrase commençant par « mets » / « lance »), et l'IA, seule à
savoir créer une alarme, n'était jamais consultée.
"""

import re
import unicodedata

from core.interlocuteur import nom_virgule
from core.web_bridge import send_web_broadcast_sync
from module.alarm_manager import (
    ajouter_alarme, annuler_alarme, lister_alarmes, parser_duree, parser_heure,
)

_MOTS_MINUTEUR = ("minuteur", "minuterie", "timer", "compte a rebours", "chrono ")
_MOTS_ALARME = ("alarme", "reveil", "reveille-moi", "reveille moi", "reveilles-moi")
_MOTS_RAPPEL = ("rappelle-moi", "rappelle moi", "fais-moi penser", "fais moi penser")
_VERBES_ANNULER = ("annule", "supprime", "enleve", "retire", "desactive", "arrete",
                   "efface", "stoppe", "coupe", "oublie")
_VERBES_LISTER = ("quelles", "quels", "liste", "affiche", "montre", "combien",
                  "j'ai des", "ai-je", "est-ce que j'ai", "mes alarmes", "mes minuteurs")


def _normaliser(texte: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", texte.lower().strip())
                if unicodedata.category(c) != "Mn")
    return t.replace("’", "'")


def _duree_parlee(secondes: int) -> str:
    h, reste = divmod(secondes, 3600)
    m, s = divmod(reste, 60)
    morceaux = []
    if h:
        morceaux.append(f"{h} heure{'s' if h > 1 else ''}")
    if m:
        morceaux.append(f"{m} minute{'s' if m > 1 else ''}")
    if s:
        morceaux.append(f"{s} seconde{'s' if s > 1 else ''}")
    return " et ".join(morceaux) if morceaux else "0 seconde"


def _objet_rappel(texte: str) -> str:
    """« rappelle-moi d'appeler Paul dans 10 minutes » → « appeler Paul » (accents conservés :
    le libellé est prononcé quand le rappel sonne)."""
    t = texte.strip().replace("’", "'")
    m = re.search(r"(?:rappelle[- ]moi|fais[- ]moi penser)\s+(?:de |d'|à |a |qu'|que )?(.*)", t, re.IGNORECASE)
    objet = m.group(1) if m else ""
    # Retire la partie temporelle
    objet = re.split(r"\s+(?:dans|à|a|vers|pour|demain|ce soir|cet après|cet apres)\b", objet, flags=re.IGNORECASE)[0]
    return objet.strip(" .,!?")


async def resoudre_alarmes_localement(texte: str):
    """Pose, liste ou annule alarmes, minuteurs et rappels. None si la phrase n'en parle pas."""
    t = _normaliser(texte)

    est_minuteur = any(m in t + " " for m in _MOTS_MINUTEUR)
    est_alarme = any(m in t for m in _MOTS_ALARME)
    est_rappel = any(m in t for m in _MOTS_RAPPEL)
    if not (est_minuteur or est_alarme or est_rappel):
        return None

    annuler = any(re.search(rf"\b{v}", t) for v in _VERBES_ANNULER)
    lister = any(v in t for v in _VERBES_LISTER) and not annuler

    # ── Minuteur ──
    if est_minuteur and not est_alarme:
        if annuler:
            ok, msg = annuler_alarme(label="Minuteur")
            send_web_broadcast_sync({"action": "timer_stop"})
            return f"Minuteur arrêté{nom_virgule()}." if ok else f"Aucun minuteur en cours{nom_virgule()}."
        if lister:
            return lister_alarmes()
        secondes = parser_duree(t)
        if not secondes:
            return f"Pour combien de temps{nom_virgule()} ? Dites par exemple : minuteur de 5 minutes."
        duree = _duree_parlee(secondes)
        ok, msg = ajouter_alarme(f"dans {secondes} secondes", f"Minuteur de {duree}")
        if not ok:
            return msg
        send_web_broadcast_sync({"action": "timer_start", "duration": secondes})
        return f"Minuteur de {duree} lancé{nom_virgule()}."

    # ── Rappel ──
    if est_rappel and not est_alarme:
        cible = parser_heure(t)
        if cible is None:
            return None  # « rappelle-moi ce que j'ai dit » : laissé à l'IA
        objet = _objet_rappel(texte)
        ok, msg = ajouter_alarme(t, f"Rappel : {objet}" if objet else "Rappel")
        return msg

    # ── Alarme / réveil ──
    if lister:
        return lister_alarmes()
    if annuler:
        if re.search(r"\b(toutes|tous|tout)\b", t):
            ok, msg = annuler_alarme(heure_texte="toutes")
            return msg
        if parser_heure(t) is not None:
            ok, msg = annuler_alarme(heure_texte=t)
            return msg
        ok, msg = annuler_alarme(label="Alarme")
        if not ok:
            ok, msg = annuler_alarme(label="Réveil")
        return msg
    cible = parser_heure(t)
    if cible is None:
        return f"À quelle heure{nom_virgule()} ? Dites par exemple : alarme à 7 heures, ou dans 20 minutes."
    label = "Réveil" if "reveil" in t else "Alarme"
    ok, msg = ajouter_alarme(t, label)
    return msg
