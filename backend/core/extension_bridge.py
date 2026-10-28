"""Pont sécurisé avec l'extension de navigateur (interfaces/chrome_extension).

Pourquoi : le serveur WebSocket accepte toute origine « chrome-extension:// ». Sans contrôle, n'importe
quelle extension installée dans le navigateur pouvait envoyer des ordres à JARVIS (« user_input » est
traité comme une saisie de confiance) et recevoir tout ce que JARVIS diffuse. Désormais :
  - les connexions de type extension sont tenues À PART des HUD (jamais dans CONNECTED_CLIENTS) ;
  - elles doivent s'authentifier par un jeton secret (« extension_hello ») avant toute chose ;
  - une extension reçoit seulement les ordres qui lui sont destinés (séquences DOM, commandes),
    et JARVIS n'accepte d'elle que ses réponses ;
  - le jeton est affiché dans Paramètres › Sécurité, à coller dans les options de l'extension.

Commandes disponibles pour JARVIS (appeler_extension) : tabs_list, tab_activate, tab_close, media, page_read.
"""

import asyncio
import hmac
import json
import os
import secrets
import uuid

import core.shared as shared

_ATTENTES = {}  # identifiant de commande -> Future résolue par la réponse de l'extension


def _chemin_config():
    return os.path.join(shared.RACINE_PROJET, "jarvis_config.json")


def jeton():
    """Jeton secret de l'extension (créé au premier appel, conservé dans jarvis_config.json)."""
    try:
        with open(_chemin_config(), "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception:
        config = {}
    existant = config.get("extension_jeton")
    if isinstance(existant, str) and len(existant) >= 20:
        return existant
    config["extension_jeton"] = secrets.token_urlsafe(24)
    with open(_chemin_config(), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    return config["extension_jeton"]


def _authentifiees():
    return getattr(shared, "EXTENSIONS_AUTH", set())


async def traiter_message_extension(websocket, data):
    """Seul point d'entrée des messages d'une connexion d'extension (le reste est ignoré)."""
    type_msg = data.get("type")
    if type_msg == "extension_hello":
        if hmac.compare_digest(str(data.get("token", "")).encode(), jeton().encode()):
            if not hasattr(shared, "EXTENSIONS_AUTH"):
                shared.EXTENSIONS_AUTH = set()
            shared.EXTENSIONS_AUTH.add(websocket)
            await websocket.send(json.dumps({"type": "extension_ok"}))
            print("[WEB] Extension navigateur authentifiée.")
        else:
            print("[WEB] ⛔ Extension refusée : jeton invalide.")
            await websocket.close(code=1008, reason="Jeton invalide")
        return
    if websocket not in _authentifiees():
        return  # non authentifiée : rien n'est pris en compte
    if type_msg == "extension_result":
        attente = _ATTENTES.pop(str(data.get("id", "")), None)
        if attente and not attente.done():
            attente.set_result((bool(data.get("ok")), data.get("data")))


def deconnecter(websocket):
    _authentifiees().discard(websocket)


def extension_connectee():
    return bool(_authentifiees())


async def diffuser(message):
    """Envoie un message aux extensions authentifiées (jamais aux autres)."""
    texte = message if isinstance(message, str) else json.dumps(message, ensure_ascii=False)
    if _authentifiees():
        await asyncio.gather(*[ws.send(texte) for ws in list(_authentifiees())], return_exceptions=True)


async def appeler_extension(cmd, timeout=6.0, **params):
    """Demande une commande à l'extension et attend sa réponse : (ok, données)."""
    if not extension_connectee():
        return False, "extension non connectée"
    identifiant = uuid.uuid4().hex
    attente = asyncio.get_running_loop().create_future()
    _ATTENTES[identifiant] = attente
    await diffuser({"action": "ext_cmd", "id": identifiant, "cmd": cmd, "params": params})
    try:
        return await asyncio.wait_for(attente, timeout)
    except asyncio.TimeoutError:
        return False, "pas de réponse du navigateur"
    finally:
        _ATTENTES.pop(identifiant, None)
