"""audit_log.py — Journal d'audit minimal pour les actions sensibles.

Jusqu'ici, les compétences générées par l'IA et les actions destructrices
(désinstallation, suppression, coffre-fort...) n'étaient tracées que par des
print() console — perdus au redémarrage, impossibles à consulter après coup.
Ce module ajoute un historique simple et persistant : un fichier JSONL
append-only (une ligne = un événement), volontairement sans base de données
ni rotation — l'objectif est d'avoir une trace consultable, pas un SIEM.

Convention : `jarvis_audit.log` est couvert par la règle `*.log` existante du
.gitignore, pas besoin d'y toucher.
"""

import json
import os
import time

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_dir))  # backend/core/ -> racine projet
_LOG_PATH = os.path.join(_root, "jarvis_audit.log")


def consigner(evenement: str, **details) -> None:
    """Ajoute une ligne au journal d'audit.

    Ne doit jamais lever d'exception : un échec d'écriture du log ne doit
    jamais faire échouer l'action auditée elle-même.
    """
    entree = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": evenement, **details}
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except Exception:
        pass

def resume_confirmations(jours: int = 7) -> dict:
    """Confirmations des `jours` derniers jours lues dans le journal : par jour (confirmées / annulées ou sans réponse)
    et la dernière. Lecture seule ; renvoie des compteurs à zéro si le journal est absent ou illisible."""
    import datetime
    aujourdhui = datetime.date.today()
    jour_de = {aujourdhui - datetime.timedelta(days=i): i for i in range(jours)}
    par_jour = [{"j": "LMMJVSD"[(aujourdhui - datetime.timedelta(days=jours - 1 - i)).weekday()], "oui": 0, "non": 0} for i in range(jours)]
    derniere = None
    try:
        with open(_LOG_PATH, "rb") as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 1_000_000))
            lignes = f.read().decode("utf-8", errors="ignore").splitlines()
        for ligne in lignes:
            try:
                e = json.loads(ligne)
                if e.get("event") not in ("confirmation_resolue", "confirmation_timeout"):
                    continue
                confirme = bool(e.get("confirme")) if e["event"] == "confirmation_resolue" else None
                derniere = {"message": e.get("message", ""), "confirme": confirme, "ts": e.get("ts", "")}
                age = jour_de.get(datetime.datetime.strptime(e["ts"], "%Y-%m-%d %H:%M:%S").date())
                if age is not None:
                    par_jour[jours - 1 - age]["oui" if confirme else "non"] += 1
            except Exception:
                continue
    except Exception:
        pass
    return {"jours": par_jour, "derniere": derniere}
