"""
alarm_manager.py — Système d'alarmes pour JARVIS
Permet de définir des alarmes à une heure précise, de les annuler et de les lister.
Les alarmes sont persistées dans un fichier JSON et survivent aux redémarrages.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
import re
from core.interlocuteur import nom_virgule

_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_dir))  # backend/module/ -> racine projet
ALARM_FILE = os.path.join(_root, "data", "alarmes.json")

# Callback global — sera défini par main2.py
_parler_callback = None
_alarme_sonner_callback = None

def set_parler_callback(fn):
    global _parler_callback
    _parler_callback = fn

def set_sonner_callback(fn):
    global _alarme_sonner_callback
    _alarme_sonner_callback = fn


# ── Persistance ──────────────────────────────────────────────────────────────

# Verrou partagé : le démon relit/réécrit le fichier toutes les secondes tandis
# que le thread de commande y ajoute ou en retire. Sans lui, poser une alarme au
# moment exact où une autre sonne faisait disparaître silencieusement la nouvelle
# (le démon réécrivait sa liste périmée par-dessus).
_VERROU_ALARMES = threading.RLock()


def _charger_alarmes() -> list:
    with _VERROU_ALARMES:
        if not os.path.exists(ALARM_FILE):
            return []
        try:
            with open(ALARM_FILE, "r", encoding="utf-8") as f:
                donnees = json.load(f)
                return donnees if isinstance(donnees, list) else []
        except Exception as e:
            print(f"[ALARME] Fichier illisible ({e}) — liste vide utilisée.")
            return []

def _sauvegarder_alarmes(alarmes: list):
    # Écriture atomique : une coupure en plein open("w") laissait un JSON
    # tronqué, donc toutes les alarmes perdues au redémarrage.
    with _VERROU_ALARMES:
        try:
            os.makedirs(os.path.dirname(ALARM_FILE), exist_ok=True)
            temporaire = ALARM_FILE + ".tmp"
            with open(temporaire, "w", encoding="utf-8") as f:
                json.dump(alarmes, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporaire, ALARM_FILE)
        except Exception as e:
            print(f"[ALARME] Erreur sauvegarde : {e}")


# ── Parsing de l'heure ───────────────────────────────────────────────────────

def parser_heure(texte: str) -> datetime | None:
    """
    Convertit une chaîne en objet datetime pour aujourd'hui (ou demain si déjà passé).
    Exemples : "midi", "minuit", "14h30", "14:30", "9h", "dans 2 heures", "dans 30 minutes"
    """
    maintenant = datetime.now()
    texte = texte.lower().strip()

    # Mots spéciaux
    if texte in ("midi", "12h", "12:00"):
        cible = maintenant.replace(hour=12, minute=0, second=0, microsecond=0)
    elif texte in ("minuit", "0h", "00h", "0:00", "00:00"):
        cible = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    # "dans X heures / X minutes"
    elif m := re.search(r'dans\s+(\d+)\s*heure', texte):
        cible = maintenant + timedelta(hours=int(m.group(1)))
        cible = cible.replace(second=0, microsecond=0)
    elif m := re.search(r'dans\s+(\d+)\s*min', texte):
        cible = maintenant + timedelta(minutes=int(m.group(1)))
        cible = cible.replace(second=0, microsecond=0)
    # Format "14h30" ou "14:30" ou "9h" ou "9:00"
    elif m := re.search(r'(\d{1,2})[h:](\d{2})', texte):
        heure, minute = int(m.group(1)), int(m.group(2))
        cible = maintenant.replace(hour=heure, minute=minute, second=0, microsecond=0)
    elif m := re.search(r'(\d{1,2})h', texte):
        cible = maintenant.replace(hour=int(m.group(1)), minute=0, second=0, microsecond=0)
    else:
        return None

    # Si l'heure est déjà passée aujourd'hui → demain
    if cible <= maintenant:
        cible += timedelta(days=1)

    return cible


# ── API publique ──────────────────────────────────────────────────────────────

def ajouter_alarme(heure_texte: str, label: str = "Alarme") -> tuple[bool, str]:
    """
    Ajoute une alarme. Retourne (True, message) ou (False, erreur).
    """
    cible = parser_heure(heure_texte)
    if cible is None:
        return False, f"Je n'ai pas compris l'heure '{heure_texte}'. Essayez '14h30' ou 'dans 2 heures'."

    # Le verrou couvre lecture + écriture d'un seul tenant, sinon le démon
    # (qui recharge/réécrit chaque seconde) pouvait écraser l'ajout.
    with _VERROU_ALARMES:
        alarmes = _charger_alarmes()

        # Vérification doublon
        ts = cible.isoformat()
        for a in alarmes:
            if a["heure"] == ts and a["label"] == label:
                return False, f"Vous avez déjà une alarme '{label}' à {cible.strftime('%H:%M')}."

        alarmes.append({
            "heure": ts,
            "label": label,
            "sonne": False
        })
        _sauvegarder_alarmes(alarmes)

    # Formatage du message
    maintenant = datetime.now()
    delta = cible - maintenant
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes >= 60:
        delta_str = f"dans {total_minutes // 60}h{total_minutes % 60:02d}"
    else:
        delta_str = f"dans {total_minutes} minutes"

    jour = "demain" if cible.date() != maintenant.date() else "aujourd'hui"
    return True, f"Alarme '{label}' programmée pour {jour} à {cible.strftime('%H:%M')} ({delta_str})."


def annuler_alarme(heure_texte: str = "", label: str = "") -> tuple[bool, str]:
    """
    Annule une alarme par heure ou par label.
    """
    # Verrou tenu sur toute la séquence lecture → filtrage → écriture
    with _VERROU_ALARMES:
      alarmes = _charger_alarmes()
      if not alarmes:
        return False, f"Vous n'avez aucune alarme active{nom_virgule()}."

      # Gestion de l'annulation globale
      mots_globaux = {"toutes", "tout", "tous", "all", "clear"}
      if (heure_texte and heure_texte.lower().strip() in mots_globaux) or (label and label.lower().strip() in mots_globaux):
        _sauvegarder_alarmes([])
        return True, f"Toutes vos alarmes ont été annulées ({len(alarmes)} alarmes supprimées){nom_virgule()}."

      nouvelles = []
      supprimees = []

      for a in alarmes:
        heure_dt = datetime.fromisoformat(a["heure"])
        match = False
        if label and label.lower() in a["label"].lower():
            match = True
        if heure_texte:
            cible = parser_heure(heure_texte)
            if cible and abs((cible - heure_dt).total_seconds()) < 120:  # ±2 min
                match = True
        if match:
            supprimees.append(a)
        else:
            nouvelles.append(a)

      if not supprimees:
        desc = label or heure_texte or "cette alarme"
        return False, f"Je n'ai pas trouvé d'alarme correspondant à '{desc}'."

      _sauvegarder_alarmes(nouvelles)
    noms = ", ".join(f"'{a['label']}' à {datetime.fromisoformat(a['heure']).strftime('%H:%M')}" for a in supprimees)
    return True, f"Alarme(s) annulée(s) : {noms}."


def lister_alarmes() -> str:
    alarmes = _charger_alarmes()
    actives = [a for a in alarmes if not a.get("sonne")]
    if not actives:
        return f"Vous n'avez aucune alarme programmée{nom_virgule()}."

    lignes = ["Voici vos alarmes :"]
    for a in sorted(actives, key=lambda x: x["heure"]):
        heure_dt = datetime.fromisoformat(a["heure"])
        jour = "demain" if heure_dt.date() != datetime.now().date() else "aujourd'hui"
        lignes.append(f"- '{a['label']}' {jour} à {heure_dt.strftime('%H:%M')}")
    return " ".join(lignes)


# ── Thread de surveillance ────────────────────────────────────────────────────

def _surveiller_alarmes():
    """
    Thread qui vérifie toutes les 30 secondes si une alarme doit sonner.
    """
    # print("[ALARME] Démon de surveillance démarré.")
    while True:
        time.sleep(1)
        try:
            maintenant = datetime.now()
            a_sonner = []

            # Section critique la plus courte possible : on relit, on marque les
            # alarmes échues et on réécrit d'un seul tenant. Les callbacks (son,
            # parole) sont exécutés APRÈS la libération du verrou pour ne pas
            # bloquer une commande utilisateur pendant l'énoncé.
            with _VERROU_ALARMES:
                alarmes = _charger_alarmes()
                modifie = False

                for a in alarmes:
                    if a.get("sonne"):
                        continue
                    heure_dt = datetime.fromisoformat(a["heure"])

                    # Déclenche dès qu'on dépasse l'heure (précision à 1s)
                    if maintenant >= heure_dt:
                        print(f"[ALARME] 🔔 Alarme déclenchée : {a['label']} à {heure_dt.strftime('%H:%M:%S')}")
                        a["sonne"] = True
                        modifie = True
                        a_sonner.append(a["label"])

                if modifie:
                    # Nettoyer les alarmes déjà sonnées depuis plus de 5 minutes
                    seuil = maintenant - timedelta(minutes=5)
                    alarmes = [
                        a for a in alarmes
                        if not a.get("sonne") or datetime.fromisoformat(a["heure"]) > seuil
                    ]
                    _sauvegarder_alarmes(alarmes)

            for label_alarme in a_sonner:
                if _alarme_sonner_callback:
                    _alarme_sonner_callback(label_alarme)
                elif _parler_callback:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(_parler_callback(f"🔔 Alarme ! {label_alarme}{nom_virgule()}."))
                    finally:
                        loop.close()

        except Exception as e:
            print(f"[ALARME] Erreur surveillance : {e}")


def demarrer_daemon_alarmes():
    """Lance le thread de surveillance en arrière-plan."""
    t = threading.Thread(target=_surveiller_alarmes, daemon=True, name="AlarmDaemon")
    t.start()
    return t
