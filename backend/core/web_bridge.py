"""Pont vers le HUD : envoi de messages WebSocket au frontend depuis n'importe quel thread."""

import asyncio
import builtins
import json
import time
import uuid

import requests

import core.shared as shared


def demarrer_tache_fond(coro):
    task = asyncio.create_task(coro)
    shared.BACKGROUND_TASKS.add(task)
    task.add_done_callback(shared.BACKGROUND_TASKS.discard)
    return task


def _safe_ws_send(msg):
    if not shared.CONNECTED_CLIENTS or shared.WS_LOOP is None: 
        return
    async def _emettre():
        if shared.CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
    try:
        asyncio.run_coroutine_threadsafe(_emettre(), shared.WS_LOOP)
    except Exception as e:
        print(f"[DEBUG WS] Erreur d'envoi: {e}")


def diffuser_web_sync(payload: dict):
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


async def envoyer_etat_hud(state):
    shared.ETAT_HUD = state  # repris par le bandeau de la console (core/console_ui)
    _safe_ws_send(json.dumps({"action": "set_state", "state": state}))


async def envoyer_texte_hud(text):
    _safe_ws_send(json.dumps({"action": "jarvis_text", "text": text}))


async def envoyer_volume_hud(volume):
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


async def envoyer_commande_globe(**kwargs):
    payload = {"action": "jarvis_globe"}
    payload.update(kwargs)
    _safe_ws_send(json.dumps(payload))


async def geolocaliser_lieu(nom_lieu: str):
    """Convertit un nom de lieu en coordonnées avec Nominatim (OpenStreetMap), gratuit et sans clé."""
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


async def geocode_lieu_detaille(nom_lieu: str):
    """Géocode un lieu via Nominatim et renvoie {lat, lon, nom, importance, rang} ou None.

    « importance » (0 à 1) permet d'écarter les faux lieux : un lieu-dit, une rue, un
    commerce ou un bâtiment qui porte le nom demandé (« La Terre », « Ma position »...)
    sont sous 0,2, alors que les vrais lieux, même de petits villages, dépassent 0,5.
    « rang » (place_rank) : 2-4 continent/pays, 5-12 région, 13+ ville et plus précis."""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(nom_lieu)}&format=jsonv2&limit=1"
        headers = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}
        resp = await asyncio.wait_for(
            asyncio.to_thread(requests.get, url, headers=headers, timeout=6),
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                d = data[0]
                return {"lat": float(d["lat"]), "lon": float(d["lon"]), "nom": d.get("display_name", nom_lieu),
                        "importance": float(d.get("importance") or 0), "rang": int(d.get("place_rank") or 30)}
    except Exception as e:
        print(f"[GLOBE] Erreur géocodage '{nom_lieu}': {e}")
    return None


async def nom_lieu_inverse(lat: float, lon: float):
    """Nom de la commune (ou du lieu le plus proche) pour des coordonnées, via Nominatim, ou None."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&zoom=10&format=jsonv2"
        headers = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)", "Accept-Language": "fr"}
        resp = await asyncio.wait_for(
            asyncio.to_thread(requests.get, url, headers=headers, timeout=6),
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            adresse = data.get("address", {})
            for cle in ("city", "town", "village", "municipality", "county", "state"):
                if adresse.get(cle):
                    return adresse[cle]
            return data.get("name") or None
    except Exception as e:
        print(f"[GLOBE] Erreur géocodage inverse ({lat}, {lon}) : {e}")
    return None


async def capturer_ecran_hud():
    """Réclame au HUD une capture d'écran par WebSocket."""
    if not shared.CONNECTED_CLIENTS:
        return None
    
    req_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    fut = loop.create_future()
    shared.PENDING_SCREEN_CAPTURES[req_id] = fut
    
    print(f"[VISION] Demande de capture envoyée, id {req_id}")
    msg = json.dumps({"action": "request_screen_capture", "id": req_id})
    await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS])
    
    try:
        # Timeout de 15 secondes car l'utilisateur doit parfois accepter le partage
        img_b64 = await asyncio.wait_for(fut, timeout=15.0)
        return img_b64
    except Exception as e:
        print(f"[VISION] Capture en échec ou trop lente : {e}")
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
builtins.envoyer_etat_hud = envoyer_etat_hud
builtins.envoyer_texte_hud = envoyer_texte_hud
builtins.envoyer_volume_hud = envoyer_volume_hud
builtins.send_web_action = send_web_action
builtins.send_web_text_interim = send_web_text_interim
builtins.est_connecte_internet = est_connecte_internet
builtins.geolocaliser_lieu = geolocaliser_lieu
builtins.capturer_ecran_hud = capturer_ecran_hud
builtins.envoyer_commande_globe = envoyer_commande_globe
builtins.envoyer_carte_contextuelle = envoyer_carte_contextuelle


# Les compétences générées par l'IA diffusent leur animation de compilation au HUD
import module.competences as _competences_mod
_competences_mod.diffuser_web_sync = diffuser_web_sync
