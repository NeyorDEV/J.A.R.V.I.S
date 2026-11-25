"""Habitudes : JARVIS repère les commandes que l'utilisateur répète à peu près à la même heure et propose d'en faire des routines.

Source : les lignes « commande » de jarvis_audit.log (core/traitement._consigner_commande), sur les 30 derniers jours.
Une habitude = la même phrase, à ± 60 minutes de l'heure médiane, sur au moins 3 jours différents (et au moins 60 % des jours où la phrase a été dite).
Ne sont jamais proposées : les commandes qui agissent sur le PC (routines.interdite), celles qui sont déjà liées à un horaire (alarmes, routines, macros),
et les phrases tronquées par le journal. Rien n'est créé sans que l'utilisateur dise « transforme l'habitude 2 en routine ».
Pur (testé : tests/test_habitudes.py) : analyser() travaille sur une liste d'événements.
"""
import re
import statistics
from datetime import datetime

from module.routines import interdite, norm

JOURS_MIN = 3
TOLERANCE_MIN = 60        # minutes autour de l'heure médiane
PART_MIN = 0.6            # part des jours où la phrase a été dite à cette heure-là
MAX_HABITUDES = 5
LONGUEUR_MAX = 79         # le journal tronque à 80 caractères : au-delà la phrase est incomplète
_IGNORES = {"alarmes", "routines", "echecs", "resoudre_macros", "resoudre_journal", "resoudre_habitudes", "resoudre_sauvegarde", "resoudre_repetition",
            "resoudre_dictee", "resoudre_presse_papiers", "resoudre_ecran", "resoudre_conversation", "resoudre_langue", "resoudre_voix_roles",
            "resoudre_quota_stt", "resoudre_cout_llm"}


def _commande(texte: str) -> str:
    t = re.sub(r"\b(?:jarvis|s'il te plait|stp)\b", " ", norm(texte))
    return re.sub(r"\s+", " ", re.sub(r"[^\w' -]", " ", t)).strip()


def analyser(evenements: list, deja: set | None = None) -> list:
    """Habitudes détectées, les plus régulières d'abord : [{'commande', 'heure' 'HH:MM', 'jours' [0-6], 'vus', 'total'}]. `deja` : commandes déjà couvertes par une routine."""
    par_commande: dict = {}
    for e in evenements:
        if e.get("event") != "commande" or e.get("resolveur") in _IGNORES:
            continue
        texte = str(e.get("texte") or "")
        c = _commande(texte)
        if not c or len(texte) > LONGUEUR_MAX or len(c.split()) < 2 or interdite(c) or c in (deja or set()):
            continue
        try:
            quand = datetime.strptime(e["ts"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            continue
        jours = par_commande.setdefault(c, {})
        minute = quand.hour * 60 + quand.minute
        jours[quand.date()] = min(minute, jours.get(quand.date(), minute))   # une fois par jour : la première
    sortie = []
    for c, jours in par_commande.items():
        if len(jours) < JOURS_MIN:
            continue
        mediane = statistics.median(jours.values())
        proches = {j: m for j, m in jours.items() if abs(m - mediane) <= TOLERANCE_MIN}
        if len(proches) < JOURS_MIN or len(proches) / len(jours) < PART_MIN:
            continue
        arrondi = int(round(statistics.median(proches.values()) / 5.0) * 5) % (24 * 60)
        semaine = {j.weekday() for j in proches}
        jours_routine = [0, 1, 2, 3, 4] if semaine <= {0, 1, 2, 3, 4} and len(proches) >= 4 else [5, 6] if semaine <= {5, 6} and len(proches) >= 3 else list(range(7))
        sortie.append({"commande": c, "heure": f"{arrondi // 60:02d}:{arrondi % 60:02d}", "jours": jours_routine, "vus": len(proches), "total": len(jours)})
    sortie.sort(key=lambda h: (-h["vus"], -h["vus"] / h["total"], h["commande"]))
    return sortie[:MAX_HABITUDES]


def decrire(h: dict) -> str:
    heure, minute = h["heure"].split(":")
    return f"« {h['commande']} » vers {int(heure)} h{'' if minute == '00' else ' ' + minute}, {h['vus']} jour{'s' if h['vus'] > 1 else ''} sur {h['total']}"


def deja_en_routine() -> set:
    from module import routines
    return {norm(r.get("commande", "")) for r in routines.charger()["routines"]}


def detecter(maintenant: datetime | None = None, jours: int = 30) -> list:
    import datetime as _dt

    from core import audit_log
    fin = maintenant or datetime.now()
    return analyser(audit_log.evenements_entre(fin - _dt.timedelta(days=jours), fin + _dt.timedelta(minutes=1)), deja_en_routine())


def en_routine(h: dict):
    """Crée la routine d'une habitude. Renvoie le texte de la routine, ou None si elle existe déjà ou si la liste est pleine."""
    from module import routines
    with routines._VERROU:
        d = routines.charger()
        r = {"commande": h["commande"], "heure": h["heure"], "jours": h["jours"]}
        if len(d["routines"]) >= 30 or any(x.get("commande") == r["commande"] and x.get("heure") == r["heure"] for x in d["routines"]):
            return None
        d["routines"].append(r)
        routines.sauver(d)
    return routines.decrire(r)
