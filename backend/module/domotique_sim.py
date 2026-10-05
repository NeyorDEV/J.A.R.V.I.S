"""Carte domotique 3D : simulation des états, métadonnées HomePod, routage audio."""

import asyncio
import json

import controller.homepod_controller as homepod_controller
import core.shared as shared
from core.speech import parler


async def update_homepods_metadata_loop():
    """Boucle d'arrière-plan pour rafraîchir les métadonnées de musique des HomePods."""
    while True:
        try:
            # Séjour (salon)
            state_sejour = shared.SIMULATED_DOMOTIC_STATES.get("media_player.homepod_salon")
            if state_sejour != "paused":
                track = await homepod_controller.get_playing_metadata("Séjour")
                shared.SIMULATED_DOMOTIC_STATES["media_player.homepod_salon"] = track or "Musique en cours (Séjour)"

            # Salle de jeux (chambre)
            state_jeux = shared.SIMULATED_DOMOTIC_STATES.get("media_player.homepod_chambre")
            if state_jeux != "paused":
                track = await homepod_controller.get_playing_metadata("Salle de jeux")
                shared.SIMULATED_DOMOTIC_STATES["media_player.homepod_chambre"] = track or "Musique en cours (Salle de jeux)"
        except Exception as e:
            pass
        await asyncio.sleep(8)


async def broadcast_ha_stats():
    """Diffuse périodiquement les états domotiques de simulation."""
    import random
    while True:
        try:
            if shared.CONNECTED_CLIENTS:
                # Simuler de légères variations de température (+- 0.05°C)
                for room in ["salon", "cuisine", "parents", "veranda", "garage", "couloir", "chambre_1", "chambre_2", "sdb"]:
                    key = f"temp.{room}"
                    shared.SIMULATED_DOMOTIC_STATES[key] += random.choice([-0.05, 0.0, 0.05])
                    shared.SIMULATED_DOMOTIC_STATES[key] = round(max(10.0, min(30.0, shared.SIMULATED_DOMOTIC_STATES[key])), 2)
                
                msg = json.dumps({
                    "action": "domotic_map_update",
                    "states": {k: {"state": v} for k, v in shared.SIMULATED_DOMOTIC_STATES.items()}
                })
                # Broadcast
                await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
        except Exception as e:
            print(f"[DOMOTIC SIM] Erreur broadcast: {e}")
        await asyncio.sleep(6)


async def handle_domotic_sim_ws(data, websocket):
    """Gère les messages WebSocket spatial_action domotique."""
    action = data.get("action")
    if action == "domotic_list":
        # Envoyer l'état complet actuel
        msg = json.dumps({
            "action": "domotic_map_update",
            "states": {k: {"state": v} for k, v in shared.SIMULATED_DOMOTIC_STATES.items()}
        })
        await websocket.send(msg)
    elif action == "domotic_toggle":
        entity_id = data.get("entity_id")
        if entity_id in shared.SIMULATED_DOMOTIC_STATES:
            curr = shared.SIMULATED_DOMOTIC_STATES[entity_id]
            new_val = "off" if curr == "on" else "on"
            shared.SIMULATED_DOMOTIC_STATES[entity_id] = new_val
            print(f"[DOMOTIC SIM] Toggle {entity_id} -> {new_val}")
            
            # Diffuser immédiatement la mise à jour à tous les clients
            msg = json.dumps({
                "action": "domotic_map_update",
                "states": {k: {"state": v} for k, v in shared.SIMULATED_DOMOTIC_STATES.items()}
            })
            await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


async def domotic_route_audio(source: str, destination: str):
    """
    Déplace la musique d'une pièce à une autre.
    """
    print(f"[DOMOTIC AUDIO] Routage de '{source}' vers '{destination}'")
    
    mapping = {
        "salon": {"id": "media_player.homepod_salon", "name": "Séjour"},
        "sejour": {"id": "media_player.homepod_salon", "name": "Séjour"},
        "séjour": {"id": "media_player.homepod_salon", "name": "Séjour"},
        "chambre": {"id": "media_player.homepod_chambre", "name": "Salle de jeux"},
        "ma chambre": {"id": "media_player.homepod_chambre", "name": "Salle de jeux"},
        "salle de jeux": {"id": "media_player.homepod_chambre", "name": "Salle de jeux"},
        "jeux": {"id": "media_player.homepod_chambre", "name": "Salle de jeux"},
    }
    
    src_info = mapping.get(source.lower(), {"id": "media_player.homepod_salon", "name": "Séjour"})
    dest_info = mapping.get(destination.lower(), {"id": "media_player.homepod_chambre", "name": "Salle de jeux"})
    
    async def run_pyatv_actions():
        try:
            await homepod_controller.send_command("pause", identifier=src_info["name"])
            await asyncio.sleep(0.5)
            await homepod_controller.send_command("play", identifier=dest_info["name"])
        except Exception as e:
            print(f"[DOMOTIC AUDIO] Erreur pyatv : {e}")

    asyncio.create_task(run_pyatv_actions())
    
    src_entity = src_info["id"]
    dest_entity = dest_info["id"]
    if src_entity in shared.SIMULATED_DOMOTIC_STATES:
        shared.SIMULATED_DOMOTIC_STATES[src_entity] = "paused"
    if dest_entity in shared.SIMULATED_DOMOTIC_STATES:
        shared.SIMULATED_DOMOTIC_STATES[dest_entity] = "playing"
        
    msg_states = json.dumps({
        "action": "domotic_map_update",
        "states": {k: {"state": v} for k, v in shared.SIMULATED_DOMOTIC_STATES.items()}
    })
    await asyncio.gather(*[ws.send(msg_states) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
    
    msg_anim = json.dumps({
        "action": "domotic_audio_route_animation",
        "source": source,
        "destination": destination
    })
    await asyncio.gather(*[ws.send(msg_anim) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
    
    parler(f"C'est fait, je déplace la musique du {source} vers {destination}.")
