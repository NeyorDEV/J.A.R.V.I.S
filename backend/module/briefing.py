"""Briefing du matin : « Jarvis, ma journée » → date, météo, agenda du jour, tâches, alarmes, mails non lus, en une seule phrase dite.

La phrase (`composer`) est une logique pure, testée dans tests/test_briefing.py. Chaque source (`_meteo`, `_agenda`…) renvoie None en cas de panne ou de service non
configuré : le briefing la passe sous silence au lieu de dire une erreur. Le resolver (plugins/briefing_resolver.py) lance les sources en parallèle.
"""
import re
from datetime import datetime

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_DEMANDE = re.compile(
    r"\b(ma journee|mon briefing|le briefing|briefing du (matin|jour)|resume de ma journee|programme (du jour|de la journee|d aujourd hui)|"
    r"(qu est ce que|qu est ce qu|quoi) (j ai|de prevu|y a t il|il y a) (aujourd hui|de prevu aujourd hui|au programme)|"
    r"mon programme|ce que j ai aujourd hui|(que|quoi) (j ai|de neuf) (aujourd hui|ce matin))\b")


def demande(t: str) -> bool:
    """t : phrase en minuscules sans accents."""
    return bool(_DEMANDE.search(re.sub(r"[-'’]", " ", t)))


def _heure(d: datetime) -> str:
    return f"{d.hour} h" + (f" {d.minute:02d}" if d.minute else "")


def _pluriel(n: int, mot: str) -> str:
    return f"{n} {mot}{'s' if n > 1 else ''}"


def _liste(elements) -> str:
    elements = list(elements)
    return elements[0] if len(elements) == 1 else ", ".join(elements[:-1]) + " et " + elements[-1]


def composer(maintenant: datetime, meteo=None, evenements=None, taches=None, alarmes=None, mails=None, nom: str = "") -> str:
    """meteo : phrase ou None ; evenements : [(datetime|None = toute la journée, titre)] ; taches : [titre] ; alarmes : [(datetime, libellé)] ; mails : nombre ou None."""
    salut = "Bonsoir" if maintenant.hour >= 18 else "Bonjour"
    morceaux = [f"{salut}{' ' + nom if nom else ''}. Nous sommes {_JOURS[maintenant.weekday()]} {maintenant.day} {_MOIS[maintenant.month - 1]}."]
    if meteo:
        morceaux.append(meteo.rstrip(" .") + ".")
    if evenements is None:
        pass   # agenda non disponible : on n'en dit rien
    elif not evenements:
        morceaux.append("Rien à l'agenda pour le reste de la journée.")
    else:
        vus = [(f"{titre}, toute la journée" if d is None else f"{titre} à {_heure(d)}") for d, titre in evenements[:5]]
        reste = len(evenements) - len(vus)
        morceaux.append(f"À l'agenda : {_liste(vus)}" + (f", et {_pluriel(reste, 'autre')}" if reste else "") + ".")
    if taches:
        vues = taches[:3]
        morceaux.append(f"{_pluriel(len(taches), 'tâche')} à faire : {_liste(vues)}" + (f", et {len(taches) - len(vues)} de plus" if len(taches) > len(vues) else "") + ".")
    if alarmes:
        morceaux.append("Alarmes : " + _liste(f"{lib} à {_heure(d)}" for d, lib in alarmes[:3]) + ".")
    if mails:
        morceaux.append(f"Vous avez {_pluriel(mails, 'mail')} non {'lus' if mails > 1 else 'lu'}.")
    elif mails == 0:
        morceaux.append("Aucun mail non lu.")
    return " ".join(morceaux)


# ── Sources (bloquantes : appelées dans un thread) ────────────────────────────

def _google_pret() -> bool:
    """Jeton Google présent et utilisable SANS interaction : identifiants_google() ouvrirait sinon une fenêtre de connexion (une par source en parallèle)."""
    try:
        import os
        import pickle
        from module.google_services import SCOPES
        racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(racine, "config", "token.pickle"), "rb") as f:
            creds = pickle.load(f)
        return all(s in (getattr(creds, "scopes", None) or []) for s in SCOPES) and bool(creds.valid or (creds.expired and creds.refresh_token))
    except Exception:
        return False


def _meteo():
    try:
        from module.meteo_domotique import meteo_du_moment
        texte = meteo_du_moment()
        return None if "pas accessible" in texte else texte.replace("C'est tout.", "")
    except Exception:
        return None


def _agenda():
    try:
        if not _google_pret():
            return None
        from module.google_services import service_agenda
        service = service_agenda()
        if not service:
            return None
        maintenant = datetime.now().astimezone()
        fin = maintenant.replace(hour=23, minute=59, second=59)
        items = service.events().list(calendarId="primary", timeMin=maintenant.isoformat(), timeMax=fin.isoformat(), singleEvents=True, orderBy="startTime", maxResults=15).execute().get("items", [])
        sortie = []
        for e in items:
            debut = e["start"].get("dateTime")
            sortie.append((datetime.fromisoformat(debut) if debut else None, e.get("summary", "sans titre")))
        return sortie
    except Exception:
        return None


def _taches():
    try:
        if not _google_pret():
            return None
        from module.google_services import get_tasks_service
        service = get_tasks_service()
        if not service:
            return None
        return [i.get("title", "sans titre") for i in service.tasks().list(tasklist="@default", showCompleted=False).execute().get("items", [])]
    except Exception:
        return None


def _mails():
    try:
        if not _google_pret():
            return None
        from module.google_services import service_gmail
        service = service_gmail()
        if not service:
            return None
        return len(service.users().messages().list(userId="me", labelIds=["INBOX"], q="is:unread category:primary", maxResults=20).execute().get("messages", []))
    except Exception:
        return None


def _alarmes():
    try:
        from module.alarm_manager import alarmes_pour_hud
        aujourdhui = datetime.now().date()
        sortie = [(datetime.fromisoformat(a["heure"]), a["label"]) for a in alarmes_pour_hud()]
        return [(d, lib) for d, lib in sortie if d.date() == aujourdhui and d > datetime.now()]
    except Exception:
        return []


SOURCES = {"meteo": _meteo, "evenements": _agenda, "taches": _taches, "mails": _mails, "alarmes": _alarmes}
