import os
import time
import asyncio
import random
import re
import requests
import builtins
from wakeonlan import send_magic_packet
from adb_shell.adb_device import AdbDeviceTcp
from adb_shell.auth.sign_pythonrsa import PythonRSASigner as sign_with_rsa_key
from adb_shell.auth.keygen import keygen
from core.interlocuteur import nom_virgule

# --- CONFIGURATION (Philips 43PUS7906/12) ---
TV_NAME = "43PUS7906/12"
TV_IP   = "192.168.0.151"
TV_MAC  = "24-b7-2a-74-97-db"
# backend/plugins/ → racine du projet = 3 niveaux au-dessus (le calcul précédent
# s'arrêtait à backend/ et cherchait la clé dans backend/config/, inexistant :
# une nouvelle clé ADB était donc régénérée à chaque fois, obligeant à ré-autoriser
# la connexion sur la TV.)
_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADB_KEY_PATH = os.path.join(_RACINE, "config", "adb_key")

def get_adb_signer():
    """Génère ou récupère la clé de signature ADB."""
    if not os.path.exists(ADB_KEY_PATH):
        keygen(ADB_KEY_PATH)
    with open(ADB_KEY_PATH) as f:
        priv = f.read()
    with open(ADB_KEY_PATH + ".pub") as f:
        pub = f.read()
    return sign_with_rsa_key(pub, priv)

async def adb_command(cmd_shell):
    """Exécute une commande shell ADB sur la télé."""
    device = None
    try:
        signer = get_adb_signer()
        device = AdbDeviceTcp(TV_IP, 5555, default_transport_timeout_s=3)
        device.connect(rsa_keys=[signer], auth_timeout_s=3)
        device.shell(cmd_shell)
        return True
    except Exception as e:
        print(f"[TV] Commande ADB échouée ({cmd_shell!r}) : {e}")
        return False
    finally:
        # La fermeture était placée après le shell() : dès qu'une exception
        # survenait, la connexion TCP vers le port 5555 de la TV restait
        # ouverte. À force d'échecs, les emplacements ADB de la TV étaient
        # tous occupés et plus aucune commande ne passait.
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

# --- LOGIQUE TECHNIQUE ---

async def tv_allumer():
    for port in [7, 9]:
        send_magic_packet(TV_MAC, ip_address="192.168.0.255", port=port)
    await asyncio.sleep(2)
    if await adb_command("input keyevent 224"):
        await adb_command("input keyevent 3")
        return f"J'ai allumé votre télé{nom_virgule()}."
    return "J'ai envoyé le signal de réveil à la télé, Monsieur."

async def tv_eteindre():
    if await adb_command("input keyevent 26"): return f"J'ai éteint la télé{nom_virgule()}."
    return "Échec de l'extinction."

async def tv_quitter_app():
    if await adb_command("input keyevent 3"): return f"J'ai fermé l'application sur la télé{nom_virgule()}."
    return "Échec du retour à l'accueil."

async def tv_volume(direction, steps=5):
    """Gère le volume via ADB par paquets."""
    key = "24" if direction == "monter" else "25"
    # Bornage : le nombre de pas provient d'un chiffre extrait de la phrase.
    # « monte le son de la tv à 200 » envoyait réellement 200 appuis, soit une
    # dizaine de secondes de martèlement sur une socket au timeout de 10 s.
    try:
        steps = max(1, min(int(steps), 30))
    except (TypeError, ValueError):
        steps = 5

    device = None
    try:
        signer = get_adb_signer()
        device = AdbDeviceTcp(TV_IP, 5555, default_transport_timeout_s=10)
        device.connect(rsa_keys=[signer], auth_timeout_s=5)
        remaining = steps
        while remaining > 0:
            batch = min(remaining, 20)
            touches = " ".join([key] * batch)
            device.shell(f"input keyevent {touches}")
            remaining -= batch
            if remaining > 0: await asyncio.sleep(0.1)
        return f"Volume de la télé ajusté de {steps} points, Monsieur."
    except Exception as e:
        # On ne prétend plus que l'opération a réussi : l'ancien message
        # « Le volume de la télé a été modifié » était affiché même en cas
        # d'échec total de la connexion.
        print(f"[TV] Réglage du volume échoué : {e}")
        return f"Je n'ai pas réussi à joindre la télé pour régler le volume{nom_virgule()}."
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

async def tv_lancer_app(app_name):
    apps = {
        "netflix": "com.netflix.ninja", "disney": "com.disney.disneyplus",
        "prime video": "com.amazon.amazonvideo.livingroom", "youtube": "com.google.android.youtube.tv",
        "deezer": "deezer.android.tv", "twitch": "tv.twitch.android.app",
        "apple tv": "com.apple.atve.androidtv.appletv", "crunchyroll": "com.crunchyroll.crunchyroid"
    }
    pkg = apps.get(app_name.lower())
    if not pkg: return f"Je ne connais pas l'application {app_name}."
    cmd = f"monkey -p {pkg} 1"
    if app_name.lower() in ["prime video", "prime"]: cmd = f"am start -n {pkg}/com.amazon.ignition.IgnitionActivity"
    if await adb_command(cmd): return f"J'ai lancé {app_name} sur la télé{nom_virgule()}."
    return f"Impossible de lancer {app_name}."

async def tv_lancer_youtube(video_id):
    cmd = f'am start -a android.intent.action.VIEW "vnd.youtube://www.youtube.com/watch?v={video_id}"'
    if await adb_command(cmd): return f"C'est lancé sur votre télé{nom_virgule()} !"
    return "Erreur lors du lancement YouTube."

def chercher_youtube(recherche):
    try:
        query = requests.utils.quote(recherche)
        url = f"https://www.youtube.com/results?search_query={query}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        video_ids = re.findall(r"watch\?v=(\S{11})", resp.text)
        return video_ids[0] if video_ids else None
    except: return None

# --- RÉSOLVEUR ---

def _sans_accent(s: str) -> str:
    """Minuscule sans accents, pour comparer indifféremment « télé » et « tele »."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower().strip())
                   if unicodedata.category(c) != "Mn")


async def resoudre_tv_localement(texte):
    """Analyse les ordres relatifs à la télévision."""
    # On compare sur la version dé-accentuée : selon le chemin d'entrée (STT,
    # clavier, phrase canonique du dispatch LLM), le texte peut arriver avec ou
    # sans accents. Les mots-clés ci-dessous sont donc écrits sans accent.
    t = _sans_accent(texte)

    if any(k in t for k in ["tele", "tv", "philips", "television"]):
        # Volume précis
        if any(k in t for k in ["son", "volume"]):
            direction = "monter" if any(k in t for k in ["monte", "augmente", "plus", "hausse"]) else "baisser"
            steps = 10
            if "un peu" in t: steps = 3
            if any(k in t for k in ["beaucoup", "fortement", "bien"]): steps = 25
            chiffres = re.findall(r'\d+', t)
            if chiffres: steps = int(chiffres[0])
            return await tv_volume(direction, steps)

        # Allumage / Extinction
        if any(k in t for k in ["allume", "demarre", "lance"]):
            if len(t.split()) < 5: return await tv_allumer()
        if any(k in t for k in ["eteins", "veille", "arrete"]):
            return await tv_eteindre()

        # Quitter / Accueil
        if any(k in t for k in ["ferme", "quitte", "quitter", "fermer", "accueil", "home"]):
            return await tv_quitter_app()

        # YouTube spécifique
        if "youtube" in t and any(k in t for k in ["lance", "mets", "joue"]):
            recherche = t
            for p in ["sur ma tele", "sur la tele", "sur ma tv", "sur la tv", "youtube", "mets", "joue", "lance", "ouvre", "sur la", "sur ma", "sur"]:
                recherche = recherche.replace(p, "")
            recherche = recherche.strip()
            if recherche:
                v_id = chercher_youtube(recherche)
                if v_id: return await tv_lancer_youtube(v_id)
            return await tv_lancer_app("youtube")

        # Autres Apps
        for app in ["netflix", "disney", "prime video", "deezer", "crunchyroll", "apple tv"]:
            if app in t and any(k in t for k in ["lance", "mets", "ouvre"]):
                return await tv_lancer_app(app)

        # Contrôles basiques
        if "pause" in t: await adb_command("input keyevent 85"); return "C'est fait."
        if "stop" in t: return await tv_quitter_app()

    return None

# Injection builtins
builtins.resoudre_tv_localement = resoudre_tv_localement
