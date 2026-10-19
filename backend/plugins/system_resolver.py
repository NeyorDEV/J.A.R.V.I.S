import os
import psutil
import pyautogui
import builtins
import random
import re
from core.interlocuteur import nom_virgule

def nettoyer_accent(texte):
    """Supprime les accents pour faciliter la comparaison."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize('NFD', texte) if unicodedata.category(c) != 'Mn')

# Volume d'un autre appareil que le PC : laissé à son resolver (télé, Deezer) ou à l'IA (HomePod)
_AUTRES_CIBLES_SON = ["homepod", "enceinte", "tele", " tv", "television", "deezer", "spotify",
                      "musique", "chanson", "telephone", "portable"]
# Batterie d'un autre appareil que le PC
_AUTRES_BATTERIES = ["telephone", "portable", "iphone", "android", "montre", "casque", "souris",
                     "clavier", "manette", "tablette", "ecouteurs", "aspirateur"]

async def resoudre_commandes_systeme(cmd):
    """Gère les commandes matérielles du PC (Volume, Screenshot, Système)."""
    t = nettoyer_accent(cmd.lower().strip())

    # 1. VOLUME PC (seulement si aucun autre appareil n'est visé : « baisse le volume du
    #    HomePod du salon » réglait le volume du PC)
    son = "volume" in t or re.search(r"\bson\b", t)
    if son and not any(k in f" {t}" for k in _AUTRES_CIBLES_SON):
        if any(k in t for k in ["augmente", "monte", "hausse", "plus fort", "plus haut"]):
            for _ in range(5): pyautogui.press("volumeup")
            return f"Volume du PC augmenté{nom_virgule()}."
        if any(k in t for k in ["baisse", "diminue", "moins fort", "plus bas"]):
            for _ in range(5): pyautogui.press("volumedown")
            return f"Volume du PC baissé{nom_virgule()}."
        if any(k in t for k in ["muet", "coupe", "sourdine", "retablis", "remets le son"]):
            pyautogui.press("volumemute")
            return f"Son du PC coupé ou rétabli{nom_virgule()}."

    # 2. SCREENSHOT (« capture » seul visait aussi « capture la carte »…)
    if "screenshot" in t or re.search(r"capture (d'|d )?ecran", t):
        try:
            import winshell
            desktop = winshell.desktop()
        except:
            from core.dossiers import dossier_connu
            desktop = dossier_connu("bureau")

        if not os.path.exists(desktop): desktop = os.getcwd()
        path = os.path.join(desktop, f"screenshot_{random.randint(1000,9999)}.png")
        pyautogui.screenshot(path)
        return f"Capture d'écran sauvegardée sur votre bureau{nom_virgule()}."

    return None

_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
         "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

# Heure / date du jour sans IA (« il est quelle heure ? » partait aux moteurs en ligne :
# jusqu'à 20 s d'attente quand l'un d'eux ne répondait pas)
_Q_HEURE = re.compile(r"\b(quelle heure|l'heure qu'il est|quelle est l'heure|(tu as|t'as|tu aurais|t'aurais) l'heure"
                      r"|(donne|dis)[- ]moi l'heure|c'est quoi l'heure)\b|^il est combien$")
_Q_DATE = re.compile(r"\b(quelle date|quel jour (on est|sommes[- ]nous|est[- ]on|nous sommes)|on est quel jour"
                     r"|c'est quel jour|on est le combien|on est quelle date|(c'est quoi|quelle est) la date"
                     r"|la date (d'aujourd'hui|du jour|aujourd'hui)|date du jour)\b")
_Q_MOIS = re.compile(r"\b(on est en quel mois|quel mois (on est|sommes[- ]nous|est[- ]on)|c'est quel mois)\b")
_Q_ANNEE = re.compile(r"\b(on est en quelle annee|quelle annee (on est|sommes[- ]nous|est[- ]on)|c'est quelle annee)\b")
# Heure d'ailleurs (« … à Tokyo » : plugins/time_resolver.py) ou d'un événement (« à quelle heure ferme… »)
_HEURE_AUTRE = re.compile(r"\ba quelle heure\b|\b(alarme|reveil|minuteur|rappel)|\b(a|au|aux|en)\s+(?!ce\b)\w")
_DATE_AUTRE = re.compile(r"\b(naissance|tombe|anniversaire|noel|paques|ferie|demain|hier|a quelle date)\b")


def _date_heure_du_jour(t):
    import datetime
    maintenant = datetime.datetime.now()
    if _Q_HEURE.search(t) and not _HEURE_AUTRE.search(t):
        return f"Il est {maintenant.hour}h{maintenant.minute:02d}{nom_virgule()}."
    if _DATE_AUTRE.search(t):
        return None
    if _Q_DATE.search(t):
        jour = _JOURS[maintenant.weekday()]
        return f"Nous sommes le {jour} {maintenant.day} {_MOIS[maintenant.month - 1]} {maintenant.year}{nom_virgule()}."
    if _Q_MOIS.search(t):
        return f"Nous sommes en {_MOIS[maintenant.month - 1]}{nom_virgule()}."
    if _Q_ANNEE.search(t):
        return f"Nous sommes en {maintenant.year}{nom_virgule()}."
    return None


async def traiter_infos_systeme(cmd):
    """Donne l'heure, la date et des informations sur l'état du PC."""
    t = nettoyer_accent(cmd.lower().strip()).replace("’", "'").rstrip(" ?!.")
    mots = re.findall(r'\b\w+\b', t)

    reponse = _date_heure_du_jour(t)
    if reponse:
        return reponse

    if "processeur" in t or "cpu" in mots:
        usage = psutil.cpu_percent(interval=1)
        return f"La charge actuelle du processeur est de {usage}%{nom_virgule()}."

    # « mémoire » seul visait aussi « qu'as-tu en mémoire ? » ou « consolide ta mémoire »
    if "ram" in mots or "memoire vive" in t or (
            "memoire" in t and any(k in t for k in ["utilisation", "usage", "occupee", "libre", "charge du pc", "du pc", "de l'ordinateur"])):
        ram = psutil.virtual_memory()
        return f"L'utilisation de la mémoire vive est de {ram.percent}%{nom_virgule()}."

    if "batterie" in t and not any(k in t for k in _AUTRES_BATTERIES):
        batt = psutil.sensors_battery()
        if batt:
            offset_m = "en charge" if batt.power_plugged else "sur batterie"
            return f"La batterie est à {batt.percent}% et l'appareil est {offset_m}."
        return f"Je ne parviens pas à détecter de batterie sur ce système{nom_virgule()}."

    return None

# Injection builtins
builtins.resoudre_commandes_systeme = resoudre_commandes_systeme
builtins.traiter_infos_systeme = traiter_infos_systeme
