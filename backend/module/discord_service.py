"""Discord : envoyer un message dans un salon (webhook ou bot) ou à quelqu'un (fenêtre Discord, en option).

Trois voies, de la plus sûre à la plus risquée :
  1. WEBHOOK  : adresse propre à un salon (Paramètres du salon › Intégrations). Aucun compte : le message
     s'affiche sous le nom du webhook. Aucun risque pour votre compte.
  2. BOT      : un bot à vous (DISCORD_BOT_TOKEN dans .env) invité sur le serveur ; un salon se désigne par son
     identifiant. Le message s'affiche sous le nom du bot.
  3. FENÊTRE  : JARVIS pilote votre vraie fenêtre Discord (Ctrl+K, nom, message). Écrit EN VOTRE NOM, mais
     Discord interdit d'automatiser un compte utilisateur : désactivé par défaut (« discord_envoi_ui »), toujours
     précédé d'une confirmation, et sans moyen de vérifier le destinataire (Ctrl+K ouvre la première
     correspondance). À vos risques.

Salons : « discord_salons » dans jarvis_config.json, {nom: adresse du webhook ou identifiant de salon}.
Les adresses de webhook sont des secrets : elles ne sont jamais renvoyées en clair au HUD.
"""

import difflib
import json
import os
import re
import time
import unicodedata

import core.shared as shared

_RE_WEBHOOK = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
_RE_CANAL = re.compile(r"^\d{15,25}$")
MASQUE = "••••••••"


def _normaliser(texte):
    sans_accent = "".join(c for c in unicodedata.normalize("NFD", str(texte).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sans_accent)).strip()


def _config():
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salons():
    brut = _config().get("discord_salons", {})
    return {str(k): str(v).strip() for k, v in brut.items() if str(k).strip() and str(v).strip()} if isinstance(brut, dict) else {}


def envoi_fenetre_autorise():
    return _config().get("discord_envoi_ui", False) is True


def type_cible(valeur):
    """« webhook », « canal » (identifiant de salon, via le bot) ou None."""
    if _RE_WEBHOOK.match(valeur):
        return "webhook"
    if _RE_CANAL.match(valeur):
        return "canal"
    return None


def trouver_salon(nom):
    """(alias, valeur) du salon configuré qui correspond le mieux à ce qui a été dit, ou None."""
    q = _normaliser(nom)
    meilleur = (0.0, None)
    for alias, valeur in salons().items():
        a = _normaliser(alias)
        if not a:
            continue
        if q == a:
            score = 1.0
        elif q in a or a in q:
            score = 0.9
        else:
            score = difflib.SequenceMatcher(None, q, a).ratio()
        if score > meilleur[0]:
            meilleur = (score, (alias, valeur))
    return meilleur[1] if meilleur[0] >= 0.75 else None


def masquer_salons(salons_):
    """Version pour le HUD : l'adresse d'un webhook n'est jamais renvoyée en clair."""
    return {a: (MASQUE if type_cible(v) == "webhook" else v) for a, v in salons_.items()}


def fusionner_salons(anciens, nouveaux):
    """Enregistrement depuis le HUD : une valeur masquée signifie « inchangée » (on garde l'adresse existante)."""
    resultat = {}
    for alias, valeur in nouveaux.items():
        valeur = str(valeur).strip()
        if valeur == MASQUE:
            valeur = anciens.get(alias, "")
        if alias.strip() and valeur and type_cible(valeur):
            resultat[alias.strip()] = valeur
    return resultat


def envoyer_salon(valeur, message):
    """Envoie dans un salon (bloquant : à lancer dans un thread). Retourne (ok, détail)."""
    import requests
    contenu = message.strip()[:1900]
    corps = {"content": contenu, "allowed_mentions": {"parse": []}}  # pas de @everyone ni de mentions par la voix
    genre = type_cible(valeur)
    try:
        if genre == "webhook":
            r = requests.post(valeur, json=corps, timeout=8)
        elif genre == "canal":
            jeton = os.getenv("DISCORD_BOT_TOKEN", "").strip()
            if not jeton or jeton.upper().startswith("VOTRE"):
                return False, "jeton du bot Discord manquant"
            r = requests.post(f"https://discord.com/api/v10/channels/{valeur}/messages", json=corps, timeout=8,
                              headers={"Authorization": f"Bot {jeton}",
                                       "User-Agent": "DiscordBot (https://github.com/NeyorDEV/J.A.R.V.I.S, 1)"})
        else:
            return False, "adresse de salon invalide"
        if r.status_code in (200, 204):
            return True, ""
        if r.status_code == 429:
            return False, "Discord demande de patienter quelques secondes"
        if r.status_code in (401, 403, 404):
            return False, "Discord refuse (adresse ou droits du bot incorrects)"
        return False, f"Discord a répondu {r.status_code}"
    except Exception as e:
        return False, f"connexion impossible ({type(e).__name__})"


def _fenetre_discord():
    import psutil
    import win32gui
    import win32process
    trouvees = []

    def rappel(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            try:
                gauche, _haut, droite, _bas = win32gui.GetWindowRect(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if psutil.Process(pid).name().lower() == "discord.exe" and droite - gauche > 300:
                    trouvees.append(hwnd)
            except Exception:
                pass
        return True

    win32gui.EnumWindows(rappel, None)
    return trouvees[0] if trouvees else None


def envoyer_par_fenetre(destinataire, message):
    """Écrit à quelqu'un en pilotant la fenêtre Discord (bloquant). Retourne (ok, détail)."""
    import pyautogui
    import win32gui
    from module.os_autopilot_agent import activer_fenetre, copier_dans_presse_papier
    hwnd = _fenetre_discord()
    if not hwnd:
        return False, "Discord n'est pas ouvert"
    if not activer_fenetre(hwnd):
        return False, "impossible de passer Discord au premier plan"
    time.sleep(0.6)
    if win32gui.GetForegroundWindow() != hwnd:
        return False, "Discord n'est pas passé au premier plan"
    pyautogui.hotkey("ctrl", "k")  # sélecteur rapide de conversations
    time.sleep(0.8)
    copier_dans_presse_papier(destinataire)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.1)
    pyautogui.press("enter")
    time.sleep(1.1)
    if win32gui.GetForegroundWindow() != hwnd:
        return False, "Discord a perdu le premier plan : message non envoyé"
    copier_dans_presse_papier(message.strip()[:1900])
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.4)
    pyautogui.press("enter")
    return True, ""
