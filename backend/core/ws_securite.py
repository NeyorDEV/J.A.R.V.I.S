"""Messages WebSocket de sécurité : pare-feu (IP bloquées), cache WebView2, actions antivirus."""

import builtins
import json
import os
import threading

import core.shared as shared
from core.interlocuteur import nom_virgule
from core.micro import _lire_config, _ecrire_config
from core.webview_cache import purger_cache_webview


try:
    import webview
    _WEBVIEW_OK = True
except ImportError:
    webview = None
    _WEBVIEW_OK = False


async def ws_block_ip(websocket, data):
    """Message WS « block_ip » : bloque une IP via le pare-feu Windows (entrant + sortant)."""
    import re as _re, subprocess as _sp
    _ip = data.get("ip", "").strip()
    if _re.match(r'^\d{1,3}(\.\d{1,3}){3}$', _ip):
        _rule = f"JARVIS_BLOCK_{_ip.replace('.', '_')}"
        try:
            echecs = []
            for _dir in ("out", "in"):
                _res = _sp.run([
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name={_rule}_{_dir.upper()}", f"dir={_dir}",
                    "action=block", f"remoteip={_ip}", "enable=yes"
                ], capture_output=True, timeout=5)
                if _res.returncode != 0:
                    echecs.append(_dir)
            if echecs:
                # Sans droits administrateur, netsh refuse d'ajouter la règle : on ne
                # l'annonce plus comme bloquée (avant : carte « IP bloquée » quand même).
                print(f"[RADAR] Blocage de {_ip} refusé par netsh (droits administrateur requis ?)")
                await websocket.send(json.dumps({
                    "action": "ctx_card", "type": "alert", "icon": "⚠",
                    "title": "Blocage impossible",
                    "text": f"Windows a refusé d'ajouter la règle pour {_ip} : lancez JARVIS en administrateur."
                }))
                if hasattr(builtins, 'parler'):
                    builtins.parler(f"Je n'ai pas pu bloquer {_ip} : il faut lancer JARVIS en administrateur.")
                return
            await websocket.send(json.dumps({
                "action": "ctx_card", "type": "alert", "icon": "⊘",
                "title": "IP Bloquée",
                "text": f"Règles pare-feu ajoutées pour {_ip} (entrant + sortant)."
            }))
            if hasattr(builtins, 'parler'):
                builtins.parler(f"IP {_ip} bloquée via le pare-feu Windows{nom_virgule()}.")
            print(f"[RADAR] IP bloquée : {_ip}")
        except Exception as _e:
            print(f"[RADAR] Erreur blocage IP : {_e}")


async def ws_get_blocked_ips(websocket, data):
    """Message WS « get_blocked_ips » : liste les IP bloquées par JARVIS."""
    import subprocess as _sp, re as _re2
    try:
        _out = _sp.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True, timeout=8
        ).stdout
        # Extraire les IPs des règles JARVIS_BLOCK_*
        _blocked = []
        _current_name = ""
        for _line in _out.splitlines():
            _lstrip = _line.strip()
            if _lstrip.startswith("Nom de la règle"):
                _current_name = _lstrip.split(":", 1)[-1].strip()
            elif _lstrip.startswith("Rule Name"):
                _current_name = _lstrip.split(":", 1)[-1].strip()
            if _re2.match(r'^JARVIS_BLOCK_\d+_\d+_\d+_\d+_OUT', _current_name):
                _ip_part = _current_name.replace("JARVIS_BLOCK_", "").replace("_OUT", "")
                _ip = ".".join(_ip_part.split("_"))
                if _ip not in _blocked:
                    _blocked.append(_ip)
        await websocket.send(json.dumps({"action": "blocked_ips", "ips": _blocked}))
    except Exception as _e:
        print(f"[RADAR] get_blocked_ips error: {_e}")
        await websocket.send(json.dumps({"action": "blocked_ips", "ips": []}))


async def ws_unblock_ip(websocket, data):
    """Message WS « unblock_ip » : supprime les règles pare-feu d'une IP puis rafraîchit la liste."""
    import re as _re3, subprocess as _sp2
    _ip = data.get("ip", "").strip()
    if _re3.match(r'^\d{1,3}(\.\d{1,3}){3}$', _ip):
        _rule = f"JARVIS_BLOCK_{_ip.replace('.', '_')}"
        try:
            for _dir in ("OUT", "IN"):
                _sp2.run([
                    "netsh", "advfirewall", "firewall", "delete", "rule",
                    f"name={_rule}_{_dir}"
                ], capture_output=True, timeout=5)
            await websocket.send(json.dumps({
                "action": "ctx_card", "type": "info", "icon": "✓",
                "title": "IP Débloquée",
                "text": f"Règles pare-feu supprimées pour {_ip}."
            }))
            # Rafraîchir la liste
            import subprocess as _sp3, re as _re4
            _out2 = _sp3.run(
                ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                capture_output=True, text=True, timeout=8
            ).stdout
            _blocked2 = []
            _cn = ""
            for _ln in _out2.splitlines():
                _ls = _ln.strip()
                if _ls.startswith("Nom de la règle") or _ls.startswith("Rule Name"):
                    _cn = _ls.split(":", 1)[-1].strip()
                if _re4.match(r'^JARVIS_BLOCK_\d+_\d+_\d+_\d+_OUT', _cn):
                    _ip2 = ".".join(_cn.replace("JARVIS_BLOCK_", "").replace("_OUT", "").split("_"))
                    if _ip2 not in _blocked2: _blocked2.append(_ip2)
            await websocket.send(json.dumps({"action": "blocked_ips", "ips": _blocked2}))
        except Exception as _e2:
            print(f"[RADAR] unblock_ip error: {_e2}")


async def ws_clear_cache(websocket, data):
    """Message WS « clear_cache » : vide le cache WebView2 et recharge la fenêtre."""
    print("[CACHE] Nettoyage manuel demandé — reset marqueur + rechargement cache-bust...")
    success = purger_cache_webview()
    await websocket.send(json.dumps({
        "type": "cache_cleared",
        "success": success
    }))
    if _WEBVIEW_OK and webview is not None:
        def _recharger_fenetre_sans_cache():
            try:
                import time
                time.sleep(1.0)
                if webview.windows:
                    try:
                        webview.windows[0].evaluate_js("location.reload(true);")
                        print("[CACHE] Fenêtre rechargée de façon fluide.")
                    except Exception as _e_js:
                        print(f"[CACHE] Rechargement JS alternatif : {_e_js}")
            except Exception as _e:
                print(f"[CACHE] Erreur rechargement fenêtre : {_e}")
        threading.Thread(target=_recharger_fenetre_sans_cache, daemon=True).start()


async def ws_av_threat_action(websocket, data):
    """Message WS « av_threat_action » : autorise / supprime / nettoie / met en quarantaine une menace."""
    action = data.get("action")
    threat = data.get("threat", {})
    t_type = threat.get("type")
    target = threat.get("target")
    success = False
    msg = ""
    # Suppression / vidage d'un fichier ou arrêt d'un processus : confirmation d'abord
    # (ces boutons agissaient immédiatement, contrairement aux autres actions destructrices)
    if action in ("delete", "clean"):
        from core.confirmation import demander_confirmation
        verbe = "Supprimer" if action == "delete" else "Neutraliser"
        if not await demander_confirmation(websocket, f"{verbe} {threat.get('name') or target} ?"):
            await websocket.send(json.dumps({
                "type": "av_action_result", "success": False, "action": action,
                "threat_target": target, "message": "Action annulée."
            }))
            return
    try:
        if action == "allow":
            if target:
                config = _lire_config()
                exclusions = config.get("av_exclusions", [])
                if target not in exclusions:
                    exclusions.append(target)
                _ecrire_config({"av_exclusions": exclusions})
                success = True
                msg = f"Menace tolérée, ajoutée aux exclusions : {target}"
            else:
                msg = "Aucune cible indiquée pour l'exclusion."
        elif action == "delete":
            if t_type == "file":
                if os.path.exists(target):
                    os.remove(target)
                    success = True
                    msg = f"Fichier supprimé : {target}"
                else:
                    success = True
                    msg = "Fichier déjà supprimé."
            elif t_type == "process":
                import re
                match = re.search(r"PID\s+(\d+)", target)
                if match:
                    pid = int(match.group(1))
                    if shared.psutil.pid_exists(pid):
                        p = shared.psutil.Process(pid)
                        p.terminate()
                        success = True
                        msg = f"Processus arrêté (PID {pid})."
                    else:
                        success = True
                        msg = f"Le processus PID {pid} n'est plus actif."
                else:
                    msg = f"Cible incorrecte pour le processus : {target}"
            elif t_type == "registry":
                import winreg
                t_name = threat.get("name")
                is_hklm = "HKLM" in threat.get("desc", "")
                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                try:
                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, t_name)
                    winreg.CloseKey(key)
                    success = True
                    msg = f"Entrée de registre '{t_name}' supprimée."
                except FileNotFoundError:
                    success = True
                    msg = f"Entrée de registre '{t_name}' déjà absente."
                except Exception as re_err:
                    msg = f"Erreur suppression registre : {re_err}"
        elif action == "clean":
            if t_type == "file":
                if os.path.exists(target):
                    with open(target, 'wb') as f:
                        f.write(b"")
                    success = True
                    msg = f"Fichier vidé et neutralisé : {target}"
                else:
                    msg = f"Fichier introuvable : {target}"
            elif t_type == "process":
                import re
                match = re.search(r"PID\s+(\d+)", target)
                if match:
                    pid = int(match.group(1))
                    if shared.psutil.pid_exists(pid):
                        p = shared.psutil.Process(pid)
                        p.terminate()
                        success = True
                        msg = f"Processus stoppé (PID {pid})."
                    else:
                        success = True
                        msg = f"Processus déjà inactif (PID {pid})."
                else:
                    msg = f"Cible invalide : {target}"
            elif t_type == "registry":
                import winreg
                t_name = threat.get("name")
                is_hklm = "HKLM" in threat.get("desc", "")
                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                try:
                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, t_name)
                    winreg.CloseKey(key)
                    success = True
                    msg = f"Entrée de registre '{t_name}' nettoyée."
                except FileNotFoundError:
                    success = True
                    msg = f"Entrée de registre '{t_name}' déjà absente."
                except Exception as re_err:
                    msg = f"Erreur nettoyage registre : {re_err}"
        elif action == "quarantine":
            if t_type == "file":
                if os.path.exists(target):
                    quarantine_dir = os.path.join(shared.RACINE_PROJET, "quarantine")
                    os.makedirs(quarantine_dir, exist_ok=True)
                    filename = threat.get("name", "quarantine_file")
                    import time
                    safe_name = f"{int(time.time())}_{filename}.quarantine"
                    dest = os.path.join(quarantine_dir, safe_name)
                    import shutil
                    shutil.move(target, dest)
                    success = True
                    msg = f"Fichier mis en quarantaine : {safe_name}"
                else:
                    msg = f"Fichier introuvable : {target}"
            elif t_type == "process":
                import re
                match = re.search(r"PID\s+(\d+)", target)
                if match:
                    pid = int(match.group(1))
                    if shared.psutil.pid_exists(pid):
                        p = shared.psutil.Process(pid)
                        p.terminate()
                        success = True
                        msg = f"Processus neutralisé (PID {pid})."
                    else:
                        success = True
                        msg = f"Le processus PID {pid} n'était plus actif."
                else:
                    msg = f"Cible de processus invalide : {target}"
            elif t_type == "registry":
                import winreg
                t_name = threat.get("name")
                is_hklm = "HKLM" in threat.get("desc", "")
                root_key = winreg.HKEY_LOCAL_MACHINE if is_hklm else winreg.HKEY_CURRENT_USER
                sub_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
                try:
                    key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_SET_VALUE)
                    winreg.DeleteValue(key, t_name)
                    winreg.CloseKey(key)
                    success = True
                    msg = f"Entrée de registre '{t_name}' désactivée."
                except FileNotFoundError:
                    success = True
                    msg = f"Entrée de registre '{t_name}' déjà absente."
                except Exception as re_err:
                    msg = f"Erreur : {re_err}"
    except Exception as e:
        msg = f"Échec de l'action {action} : {e}"
        print(f"[AV] Échec action {action} : {e}")
    await websocket.send(json.dumps({
        "type": "av_action_result",
        "success": success,
        "action": action,
        "threat_target": target,
        "message": msg
    }))
