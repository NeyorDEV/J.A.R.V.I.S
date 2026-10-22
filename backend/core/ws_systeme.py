"""Messages WebSocket système : coffre-fort, courses, désinstallation, fichiers, Winget, position."""

import asyncio
import json
import os

import core.shared as shared
from core.confirmation import demander_confirmation
from core.micro import _lire_config
from core.web_bridge import demarrer_tache_fond
from module.weather_music_service import (
    actualiser_position_reelle, broadcast_weather_stats_once, update_client_city,
)
from module.winget_manager import inventorier_mises_a_jour, lancer_mise_a_jour_winget
from plugins.list_manager import _relire_listes, _ecrire_listes


# Racine autorisée pour les lectures/écritures de fichiers demandées par l'interface.
_RACINE_PROJET = shared.RACINE_PROJET


def _chemin_projet_valide(chemin: str):
    """Résout `chemin` et vérifie qu'il reste DANS le dossier du projet.

    Retourne le chemin absolu si c'est le cas, sinon None. Sans ce garde-fou,
    un client pouvait lire n'importe quel fichier de la machine (« ../../.env »,
    « C:\\Users\\...\\ »), ou en écraser un — y compris main.py lui-même.
    """
    if not chemin or not isinstance(chemin, str):
        return None
    try:
        absolu = os.path.abspath(os.path.join(_RACINE_PROJET, chemin))
        if os.path.commonpath([absolu, _RACINE_PROJET]) != _RACINE_PROJET:
            return None
        return absolu
    except Exception:
        return None


async def ws_vault(websocket, data):
    """Messages WS du coffre-fort chiffré (déverrouillage, verrouillage, ajout, export, suppression)."""
    from module import voice_vault

    async def _diffuser_vault(msg):
        if shared.CONNECTED_CLIENTS:
            await asyncio.gather(*[ws.send(json.dumps(msg)) for ws in shared.CONNECTED_CLIENTS],
                                 return_exceptions=True)

    action_vault = data.get("type")

    if action_vault == "vault_unlock":
        mdp = data.get("password", "")
        deja_configure = voice_vault.is_vault_configured()
        ok = await asyncio.to_thread(voice_vault.unlock_vault, mdp) if mdp else False
        await websocket.send(json.dumps({
            "type": "vault_unlock_result",
            "success": ok,
            "message": "" if ok else voice_vault.dernier_message(),
            "is_unlocked": voice_vault.is_vault_unlocked(),
            "is_configured": voice_vault.is_vault_configured() if deja_configure else True,
            "files": voice_vault.list_vault_files() if ok else [],
        }))

    elif action_vault == "vault_lock":
        voice_vault.lock_vault()
        await _diffuser_vault({"type": "vault_lock_result", "is_unlocked": False})

    elif action_vault == "vault_add_file":
        # Le chemin vient du sélecteur de fichier natif du navigateur
        # (input[type=file].path côté Electron/webview) : on ne le
        # confine pas à un dossier — l'utilisateur choisit lui-même
        # le fichier via une boîte de dialogue système, il n'y a pas
        # de risque de traversée de chemin côté serveur ici.
        chemin_fichier = data.get("file_path", "")
        ok = await asyncio.to_thread(voice_vault.add_file_to_vault, chemin_fichier) if chemin_fichier else False
        # L'original restait en clair à côté de sa copie chiffrée : on propose de le
        # mettre à la corbeille (récupérable).
        if ok and os.path.exists(chemin_fichier) and await demander_confirmation(
                websocket, f"Fichier chiffré dans le coffre. Mettre l'original « {os.path.basename(chemin_fichier)} » à la corbeille ?"):
            try:
                from send2trash import send2trash
                await asyncio.to_thread(send2trash, chemin_fichier)
            except Exception as e:
                print(f"[VOICE VAULT] Original non déplacé à la corbeille : {e}")
        await _diffuser_vault({
            "type": "vault_file_added",
            "success": ok,
            "is_unlocked": voice_vault.is_vault_unlocked(),
            "is_configured": True,
            "files": voice_vault.list_vault_files(),
        })

    elif action_vault == "vault_export_file":
        nom_fichier = data.get("filename", "")
        from core.dossiers import dossier_connu
        dossier_telechargements = dossier_connu("telechargements")
        chemin_final = ""
        if nom_fichier:
            chemin_final = await asyncio.to_thread(
                voice_vault.export_file_from_vault, nom_fichier, dossier_telechargements
            )
        await websocket.send(json.dumps({
            "type": "vault_export_result",
            "success": bool(chemin_final),
            "filename": nom_fichier,
            "path": chemin_final,
        }))

    elif action_vault == "vault_delete_file":
        nom_fichier = data.get("filename", "")
        ok = False
        if nom_fichier and await demander_confirmation(websocket, f"Supprimer définitivement {nom_fichier} du coffre-fort ?"):
            ok = await asyncio.to_thread(voice_vault.delete_file_from_vault, nom_fichier)
        await _diffuser_vault({
            "type": "vault_file_deleted",
            "success": ok,
            "is_unlocked": voice_vault.is_vault_unlocked(),
            "is_configured": True,
            "files": voice_vault.list_vault_files(),
        })


async def ws_update_shopping_list(websocket, data):
    """Message WS « update_shopping_list » : enregistre et rediffuse la liste de courses."""
    items = data.get("items", [])
    listes = _relire_listes()
    listes["courses"] = items
    _ecrire_listes(listes)
    msg = json.dumps({"type": "shopping_list", "items": items})
    if shared.CONNECTED_CLIENTS:
        await asyncio.gather(*[ws.send(msg) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True)


async def ws_uninstall_program(websocket, data):
    """Message WS « uninstall_program » : désinstallation (avec confirmation) puis scan des résidus."""
    from module.uninstaller_helper import executer_desinstallation, chercher_traces_fichiers, chercher_traces_registre
    app_name = data.get("name", "")
    publisher = data.get("publisher", "")
    install_location = data.get("install_location", "")
    uninstall_string = data.get("uninstall_string", "")

    if not await demander_confirmation(websocket, f"Désinstaller {app_name} ?"):
        await websocket.send(json.dumps({
            "type": "uninstall_complete",
            "app_name": app_name,
            "success": False,
            "cancelled": True,
            "leftovers": []
        }))
        return

    print(f"[UNINSTALLER] Désinstallation en cours : {app_name}...")
    await websocket.send(json.dumps({
        "type": "uninstall_progress",
        "status": "started",
        "message": f"Démarrage du désinstallateur de {app_name}..."
    }))
    success, msg_un = await asyncio.to_thread(executer_desinstallation, uninstall_string, app_name)
    if not success:
        # Désinstallation annulée ou ratée : pas de recherche de « résidus » d'un
        # programme encore installé (on proposerait de supprimer ses vrais fichiers).
        print(f"[UNINSTALLER] {msg_un}")
        await websocket.send(json.dumps({
            "type": "uninstall_complete",
            "app_name": app_name,
            "success": False,
            "message": msg_un,
            "leftovers": []
        }))
        return
    await websocket.send(json.dumps({
        "type": "uninstall_progress",
        "status": "scanning",
        "message": f"Désinstallation faite. Recherche des traces restantes de {app_name}..."
    }))
    leftovers_files = await asyncio.to_thread(chercher_traces_fichiers, app_name, publisher, install_location)
    leftovers_reg = await asyncio.to_thread(chercher_traces_registre, app_name, publisher)
    all_leftovers = leftovers_files + leftovers_reg
    print(f"[UNINSTALLER] Scan fini, {len(all_leftovers)} traces trouvées.")
    await websocket.send(json.dumps({
        "type": "uninstall_complete",
        "app_name": app_name,
        "success": success,
        "leftovers": all_leftovers
    }))


async def ws_clean_leftovers(websocket, data):
    """Message WS « clean_leftovers » : suppression (avec confirmation) des résidus de désinstallation."""
    from module.uninstaller_helper import effacer_trace
    items_to_clean = data.get("items", [])

    if items_to_clean and not await demander_confirmation(websocket, f"Supprimer définitivement {len(items_to_clean)} traces résiduelles ?"):
        await websocket.send(json.dumps({
            "type": "clean_complete",
            "cleaned_count": 0,
            "total_count": len(items_to_clean),
            "cancelled": True,
            "errors": []
        }))
        return

    cleaned_count = 0
    errors = []
    print(f"[UNINSTALLER] Nettoyage de {len(items_to_clean)} traces...")
    for item in items_to_clean:
        success_cl, msg_cl = effacer_trace(item)
        if success_cl:
            cleaned_count += 1
        else:
            errors.append(f"{item.get('path')} : {msg_cl}")
    await websocket.send(json.dumps({
        "type": "clean_complete",
        "cleaned_count": cleaned_count,
        "total_count": len(items_to_clean),
        "errors": errors
    }))


async def ws_fichier(websocket, data):
    """Messages WS « read_file » / « write_file » : lecture/écriture confinées au dossier du projet."""
    action_type = data.get("action") or data.get("type")
    filepath = data.get("filepath", "")
    # Confinement obligatoire au dossier du projet (cf. _chemin_projet_valide)
    chemin_sur = _chemin_projet_valide(filepath)
    if chemin_sur is None:
        print(f"[WEB] ⛔ Accès fichier refusé (hors projet) : {filepath!r}")
        await websocket.send(json.dumps({
            "action": "file_content" if action_type == "read_file" else "file_saved",
            "type": "file_content" if action_type == "read_file" else "file_saved",
            "filepath": filepath,
            "success": False,
            "error": "Chemin refusé : en dehors du dossier du projet.",
            "content": "// Accès refusé : ce fichier est en dehors du dossier JARVIS."
        }))
    elif action_type == "read_file":
        content = ""
        try:
            if os.path.exists(chemin_sur):
                with open(chemin_sur, "r", encoding="utf-8", errors="ignore") as f_in:
                    content = f_in.read()
            else:
                content = f"// Fichier introuvable sur le disque : {filepath}"
        except Exception as ex_rf:
            content = f"// Erreur lors de la lecture : {ex_rf}"
        await websocket.send(json.dumps({
            "action": "file_content",
            "type": "file_content",
            "filepath": filepath,
            "chemin_absolu": chemin_sur,
            "content": content
        }))
    elif action_type == "write_file":
        content = data.get("content", "")
        try:
            dossier = os.path.dirname(chemin_sur)
            if dossier:
                os.makedirs(dossier, exist_ok=True)
            with open(chemin_sur, "w", encoding="utf-8") as f_out:
                f_out.write(content)
            await websocket.send(json.dumps({
                "action": "file_saved",
                "type": "file_saved",
                "filepath": filepath,
                "success": True
            }))
        except Exception as ex_wf:
            await websocket.send(json.dumps({
                "action": "file_saved",
                "type": "file_saved",
                "filepath": filepath,
                "success": False,
                "error": str(ex_wf)
            }))


async def ws_get_winget_upgrades(websocket, data):
    """Message WS « get_winget_upgrades » : liste les mises à jour Winget disponibles."""
    print("[WINGET] Recherche des mises à jour...")
    upgrades = await asyncio.to_thread(inventorier_mises_a_jour)
    await websocket.send(json.dumps({
        "type": "winget_upgrades",
        "upgrades": upgrades
    }))


async def ws_run_winget_upgrade(websocket, data):
    """Message WS « run_winget_upgrade » : lance les mises à jour Winget en arrière-plan."""
    ids = data.get("ids", [])
    run_all = data.get("all", False)
    loop = asyncio.get_running_loop()
    if run_all:
        print("[WINGET] Mise à jour de tout en cours...")
        args = ["winget", "upgrade", "--all", "--accept-package-agreements", "--accept-source-agreements", "--include-unknown"]
        demarrer_tache_fond(asyncio.to_thread(lancer_mise_a_jour_winget, args, loop, websocket))
    elif ids:
        async def executer_sequence():
            for idx, pkg_id in enumerate(ids):
                print(f"[WINGET] Mise à jour de {pkg_id} ({idx+1}/{len(ids)})...")
                args = ["winget", "upgrade", "--id", pkg_id, "--accept-package-agreements", "--accept-source-agreements", "--include-unknown"]
                await asyncio.to_thread(lancer_mise_a_jour_winget, args, loop, websocket, pkg_id)
        demarrer_tache_fond(executer_sequence())


async def ws_set_location(websocket, data):
    """Message WS « set_location » : met à jour la position client puis la météo.

    Priorité : position réelle donnée par Windows (comme « ma position » sur le globe),
    puis position réglée dans la configuration, puis celle du navigateur."""
    if await actualiser_position_reelle():
        await broadcast_weather_stats_once()
        return
    _cfg = _lire_config()
    if _cfg.get("latitude") is not None and _cfg.get("longitude") is not None:
        shared.CLIENT_LOCATION["lat"] = _cfg["latitude"]
        shared.CLIENT_LOCATION["lon"] = _cfg["longitude"]
    else:
        shared.CLIENT_LOCATION["lat"] = data.get("lat")
        shared.CLIENT_LOCATION["lon"] = data.get("lon")
    asyncio.ensure_future(update_client_city())
    # Forcer un broadcast immédiat après mise à jour
    asyncio.ensure_future(asyncio.sleep(1)).add_done_callback(lambda _: asyncio.ensure_future(broadcast_weather_stats_once()))


async def ws_select_folder(websocket, data):
    """Message WS « select_folder » (bouton Parcourir de l'atelier de création de site) :
    ouvre le sélecteur de dossier de Windows et renvoie le chemin choisi. Le bouton
    n'avait aucun gestionnaire côté backend et ne faisait donc rien."""
    def _choisir():
        import tkinter as tk
        from tkinter import filedialog
        racine = tk.Tk()
        racine.withdraw()
        racine.attributes("-topmost", True)
        try:
            return filedialog.askdirectory(title="Choisissez le dossier du projet") or ""
        finally:
            racine.destroy()

    dossier = await asyncio.to_thread(_choisir)
    if dossier:
        await websocket.send(json.dumps({"type": "folder_selected", "folder": os.path.normpath(dossier)}))
