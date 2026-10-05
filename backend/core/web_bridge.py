"""Pont vers le HUD : envoi de messages WebSocket au frontend depuis n'importe quel thread."""

import asyncio
import builtins
import json
import time
import uuid

import requests

import core.shared as shared


def lancer_tache_arriere_plan(coro):
    task = asyncio.create_task(coro)
    shared.BACKGROUND_TASKS.add(task)
    task.add_done_callback(shared.BACKGROUND_TASKS.discard)
    return task


def _safe_ws_send(msg):
    if not shared.CONNECTED_CLIENTS or shared.WS_LOOP is None: 
        return
    async def _send():
        if shared.CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
    try:
        asyncio.run_coroutine_threadsafe(_send(), shared.WS_LOOP)
    except Exception as e:
        print(f"[DEBUG WS] Erreur d'envoi: {e}")


def send_web_broadcast_sync(payload: dict):
    """Envoie un message WebSocket (dict) depuis n'importe quel thread — utilisé par module.competences."""
    import json as _json
    _safe_ws_send(_json.dumps(payload))


async def envoyer_image_web(url, prompt):
    """Envoie l'URL de l'image générée au frontend via WebSocket."""
    msg = json.dumps({
        "action": "display_image",
        "url": url,
        "prompt": prompt,
        "timestamp": time.time()
    })
    _safe_ws_send(msg)


async def send_web_state(state):
    _safe_ws_send(json.dumps({"action": "set_state", "state": state}))


async def send_web_text(text):
    _safe_ws_send(json.dumps({"action": "jarvis_text", "text": text}))


async def send_web_volume(volume):
    _safe_ws_send(json.dumps({"action": "set_volume", "volume": round(volume, 3)}))


async def send_web_action(action, selector=None, text=None, class_name=None):
    payload = {"type": "dom_action", "action": action}
    if selector:
        payload["selector"] = selector
    if text:
        payload["text"] = text
    if class_name:
        payload["class_name"] = class_name
    _safe_ws_send(json.dumps(payload))


async def send_web_text_interim(text):
    """Envoie la transcription partielle (en cours de parole) au HUD."""
    _safe_ws_send(json.dumps({"action": "interim_speech", "text": text}))


async def send_action_to_frontend(action):
    """Envoie une action WebSocket brute au frontend."""
    _safe_ws_send(json.dumps(action))


def est_connecte_internet():
    """Détecte de manière ultra-rapide si une connexion internet est active et fonctionnelle."""
    import socket
    try:
        # Tenter d'ouvrir une connexion TCP rapide vers le DNS public de Google
        socket.create_connection(("8.8.8.8", 53), timeout=0.8)
        return True
    except Exception:
        try:
            # Fallback vers Cloudflare DNS
            socket.create_connection(("1.1.1.1", 53), timeout=0.8)
            return True
        except Exception:
            return False


async def send_globe_command(**kwargs):
    payload = {"action": "jarvis_globe"}
    payload.update(kwargs)
    _safe_ws_send(json.dumps(payload))


async def geocode_lieu(nom_lieu: str):
    """Géocode un nom de lieu via Nominatim (OpenStreetMap) — gratuit, sans clé API."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(nom_lieu)}&format=json&limit=1"
        headers = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}
        resp = await asyncio.wait_for(
            asyncio.to_thread(requests.get, url, headers=headers, timeout=6),
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0].get("display_name", nom_lieu)
    except Exception as e:
        print(f"[GLOBE] Erreur géocodage '{nom_lieu}': {e}")
    return None, None, nom_lieu


async def request_screen_capture():
    """Demande une capture d'écran au frontend via WebSocket."""
    if not shared.CONNECTED_CLIENTS:
        return None
    
    req_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    shared.PENDING_SCREEN_CAPTURES[req_id] = fut
    
    print(f"[VISION] Envoi requete capture ID: {req_id}")
    msg = json.dumps({"action": "request_screen_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS])
    
    try:
        # Timeout de 15 secondes car l'utilisateur doit parfois accepter le partage
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[VISION] Erreur ou timeout capture : {e}")
        shared.PENDING_SCREEN_CAPTURES.pop(req_id, None)
        return None


async def envoyer_carte_contextuelle(titre: str, texte: str, type_carte: str = "info", icon: str = "◈", duree: int = 10000):
    """Envoie une carte dynamique au HUD via WebSocket."""
    if shared.CONNECTED_CLIENTS:
        msg = json.dumps({
            "action": "ctx_card",
            "title": titre,
            "text": texte,
            "type": type_carte,
            "icon": icon,
            "duration": duree
        })
        await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


async def diffuser_echecs(data):
    if shared.CONNECTED_CLIENTS:
        msg = json.dumps(data)
        await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


builtins.envoyer_image_web = envoyer_image_web
builtins.send_action_to_frontend = send_action_to_frontend
builtins.send_web_state = send_web_state
builtins.send_web_text = send_web_text
builtins.send_web_volume = send_web_volume
builtins.send_web_action = send_web_action
builtins.send_web_text_interim = send_web_text_interim
builtins.est_connecte_internet = est_connecte_internet
builtins.geocode_lieu = geocode_lieu
builtins.request_screen_capture = request_screen_capture
builtins.send_globe_command = send_globe_command
builtins.envoyer_carte_contextuelle = envoyer_carte_contextuelle


# Les compétences générées par l'IA diffusent leur animation de compilation au HUD
import module.competences as _competences_mod
_competences_mod.send_web_broadcast_sync = send_web_broadcast_sync
