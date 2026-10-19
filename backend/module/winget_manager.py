"""
winget_manager.py — Mises à jour système via winget.

Listing des paquets obsolètes et exécution des upgrades (avec élévation UAC
si nécessaire), progression streamée au frontend via websocket.
Extrait de main2.py.
"""

import asyncio

# ── Winget System Upgrade Helpers ──────────────────────────────────────────
def _normaliser_version_winget(v):
    v = v.strip().lower()
    if v.startswith('v'):
        v = v[1:]
    if v.startswith('.'):
        v = v[1:]
    return v.strip()

def _version_au_moins(installed, available):
    inst_clean = _normaliser_version_winget(installed)
    avail_clean = _normaliser_version_winget(available)
    if inst_clean == avail_clean:
        return True
    try:
        import re
        inst_parts = [int(x) for x in re.split(r'[^0-9]', inst_clean) if x]
        avail_parts = [int(x) for x in re.split(r'[^0-9]', avail_clean) if x]
        for i in range(max(len(inst_parts), len(avail_parts))):
            p1 = inst_parts[i] if i < len(inst_parts) else 0
            p2 = avail_parts[i] if i < len(avail_parts) else 0
            if p1 > p2:
                return True
            elif p1 < p2:
                return False
        return True
    except Exception:
        pass
    return inst_clean == avail_clean

def inventorier_mises_a_jour():
    try:
        import subprocess
        res = subprocess.run(["winget", "upgrade", "--include-unknown"], capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=20)
        stdout = res.stdout
    except subprocess.TimeoutExpired:
        print("[WINGET] winget upgrade n'a pas répondu à temps.")
        return []
    except Exception as e:
        try:
            res = subprocess.run(["winget", "upgrade", "--include-unknown"], capture_output=True, text=True, encoding="cp1252", errors="ignore", timeout=20)
            stdout = res.stdout
        except Exception as e2:
            print(f"[WINGET] winget a échoué : {e2}")
            return []

    lines = stdout.splitlines()
    header_idx = -1
    for idx, line in enumerate(lines):
        if "-------------------" in line or "======" in line:
            header_idx = idx - 1
            break
            
    if header_idx == -1:
        print("[WINGET] Pas d'en-tête de tableau, ou tout est déjà à jour.")
        return []
        
    headers_line = lines[header_idx]
    
    idx_id = headers_line.find("ID")
    idx_ver = headers_line.find("Version")
    idx_disp = headers_line.find("Disponible")
    if idx_disp == -1:
        idx_disp = headers_line.find("Available")
    idx_src = headers_line.find("Source")
    
    if idx_id == -1 or idx_ver == -1 or idx_disp == -1 or idx_src == -1:
        print("[WINGET] Colonnes du tableau introuvables.")
        return []
        
    results = []
    for line in lines[header_idx+2:]:
        if not line.strip():
            continue
        if any(term in line.lower() for term in ["mise à niveau", "upgrade", "package", "numéro", "version"]):
            continue
            
        name = line[:idx_id].strip()
        pkg_id = line[idx_id:idx_ver].strip()
        version = line[idx_ver:idx_disp].strip()
        available = line[idx_disp:idx_src].strip()
        source = line[idx_src:].strip()
        
        if pkg_id and available:
            if _version_au_moins(version, available):
                continue
            results.append({
                "name": name,
                "id": pkg_id,
                "version": version,
                "available": available,
                "source": source
            })
            
    return results

def lancer_mise_a_jour_winget(args, loop, websocket_client, paquet=None):
    """Lance winget et relaie sa sortie au HUD. `paquet` (identifiant winget) accompagne chaque
    message : le panneau affiche l'avancement sur la ligne du logiciel concerné."""
    try:
        import subprocess
        import ctypes
        import json
        
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            is_admin = False
            
        if not is_admin:
            # Élévation UAC : les arguments sont interpolés dans une commande
            # PowerShell, il faut donc les échapper rigoureusement.
            # Auparavant ils étaient insérés bruts entre apostrophes : un simple
            # « ' » dans un identifiant de paquet fermait la chaîne et permettait
            # d'exécuter du PowerShell arbitraire AVEC les droits administrateur.
            # On valide d'abord chaque argument, puis on double les apostrophes
            # (échappement PowerShell) et on construit un tableau explicite.
            import re as _re_w

            def _arg_sur(a: str) -> str:
                a = str(a)
                # Jeu de caractères volontairement restreint : identifiants winget,
                # versions, sources et options. Tout le reste est rejeté.
                if not _re_w.fullmatch(r"[A-Za-z0-9 ._\-+:/\\@]{1,200}", a):
                    raise ValueError(f"Argument winget refusé (caractères interdits) : {a!r}")
                return "'" + a.replace("'", "''") + "'"

            winget_args = ", ".join(_arg_sur(a) for a in args[1:])
            elevated_cmd = f"Start-Process winget -ArgumentList @({winget_args}) -Verb RunAs -Wait"
            
            asyncio.run_coroutine_threadsafe(
                websocket_client.send(json.dumps({
                    "type": "winget_upgrade_progress",
                    "id": paquet,
                    "status": "running",
                    "log": "[JARVIS] Demande d'élévation Administrateur (UAC) en cours...\n[JARVIS] Une fenêtre de commande administrateur va s'ouvrir pour effectuer l'installation.\n"
                })),
                loop
            )
            
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", elevated_cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            proc.wait()
            return_code = proc.returncode
        else:
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1,
                errors='ignore'
            )
            for line in proc.stdout:
                text = line.strip()
                if text:
                    asyncio.run_coroutine_threadsafe(
                        websocket_client.send(json.dumps({
                            "type": "winget_upgrade_progress",
                            "id": paquet,
                            "status": "running",
                            "log": text + "\n"
                        })),
                        loop
                    )
            proc.wait()
            return_code = proc.returncode
            
        asyncio.run_coroutine_threadsafe(
            websocket_client.send(json.dumps({
                "type": "winget_upgrade_progress",
                "id": paquet,
                "status": "complete",
                "returncode": return_code
            })),
            loop
        )
        return return_code == 0
    except Exception as e:
        print(f"[WINGET] winget upgrade a échoué : {e}")
        asyncio.run_coroutine_threadsafe(
            websocket_client.send(json.dumps({
                "type": "winget_upgrade_progress",
                "id": paquet,
                "status": "complete",
                "returncode": -1,
                "log": f"Erreur: {str(e)}\n"
            })),
            loop
        )




