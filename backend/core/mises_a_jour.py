"""Mises à jour : compare la version installée à la dernière release publiée sur GitHub.

Messages (frontend -> backend) :
  {"type": "check_update", "auto": true|false}   -> {"type": "update_status", ...}
  {"type": "open_release", "url": "https://github.com/NeyorDEV/J.A.R.V.I.S/..."}  (ouvre la page dans le navigateur)

La vérification automatique (au lancement) se coupe avec « maj_auto »: false dans jarvis_config.json
(case dans Paramètres) ; la vérification manuelle reste toujours possible. Seule la page de la release est
ouverte : rien n'est téléchargé ni installé sans l'utilisateur. Seule requête : l'API publique de GitHub,
sans clé ni identifiant (voir PRIVACY.md).
"""

import asyncio
import json
import os
import re

import core.shared as shared

DEPOT = "NeyorDEV/J.A.R.V.I.S"
URL_API = f"https://api.github.com/repos/{DEPOT}/releases/latest"
PREFIXE_PAGES = f"https://github.com/{DEPOT}/"


def _version(texte):
    """« v9.5.1 » -> (9, 5, 1) ; comparaison par nombres : 9.10.0 > 9.5.1."""
    nombres = [int(n) for n in re.findall(r"\d+", str(texte).lstrip("vV"))[:3]]
    return tuple(nombres + [0] * (3 - len(nombres)))


def comparer(actuelle, derniere):
    """« disponible » si la dernière version est plus récente, sinon « a_jour »."""
    return "disponible" if _version(derniere) > _version(actuelle) else "a_jour"


def _auto_active():
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("maj_auto", True) is not False
    except Exception:
        return True


def verifier(auto=False):
    """Interroge GitHub (bloquant : à lancer dans un thread). Retourne le message « update_status »."""
    actuelle = getattr(shared, "CURRENT_VERSION", "0.0.0")
    base = {"type": "update_status", "actuelle": actuelle, "auto": bool(auto)}
    try:
        import requests
        r = requests.get(URL_API, timeout=6, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "JARVIS-updater"})
        if r.status_code == 404:  # aucune release publiée
            return {**base, "etat": "a_jour", "version": actuelle}
        r.raise_for_status()
        d = r.json()
        tag = str(d.get("tag_name", "")).strip()
        if not tag:
            return {**base, "etat": "erreur", "detail": "Réponse de GitHub incomplète."}
        installateur = next((a.get("browser_download_url") for a in d.get("assets", [])
                             if str(a.get("name", "")).lower().endswith(".exe")), "")
        notes = re.sub(r"\r", "", str(d.get("body", "") or "")).strip()
        notes = re.split(r"\n#{1,3} ", notes + "\n")[0] if len(notes) > 700 else notes
        return {**base, "etat": comparer(actuelle, tag), "version": tag.lstrip("vV"),
                "notes": notes[:700], "url": d.get("html_url") or PREFIXE_PAGES + "releases",
                "installateur": installateur}
    except Exception as e:
        print(f"[UPDATE] Vérification impossible : {type(e).__name__}")
        return {**base, "etat": "erreur", "detail": "Impossible de joindre GitHub (connexion ?)."}


async def ws_check_update(websocket, data):
    auto = bool((data or {}).get("auto"))
    if auto and not _auto_active():
        return  # vérification au lancement désactivée dans les Paramètres : aucune requête
    resultat = await asyncio.get_running_loop().run_in_executor(None, verifier, auto)
    await websocket.send(json.dumps(resultat, ensure_ascii=False))


async def ws_open_release(websocket, data):
    """Ouvre la page de la release dans le navigateur (seulement une page du dépôt du projet)."""
    url = str((data or {}).get("url", ""))
    if not url.startswith(PREFIXE_PAGES):
        print(f"[UPDATE] Ouverture refusée (hors du dépôt du projet) : {url[:80]!r}")
        return
    import webbrowser
    webbrowser.open(url)
