"""Protection antivirus en temps réel (surveillance continue des processus et fichiers récents)."""

import asyncio

import core.shared as shared
from core.micro import _charger_config
from core.speech import parler


async def boucle_antivirus_live():
    """Surveille les dossiers sensibles et processus actifs toutes les 3 secondes."""
    import json
    import os
    import time
    import stat
    import shutil
    import psutil
    from antivirus_scanner import is_file_suspicious, get_exclusions, is_excluded

    # Charger l'état initial depuis la config
    try:
        cfg = _charger_config()
        shared.AV_LIVE_PROTECTION_ENABLED = cfg.get("av_live_protection", False)
    except Exception:
        shared.AV_LIVE_PROTECTION_ENABLED = False

    print(f"[AV LIVE] Protection en temps réel initialisée : {'ACTIF' if shared.AV_LIVE_PROTECTION_ENABLED else 'INACTIF'}")

    last_check_time = time.time()

    while True:
        try:
            if shared.AV_LIVE_PROTECTION_ENABLED:
                folders = [
                    os.path.expanduser("~/Desktop"),
                    os.path.expanduser("~/Downloads"),
                    os.environ.get("TEMP"),
                    os.environ.get("TMP"),
                    shared.RACINE_PROJET
                ]
                folders = list(set([os.path.abspath(f) for f in folders if f and os.path.exists(f)]))
                exclusions = get_exclusions()
                current_time = time.time()

                # 1. Surveillance des fichiers physiques
                for folder in folders:
                    try:
                        for file in os.listdir(folder):
                            filepath = os.path.join(folder, file)
                            if os.path.isfile(filepath):
                                try:
                                    mtime = os.path.getmtime(filepath)
                                    if mtime > last_check_time:
                                        normalized_filepath = os.path.normpath(filepath).lower()
                                        if normalized_filepath in shared.AV_LIVE_REPORTED_THREATS:
                                            continue

                                        t_class, t_desc = is_file_suspicious(filepath)
                                        if t_class:
                                            if is_excluded(filepath, exclusions):
                                                continue

                                            shared.AV_LIVE_REPORTED_THREATS.add(normalized_filepath)
                                            print(f"[AV LIVE] Menace détectée : {filepath} ({t_class})")

                                            # Tenter d'arrêter les processus verrouillant le fichier
                                            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                                                try:
                                                    exe_path = proc.info.get('exe')
                                                    if exe_path and os.path.normpath(exe_path).lower() == normalized_filepath:
                                                        print(f"[AV LIVE] Arrêt du processus {proc.info['name']} (PID {proc.info['pid']})")
                                                        p = psutil.Process(proc.info['pid'])
                                                        p.terminate()
                                                        try:
                                                            p.wait(timeout=1.0)
                                                        except psutil.TimeoutExpired:
                                                            p.kill()
                                                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                                    pass

                                            # Rendre le fichier modifiable/supprimable
                                            try:
                                                os.chmod(filepath, stat.S_IWRITE)
                                            except Exception:
                                                pass

                                            # Déplacer vers quarantaine
                                            quarantine_dir = os.path.join(shared.RACINE_PROJET, "quarantine")
                                            os.makedirs(quarantine_dir, exist_ok=True)
                                            safe_name = f"{int(time.time())}_{file}.quarantine"
                                            dest = os.path.join(quarantine_dir, safe_name)
                                            shutil.move(filepath, dest)

                                            # Alerte WebSocket
                                            msg = {
                                                "type": "av_live_threat_intercepted",
                                                "threat": {
                                                    "type": "file",
                                                    "name": file,
                                                    "target": filepath,
                                                    "class": t_class,
                                                    "desc": f"INTERCEPTÉ & SÉCURISÉ. {t_desc}"
                                                },
                                                "quarantine_file": safe_name
                                            }
                                            if shared.CONNECTED_CLIENTS:
                                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True))

                                            # Notification vocale
                                            try:
                                                u_name = cfg.get("user_name", "mylane")
                                                asyncio.create_task(parler(f"Alerte sécurité, {u_name}. J'ai détecté et neutralisé une menace en temps réel : {file}. Le fichier suspect a été placé en quarantaine."))
                                            except: pass
                                except OSError:
                                    pass
                    except Exception as e:
                        print(f"[AV LIVE] Erreur dossier {folder} : {e}")

                # 2. Surveillance des processus actifs suspects
                for proc in psutil.process_iter(['pid', 'name', 'exe']):
                    try:
                        pid = proc.info.get('pid')
                        name = proc.info.get('name') or ''
                        exe = proc.info.get('exe') or ''
                        
                        target_key = f"PID {pid} ({exe})"
                        normalized_exe = os.path.normpath(exe).lower() if exe else ""
                        
                        if target_key in shared.AV_LIVE_REPORTED_THREATS or (normalized_exe and normalized_exe in shared.AV_LIVE_REPORTED_THREATS):
                            continue
                            
                        name_lower = name.lower()
                        exe_lower = exe.lower()
                        
                        detected = False
                        desc = ""
                        if "mimikatz" in name_lower or "miner.exe" in name_lower or "keylogger" in name_lower:
                            detected = True
                            desc = "Processus suspect (menace connue)"
                        elif ("temp" in exe_lower or "tmp" in exe_lower) and name_lower.endswith((".exe", ".bat")):
                            detected = True
                            desc = "Processus actif lancé depuis le dossier temporaire"
                            
                        if detected:
                            if is_excluded(target_key, exclusions) or (exe and is_excluded(exe, exclusions)):
                                continue
                                
                            shared.AV_LIVE_REPORTED_THREATS.add(target_key)
                            print(f"[AV LIVE] Processus suspect neutralisé : {name} (PID {pid})")
                            
                            # Arrêter le processus
                            p = psutil.Process(pid)
                            p.terminate()
                            try:
                                p.wait(timeout=1.0)
                            except psutil.TimeoutExpired:
                                p.kill()
                                
                            # Alerte WebSocket
                            msg = {
                                "type": "av_live_threat_intercepted",
                                "threat": {
                                    "type": "process",
                                    "name": name,
                                    "target": target_key,
                                    "class": "Suspicious.ActiveProcess",
                                    "desc": f"PROCESSUS ARRÊTÉ & NEUTRALISÉ. {desc}"
                                }
                            }
                            if shared.CONNECTED_CLIENTS:
                                asyncio.ensure_future(asyncio.gather(*[ws.send(json.dumps(msg)) for ws in shared.CONNECTED_CLIENTS], return_exceptions=True))
                                
                            try:
                                u_name = cfg.get("user_name", "mylane")
                                asyncio.create_task(parler(f"Sécurité système, {u_name}. J'ai intercepté et arrêté un processus suspect actif : {name}."))
                            except: pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                
                last_check_time = current_time
        except Exception as e:
            print(f"[AV LIVE] Erreur boucle principale : {e}")
            
        await asyncio.sleep(3)
