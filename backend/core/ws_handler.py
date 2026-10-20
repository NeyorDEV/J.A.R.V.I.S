"""Serveur WebSocket : contrôle d'origine et aiguillage des messages du frontend."""

import asyncio
import json
import re
import unicodedata

import chess

import core.shared as shared
import core.speech as speech
from controller.actions_pc import recenser_applications
from core.confirmation import resoudre_confirmation
from core.etat_parole import get_is_speaking, set_stop_parler
from core.speech import parler
from core.traitement import gerer_reponse_ia
from core.web_bridge import diffuser_echecs, demarrer_tache_fond, envoyer_etat_hud
from core.ws_etat_systeme import ws_get_system_status, ws_system_test
from core.ws_reglages import ws_get_settings, ws_update_settings
from core.ws_securite import (
    ws_av_threat_action, ws_block_ip, ws_clear_cache, ws_get_blocked_ips, ws_unblock_ip,
)
from core.ws_systeme import (
    ws_clean_leftovers, ws_fichier, ws_get_winget_upgrades, ws_run_winget_upgrade,
    ws_select_folder, ws_set_location, ws_uninstall_program, ws_update_shopping_list, ws_vault,
)
from module.chess_manager import ChessGame
from module.cortex_service import handle_cortex_ws
from module.domotique_sim import handle_domotic_sim_ws
from module.meteo_domotique import traiter_message_ws_ha
from module.weather_music_service import broadcast_weather_stats_once
from plugins.list_manager import _relire_listes


# ── SÉCURITÉ WEBSOCKET ────────────────────────────────────────────────────────
# Les WebSockets ne sont PAS soumis à la politique CORS : n'importe quel site web
# visité dans un navigateur peut ouvrir ws://localhost:8765 et piloter JARVIS.
# On filtre donc l'en-tête Origin : les clients légitimes sont soit natifs
# (pywebview : pas d'Origin), soit servis en local (Vite).
# Tout le reste — c'est-à-dire un vrai site distant — est refusé.
def _origine_autorisee(websocket) -> bool:
    try:
        # websockets >= 12 expose request.headers ; les versions antérieures request_headers
        entetes = getattr(getattr(websocket, "request", None), "headers", None)
        if entetes is None:
            entetes = getattr(websocket, "request_headers", None)
        origine = entetes.get("Origin") if entetes else None
    except Exception:
        return True  # en cas de doute on n'enferme pas l'utilisateur dehors

    if not origine:
        return True  # client natif (pywebview) : pas d'Origin

    o = origine.lower().strip()
    if o == "null" or o.startswith("file://"):
        return True
    # Extension JARVIS (Chrome / Opera) : son origine « chrome-extension://<id> » était
    # refusée, si bien qu'elle ne se connectait jamais.
    if o.startswith("chrome-extension://"):
        return True
    # Hôtes locaux uniquement (le WebSocket n'écoute plus que sur localhost)
    import re as _re_o
    return bool(_re_o.match(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$", o))


def _origine_extension(websocket) -> bool:
    try:
        entetes = getattr(getattr(websocket, "request", None), "headers", None) or getattr(websocket, "request_headers", None)
        return bool(entetes) and (entetes.get("Origin") or "").lower().startswith("chrome-extension://")
    except Exception:
        return False


def _en_tache_de_fond(coro):
    """Lance un handler sans bloquer la lecture des messages suivants de la connexion.

    Indispensable pour les actions qui attendent une confirmation (core/confirmation.py) :
    attendues en ligne, elles bloquaient la boucle `async for` — le message
    « confirm_response » envoyé par le clic HUD sur cette même connexion n'était lu
    qu'après le délai d'expiration, et l'action était donc toujours annulée.
    """
    async def _executer():
        try:
            await coro
        except Exception as e:
            print(f"[WEB] Message mal traité : {e}")
    return demarrer_tache_fond(_executer())


async def gerer_connexion_ws(websocket):
    if not _origine_autorisee(websocket):
        print("[WEB] ⛔ Connexion refusée : origine non autorisée (site web distant ?).")
        try:
            await websocket.close(code=1008, reason="Origine non autorisee")
        except Exception:
            pass
        return

    shared.CONNECTED_CLIENTS.add(websocket)
    if _origine_extension(websocket):
        # L'extension n'est pas un HUD : elle ne doit pas empêcher l'arrêt automatique
        # quand l'interface est fermée (core/lancement._attendre_hud).
        shared.CLIENTS_EXTENSION.add(websocket)
        print("[WEB] Extension navigateur connectée.")
    else:
        shared.interface_deja_connectee = True
        print(f"[WEB] HUD connecté (clients : {len(shared.CONNECTED_CLIENTS)})")
    
    # Force le broadcast immédiat de tous les widgets
    asyncio.create_task(broadcast_weather_stats_once())
    
    # Envoi d'un état initial pour la musique
    asyncio.create_task(websocket.send(json.dumps({
        "action": "music_update", 
        "data": {"status": "Stopped", "title": "DEEZER_SYNC...", "artist": "INITIALISATION"}
    })))
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                if data.get("type") == "stop_audio":
                    shared.STOP_PARLER = True
                    set_stop_parler(True)
                    speech.vider_files()
                    print("[WEB] Signal STOP audio recu")
                elif data.get("type") == "toggle_mic":
                    shared.MIC_MUTED = not shared.MIC_MUTED
                    await websocket.send(json.dumps({"type": "mic_state", "muted": shared.MIC_MUTED}))
                    if shared.MIC_MUTED:
                        await envoyer_etat_hud("idle")
                    print(f"[WEB] Micro {'COUPE' if shared.MIC_MUTED else 'REACTIF'}")
                elif data.get("type") == "globe_state":
                    shared.GLOBE_VISIBLE = bool(data.get("visible"))
                elif data.get("type") == "toggle_fullscreen":
                    if hasattr(shared, "_WEBVIEW_WINDOW") and shared._WEBVIEW_WINDOW:
                        shared._WEBVIEW_WINDOW.toggle_fullscreen()
                        print("[WEB] Plein écran pywebview basculé")
                elif data.get("type") == "get_system_status":
                    await ws_get_system_status(websocket, data)
                elif data.get("type") == "system_test":
                    _en_tache_de_fond(ws_system_test(websocket, data))  # requêtes réseau : sans bloquer la lecture
                elif data.get("type") == "get_settings":
                    await ws_get_settings(websocket, data)
                elif data.get("type") == "update_settings":
                    await ws_update_settings(websocket, data)
                # ── Voice Vault (coffre-fort chiffré) ────────────────────────
                # Le module backend/module/voice_vault.py existe déjà et gère le
                # chiffrement AES (Fernet + PBKDF2). Seule la commande vocale
                # ("coffre fort") était câblée ; les boutons du panneau HUD
                # (#vault-unlock-btn, #vault-lock-btn, #vault-add-btn, export,
                # suppression) envoyaient ces types de message sans qu'aucun
                elif data.get("type") == "confirm_response":
                    resoudre_confirmation(data.get("id", ""), bool(data.get("confirmed")))

                # handler n'existe ici : ils ne faisaient donc rien.
                elif data.get("type") == "vault_delete_file":
                    _en_tache_de_fond(ws_vault(websocket, data))  # attend une confirmation
                elif data.get("type") == "vault_add_file":
                    _en_tache_de_fond(ws_vault(websocket, data))  # propose ensuite de jeter l'original
                elif data.get("type") in ("vault_unlock", "vault_lock", "vault_export_file"):
                    await ws_vault(websocket, data)

                # ── Shopping List ──────────────────────────────────────────
                elif data.get("type") == "get_shopping_list":
                    listes = _relire_listes()
                    await websocket.send(json.dumps({"type": "shopping_list", "items": listes.get("courses", [])}))
                elif data.get("type") == "update_shopping_list":
                    await ws_update_shopping_list(websocket, data)
                elif data.get("type") == "get_installed_programs":
                    from module.uninstaller_helper import inventaire_logiciels
                    programs = inventaire_logiciels()
                    await websocket.send(json.dumps({"type": "installed_programs", "programs": programs}))
                elif data.get("type") == "uninstall_program":
                    _en_tache_de_fond(ws_uninstall_program(websocket, data))  # attend une confirmation
                elif data.get("type") == "clean_leftovers":
                    _en_tache_de_fond(ws_clean_leftovers(websocket, data))  # attend une confirmation
                elif data.get("type") in ["read_file", "write_file"] or data.get("action") in ["read_file", "write_file"]:
                    await ws_fichier(websocket, data)
                elif data.get("type") == "get_winget_upgrades":
                    await ws_get_winget_upgrades(websocket, data)
                elif data.get("type") == "run_winget_upgrade":
                    await ws_run_winget_upgrade(websocket, data)
                elif data.get("type") in ("ha_get_states", "ha_call_service"):
                    # ── Home Assistant Dashboard ──────────────────────────────
                    await traiter_message_ws_ha(data, websocket, shared.CONNECTED_CLIENTS)
                elif data.get("type") == "block_ip":
                    await ws_block_ip(websocket, data)
                elif data.get("type") == "get_blocked_ips":
                    await ws_get_blocked_ips(websocket, data)
                elif data.get("type") == "unblock_ip":
                    await ws_unblock_ip(websocket, data)
                elif data.get("type") == "user_input":
                    texte = data.get("text", "").strip()
                    if texte:
                        print(f"[HUD] Commande clavier : {texte}")
                        # (shared.is_speaking n'était jamais mis à jour : l'état réel est dans speech)
                        # Ordre d'arrêt court seulement : « arrête le minuteur » est une commande
                        if get_is_speaking() and len(texte.split()) <= 3 and any(word in texte.lower() for word in ["arrete", "arrête", "stop", "tais", "chut", "silence"]):
                            shared.STOP_PARLER = True
                            set_stop_parler(True)
                            speech.vider_files()
                        elif re.search(r"\b(re-?enregistre|enregistre|mets? a jour)\s+ma voix\b",
                                       unicodedata.normalize("NFD", texte.lower()).encode("ascii", "ignore").decode()):
                            # Enrôlement vocal du créateur lancé par la boucle d'écoute (core/ecoute.py)
                            shared.ENROLEMENT_CLAVIER = True
                        else:
                            # Clavier du HUD local (utilisateur physiquement présent) → de confiance
                            asyncio.ensure_future(gerer_reponse_ia(texte, de_confiance=True))
                elif data.get("type") == "screen_frame":
                    req_id = data.get("id")
                    if req_id in shared.PENDING_SCREEN_CAPTURES:
                        fut = shared.PENDING_SCREEN_CAPTURES.pop(req_id)
                        if "error" in data:
                            fut.set_exception(Exception(data["error"]))
                        else:
                            fut.set_result(data["data"])
                    print(f"[VISION] Frame recue pour ID: {req_id}")
                elif data.get("type") == "select_folder":
                    _en_tache_de_fond(ws_select_folder(websocket, data))  # boîte de dialogue : ne bloque pas
                elif data.get("type") == "set_location":
                    _en_tache_de_fond(ws_set_location(websocket, data))  # localisation Windows : quelques secondes
                elif data.get("type") == "spatial_action":
                    action = data.get("action", "")
                    if action.startswith("domotic_"):
                        await handle_domotic_sim_ws(data, websocket)
                    elif action.startswith("cortex_"):
                        await handle_cortex_ws(data, websocket)
                    else:
                        from plugins.spatial_explorer import handle_spatial_ws
                        if action == "delete":
                            _en_tache_de_fond(handle_spatial_ws(data, websocket))  # attend une confirmation
                        else:
                            await handle_spatial_ws(data, websocket)
                elif data.get("type") == "chess_action":
                    action = data.get("action", "")
                    if action == "start":
                        difficulty = data.get("difficulty", "1000")
                        player_color_str = data.get("player_color", "white")
                        use_timer = data.get("use_timer", "no")
                        shared.CHESS_GAME = ChessGame()
                        shared.CHESS_GAME.difficulty = difficulty
                        shared.CHESS_GAME.player_color = chess.WHITE if player_color_str == "white" else chess.BLACK
                        shared.CHESS_GAME_ACTIVE = True
                        state = shared.CHESS_GAME.get_state()
                        await websocket.send(json.dumps({
                            "action": "chess_start",
                            "state": state,
                            "difficulty": difficulty,
                            "player_color": player_color_str,
                            "use_timer": use_timer
                        }))

                        # Si le joueur est Noir, JARVIS est Blanc et doit jouer le premier coup !
                        if shared.CHESS_GAME.player_color == chess.BLACK:
                            async def play_first_move_delayed():
                                await asyncio.sleep(1.2) # Laisser le temps au plateau de pivoter
                                if not shared.CHESS_GAME or not shared.CHESS_GAME_ACTIVE:
                                    return
                                await diffuser_echecs({
                                    "action": "chess_thinking",
                                    "thinking": True
                                })
                                thinking_time = shared.CHESS_GAME.calculate_thinking_time()
                                await asyncio.sleep(thinking_time)
                                if not shared.CHESS_GAME or not shared.CHESS_GAME_ACTIVE:
                                    return
                                j_move, remark, j_state = shared.CHESS_GAME.play_jarvis_move()
                                await diffuser_echecs({
                                    "action": "chess_game_state",
                                    "state": j_state,
                                    "last_move": {
                                        "from": chess.square_name(j_move.from_square),
                                        "to": chess.square_name(j_move.to_square),
                                        "color": "white"
                                    }
                                })
                                parler(remark)
                            asyncio.create_task(play_first_move_delayed())
                    elif action == "stop":
                        shared.CHESS_GAME = None
                        shared.CHESS_GAME_ACTIVE = False
                        await websocket.send(json.dumps({
                            "action": "chess_stop"
                        }))
                    elif action == "reset":
                        shared.CHESS_GAME = None
                        shared.CHESS_GAME_ACTIVE = False
                        # Le frontend a déjà réinitialisé son UI — ne pas renvoyer chess_reset (évite la boucle infinie)
                    elif action == "get_state":
                        if not shared.CHESS_GAME:
                            shared.CHESS_GAME = ChessGame()
                        state = shared.CHESS_GAME.get_state()
                        await websocket.send(json.dumps({
                            "action": "chess_game_state",
                            "state": state
                        }))
                elif data.get("type") == "music_control":

                    act = data.get("action")
                    if act == "toggle":
                        import pyautogui
                        pyautogui.press("playpause")
                    elif act == "next":
                        import pyautogui
                        pyautogui.press("nexttrack")
                    elif act == "prev":
                        import pyautogui
                        pyautogui.press("prevtrack")
                    print(f"[MUSIC] Commande recue : {act}")
                elif data.get("type") == "detect_apps":
                    apps = await asyncio.to_thread(recenser_applications)
                    await websocket.send(json.dumps({"type": "detected_apps", "apps": apps}))
                elif data.get("type") == "av_scan_start":
                    import antivirus_scanner
                    if antivirus_scanner.ACTIVE_SCAN_TASK is None or antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        async def ws_diffuser(m):
                            if shared.CONNECTED_CLIENTS:
                                try:
                                    await asyncio.gather(*[ws.send(json.dumps(m)) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)
                                except Exception:
                                    pass
                        antivirus_scanner.ACTIVE_SCAN_TASK = asyncio.create_task(
                            antivirus_scanner.executer_scan_antivirus(ws_diffuser, parler)
                        )
                        print("[AV] Démarrage de l'analyse antivirus...")
                elif data.get("type") == "av_scan_cancel":
                    import antivirus_scanner
                    if antivirus_scanner.ACTIVE_SCAN_TASK and not antivirus_scanner.ACTIVE_SCAN_TASK.done():
                        antivirus_scanner.ACTIVE_SCAN_TASK.cancel()
                        print("[AV] Analyse antivirus annulée depuis le HUD.")
                elif data.get("type") == "clear_cache":
                    await ws_clear_cache(websocket, data)
                elif data.get("type") == "av_threat_action":
                    _en_tache_de_fond(ws_av_threat_action(websocket, data))  # attend une confirmation
                elif data.get("type") == "av_speak":
                    text = data.get("text")
                    if text:
                        parler(text)   # synchrone (create_task(None) levait une erreur)
            except Exception as e:
                print(f"[WEB] Message mal traité : {e}")
    except Exception:
        pass
    finally:
        shared.CONNECTED_CLIENTS.discard(websocket)
        shared.CLIENTS_EXTENSION.discard(websocket)
        print(f"[WEB] HUD déconnecté (clients : {len(shared.CONNECTED_CLIENTS)})")
