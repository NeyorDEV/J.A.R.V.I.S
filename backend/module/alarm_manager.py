"""
alarm_manager.py — Système d'alarmes pour JARVIS
Permet de définir des alarmes à une heure précise, de les annuler et de les lister.
Les alarmes sont persistées dans un fichier JSON et survivent aux redémarrages.
"""

import asyncio
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

def set_parler_callback(fn):
    global _parler_callback
    _parler_callback = fn


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

_NOMBRES_EN_LETTRES = {
    "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
    "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20,
    "vingt-cinq": 25, "trente": 30, "quarante": 40, "quarante-cinq": 45,
    "cinquante": 50, "soixante": 60, "quatre-vingt-dix": 90,
}


def _normaliser_texte_heure(texte: str) -> str:
    """Minuscules, sans accents, nombres écrits en lettres convertis en chiffres."""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", texte.lower().strip())
                if unicodedata.category(c) != "Mn")
    t = t.replace("’", "'")
    t = re.sub(r"\bune? demi[- ]heure\b", "30 minutes", t)
    t = re.sub(r"\bun quart d['\s]?heure\b", "15 minutes", t)
    t = re.sub(r"\btrois quarts d['\s]?heure\b", "45 minutes", t)
    # Les composés (« vingt-cinq ») avant leurs parties (« vingt »)
    for mot in sorted(_NOMBRES_EN_LETTRES, key=len, reverse=True):
        t = re.sub(rf"(?<![\w-]){re.escape(mot)}(?![\w-])", str(_NOMBRES_EN_LETTRES[mot]), t)
    return t


def parser_duree(texte: str) -> int | None:
    """Durée en secondes d'un texte (« 5 minutes », « 2h30 », « 1 heure 30 »,
    « une demi-heure », « 90 secondes »…), ou None si aucune durée n'y figure."""
    t = _normaliser_texte_heure(texte)
    heures = minutes = secondes = 0
    trouve = False
    # « 2h30 » / « 2 h 30 » / « 1 heure 30 » : des minutes sans unité après les heures
    m = re.search(r"(\d+)\s*(?:h(?![a-z])|heures?\b)(?:\s*(?:et\s*)?(\d{1,2})(?!\d|\s*(?:s\b|sec|min|mn)))?", t)
    if m:
        heures = int(m.group(1))
        if m.group(2):
            minutes = int(m.group(2))
        trouve = True
    # « 1 minute 30 » : des secondes sans unité après les minutes
    m = re.search(r"(\d+)\s*(?:min(?:ute)?s?\b|mn\b)(?:\s*(?:et\s*)?(\d{1,2})(?!\d|\s*(?:h|min|mn)))?", t)
    if m:
        minutes = int(m.group(1))
        if m.group(2):
            secondes = int(m.group(2))
        trouve = True
    m = re.search(r"(\d+)\s*(?:s\b|sec\b|secondes?\b)", t)
    if m:
        secondes = int(m.group(1))
        trouve = True
    if not trouve:
        return None
    total = heures * 3600 + minutes * 60 + secondes
    return total if total > 0 else None


def parser_heure(texte: str) -> datetime | None:
    """
    Convertit une chaîne en objet datetime pour aujourd'hui (ou demain si déjà passé).
    Exemples : "midi", "minuit", "14h30", "14:30", "9h", "7h du soir", "8h et demie",
    "dans 2 heures", "dans 2h30", "dans 1 heure 30", "dans une heure", "dans 30 minutes",
    "dans 90 secondes". Retourne None si l'heure n'est pas comprise ou invalide.
    """
    maintenant = datetime.now()
    t = _normaliser_texte_heure(texte)

    # ── Durée relative : « dans … » ──
    m_dans = re.search(r"\bdans\b(.*)", t)
    if m_dans:
        secondes = parser_duree(m_dans.group(1))
        if not secondes:
            return None
        cible = maintenant + timedelta(seconds=secondes)
        return cible.replace(microsecond=0) if secondes % 60 else cible.replace(second=0, microsecond=0)

    # ── Heure absolue ──
    if re.search(r"\bmidi\b", t) and not re.search(r"\d", t):
        heure, minute = 12, 0
    elif re.search(r"\bminuit\b", t) and not re.search(r"\d", t):
        heure, minute = 0, 0
    else:
        m = re.search(r"(\d{1,2})\s*(?:h|heures?|:)\s*(\d{2})?", t)
        if not m:
            return None
        heure = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        if not m.group(2):
            if re.search(r"\bet quart\b", t):
                minute = 15
            elif re.search(r"\bet demie?\b", t):
                minute = 30
            elif re.search(r"\bmoins le quart\b", t):
                heure, minute = heure - 1, 45
        # « du soir », « de l'après-midi » : 7h du soir = 19h
        if heure < 12 and re.search(r"\b(du soir|de l'apres[- ]midi|de l apres[- ]midi|cet apres[- ]midi|ce soir)\b", t):
            heure += 12
        if not (0 <= heure <= 23 and 0 <= minute <= 59):
            return None

    cible = maintenant.replace(hour=heure, minute=minute, second=0, microsecond=0)
    # Si l'heure est déjà passée aujourd'hui (ou si « demain » est précisé) → demain.
    # Avant 4 h du matin, « demain à 6h30 » désigne le matin qui vient, pas le surlendemain.
    demain = re.search(r"\bdemain\b", t) and maintenant.hour >= 4
    if cible <= maintenant or (demain and cible.date() == maintenant.date()):
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
    total_secondes = max(0, int(round(delta.total_seconds())))
    total_minutes = total_secondes // 60
    if total_minutes >= 60:
        delta_str = f"dans {total_minutes // 60}h{total_minutes % 60:02d}"
    elif total_minutes >= 1:
        delta_str = f"dans {total_minutes} minute{'s' if total_minutes > 1 else ''}"
    else:
        delta_str = f"dans {total_secondes} seconde{'s' if total_secondes > 1 else ''}"

    jour = "demain" if cible.date() != maintenant.date() else "aujourd'hui"
    quand = f"{jour} à {cible.strftime('%H:%M')} ({delta_str})"
    if label.startswith("Rappel"):
        return True, f"C'est noté{nom_virgule()}. Je vous le rappellerai {quand}."
    if label == "Réveil":
        return True, f"Réveil programmé pour {quand}."
    if label == "Alarme":
        return True, f"Alarme programmée pour {quand}."
    return True, f"Alarme « {label} » programmée pour {quand}."


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

def _message_sonnerie(label_alarme: str) -> str:
    """Phrase prononcée quand une alarme, un minuteur ou un rappel arrive à échéance."""
    if label_alarme.startswith("Minuteur"):
        return f"Le {label_alarme[0].lower()}{label_alarme[1:]} est terminé{nom_virgule()}."
    if label_alarme.startswith("Rappel"):
        return f"{label_alarme}{nom_virgule()}."
    if label_alarme in ("Alarme", "Réveil"):
        return f"{label_alarme} ! Il est {datetime.now().strftime('%H:%M')}{nom_virgule()}."
    return f"Alarme ! {label_alarme}{nom_virgule()}."


def _notifier_hud_alarme(label_alarme: str):
    """Carte d'alerte sur le HUD quand une alarme ou un minuteur sonne."""
    try:
        import builtins as _b
        envoyer = getattr(_b, "diffuser_web_sync", None)
        if envoyer is None:
            from core.web_bridge import diffuser_web_sync as envoyer
        envoyer({"action": "ctx_card", "title": "ALARME", "text": label_alarme,
                 "type": "alert", "icon": "⏰", "duration": 15000})
    except Exception as e:
        print(f"[ALARME] Notification HUD impossible : {e}")


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
                try:
                    if _parler_callback:
                        # Un « stop » prononcé plus tôt laisse STOP_PARLER à vrai jusqu'à la
                        # commande suivante : sans ce réarmement, l'alarme restait muette.
                        try:
                            from core.etat_parole import set_stop_parler
                            import core.shared as _shared
                            _shared.STOP_PARLER = False
                            set_stop_parler(False)
                        except Exception:
                            pass
                        resultat = _parler_callback(_message_sonnerie(label_alarme))
                        if asyncio.iscoroutine(resultat):
                            _boucle = asyncio.new_event_loop()
                            try:
                                _boucle.run_until_complete(resultat)
                            finally:
                                _boucle.close()
                    _notifier_hud_alarme(label_alarme)
                except Exception as e_alarme:
                    print(f"[ALARME] Erreur annonce de « {label_alarme} » : {e_alarme}")

        except Exception as e:
            print(f"[ALARME] Erreur surveillance : {e}")


def demarrer_daemon_alarmes():
    """Lance le thread de surveillance en arrière-plan."""
    t = threading.Thread(target=_surveiller_alarmes, daemon=True, name="AlarmDaemon")
    t.start()
    return t
