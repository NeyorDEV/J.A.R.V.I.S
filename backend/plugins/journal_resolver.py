"""journal_resolver.py — « qu'est-ce que tu as fait hier ? » : résumé parlé de jarvis_audit.log (commandes exécutées, confirmations, actions sensibles)."""
import builtins
import datetime
import re
import unicodedata

from core import audit_log
from core.interlocuteur import nom_virgule

_ETIQUETTES = {"alarmes": "alarmes", "routines": "routines", "echecs": "échecs", "commandes_locales": "commandes", "resoudre_musique": "musique",
               "resoudre_briefing": "briefing", "resoudre_langue": "langue", "resoudre_vue_de_dieu": "vue de Dieu", "resoudre_macros": "macros",
               "resoudre_apps_localement": "applications", "resoudre_tv_localement": "télé", "resoudre_sauvegarde": "sauvegardes",
               "resoudre_presse_papiers": "presse-papiers", "resoudre_navigateur": "navigateur", "resoudre_skills": "compétences"}


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def demande(t: str) -> bool:
    return bool(re.search(r"\b(?:qu'est[- ]ce que|ce que)\s+tu\s+(?:as|a)\s+fait\b|\bqu'as[- ]tu\s+fait\b|\bmon journal\b|\bton journal\b|\bhistorique des actions\b|\bresume (?:de )?(?:ton|ton )?activite\b", t))


def periode(t: str, maintenant: datetime.datetime):
    """(début, fin, libellé) de la période demandée : hier, aujourd'hui (défaut), cette semaine, ce matin."""
    debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    if re.search(r"\bhier\b", t):
        return debut_jour - datetime.timedelta(days=1), debut_jour, "Hier"
    if re.search(r"\b(?:cette semaine|7 derniers jours|sept derniers jours)\b", t):
        return debut_jour - datetime.timedelta(days=6), maintenant, "Ces sept derniers jours"
    if re.search(r"\bce matin\b", t):
        return debut_jour, debut_jour.replace(hour=12), "Ce matin"
    return debut_jour, maintenant, "Aujourd'hui"


def resumer(evenements: list, libelle: str) -> str:
    commandes = [e for e in evenements if e.get("event") == "commande"]
    conf = [e for e in evenements if e.get("event") in ("confirmation_resolue", "confirmation_timeout")]
    refus = sum(1 for e in conf if not e.get("confirme"))
    autres = [e for e in evenements if e.get("event") not in ("commande", "confirmation_resolue", "confirmation_timeout")]
    if not commandes and not conf and not autres:
        return f"{libelle}, je n'ai rien consigné."
    morceaux = []
    if commandes:
        par = {}
        for e in commandes:
            nom = _ETIQUETTES.get(e.get("resolveur"), str(e.get("resolveur") or "autres").replace("resoudre_", "").replace("_", " "))
            par[nom] = par.get(nom, 0) + 1
        top = sorted(par.items(), key=lambda kv: -kv[1])[:4]
        morceaux.append(f"{len(commandes)} commande{'s' if len(commandes) > 1 else ''} (" + ", ".join(f"{n} {nom}" for nom, n in top) + ")")
    if conf:
        morceaux.append(f"{len(conf)} confirmation{'s' if len(conf) > 1 else ''}" + (f", dont {refus} refusée{'s' if refus > 1 else ''} ou sans réponse" if refus else ""))
    if autres:
        morceaux.append(f"{len(autres)} action{'s' if len(autres) > 1 else ''} sensible{'s' if len(autres) > 1 else ''}")
    derniere = commandes[-1]["texte"] if commandes and commandes[-1].get("texte") else ""
    return f"{libelle} : " + ", ".join(morceaux) + "." + (f" La dernière : « {derniere} »." if derniere else "")


async def resoudre_journal(cmd: str):
    t = _norm(cmd.strip())
    if not demande(t):
        return None
    debut, fin, libelle = periode(t, datetime.datetime.now())
    return resumer(audit_log.evenements_entre(debut, fin), libelle) + ("" if audit_log.journal_existe() else f" Le journal est vide{nom_virgule()}.")


builtins.resoudre_journal = resoudre_journal
