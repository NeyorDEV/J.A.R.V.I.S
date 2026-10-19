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

