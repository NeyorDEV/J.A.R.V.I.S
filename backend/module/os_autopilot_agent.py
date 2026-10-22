import os
import time
import json
import re
import asyncio
import subprocess
import builtins
import pyautogui
import win32gui
import win32con
import win32process
import win32api
import win32clipboard
from google.genai import types
from core.config import CHOSEN_MODEL
from controller.app_launcher import _APPS_CATALOGUE, _demarrer_appli_travail
from core.interlocuteur import nom_espace, nom_virgule

# Client Gemini différé (core/ai_clients.py) : pas de plantage à l'import sans clé,
# et une clé changée dans les Paramètres est prise en compte sans redémarrer.
from core.ai_clients import client_gemini as client

# Activer le FailSafe de PyAutoGUI
pyautogui.FAILSAFE = True

SYSTEM_INSTRUCTION = """
Tu es l'agent d'Autopilote OS de J.A.R.V.I.S. Ton but est de traduire des instructions de l'utilisateur en une séquence d'actions système Windows.
Tu devez renvoyer OBLIGATOIREMENT un tableau JSON contenant la suite d'instructions à exécuter.

CONSIGNES IMPORTANTES DE RECHERCHE & SÉCURITÉ :
- Si l'utilisateur demande de créer un NOUVEAU document, d'écrire un NOUVEAU texte ou de taper à partir de zéro dans un éditeur (comme notepad, vscode, word, etc.) :
  Tu devez OBLIGATOIREMENT commencer par envoyer un raccourci clavier "ctrl+n" (nouveau fichier) ou "ctrl+t" (nouvel onglet) IMMÉDIATEMENT après avoir ouvert ou activé l'application, afin d'opérer sur une page blanche et de ne pas écraser les fichiers importants ouverts par erreur.
- Si l'utilisateur demande de MODIFIER, COMPLÉTER ou AGIR sur un fichier DÉJÀ EXISTANT ou déjà ouvert à l'écran :
  Tu ne dois PAS envoyer de "ctrl+n" ni de "ctrl+t". Tu dois interagir directement avec le document actif ou l'ouvrir d'abord, puis y insérer votre texte.
- Si l'utilisateur demande de SAUVEGARDER ou d'ENREGISTRER un fichier à un emplacement particulier (ex: le Bureau, Documents, Téléchargements, un lecteur comme le disque D:, ou un dossier personnalisé comme 'Projets', 'Cours', etc.) :
  Tu devez OBLIGATOIREMENT préfixer le nom du fichier par la variable `{FOLDER:nom_du_dossier_ou_du_lecteur}` dans ton action "type_text" lors de la boîte de dialogue de sauvegarde.
  Voici les exemples d'utilisation :
  * Sauvegarde sur le bureau : `{"action": "type_text", "text": "{FOLDER:bureau}\\\\mon_fichier.txt"}`
  * Sauvegarde dans le dossier Documents : `{"action": "type_text", "text": "{FOLDER:documents}\\\\mon_fichier.txt"}`
  * Sauvegarde sur le lecteur D: : `{"action": "type_text", "text": "{FOLDER:lecteur d}\\\\mon_fichier.txt"}`
  * Sauvegarde dans un dossier personnalisé 'Projets' : `{"action": "type_text", "text": "{FOLDER:projets}\\\\mon_fichier.txt"}`
- Si l'utilisateur demande d'OUVRIR l'explorateur de fichiers sur un dossier particulier (Bureau, Téléchargements, Documents, etc.) :
  Tu as deux options extrêmement fiables :
  1. Préfère TOUJOURS ouvrir directement le dossier via l'action open_app avec arguments (ex: `{"action": "open_app", "app": "explorer shell:Downloads"}` pour les Téléchargements, ou `{"action": "open_app", "app": "explorer {FOLDER:nom_dossier}"}`). C'est instantané et sans erreur de focus.
  2. Si tu choisis d'ouvrir d'abord l'explorateur de fichiers seul (`{"action": "open_app", "app": "explorer"}`), tu devez OBLIGATOIREMENT envoyer le raccourci clavier "alt+d" ou "ctrl+l" pour focaliser et surligner la barre d'adresse avant de taper le chemin du dossier avec l'action "type_text".
- Préfère utiliser "ctrl+n" pour Notepad/Word et "ctrl+n" pour VS Code pour garantir une page blanche lors d'une nouvelle création.

Voici les actions supportées :
1. Lancer une application :
   {"action": "open_app", "app": "notepad|vscode|chrome|cmd|calc|..."}
2. Attendre :
   {"action": "wait", "seconds": 1.5}
3. Saisir du texte dans l'application active :
   {"action": "type_text", "text": "Le texte à taper ici", "app_title": "Titre partiel de l'application (facultatif)"}
4. Raccourcis clavier (ex: sauvegarder ctrl+s, fermer alt+f4, valider enter) :
   {"action": "shortcut", "keys": ["ctrl", "s"]}
5. Clic de souris :
   {"action": "click", "x": 100, "y": 200, "app_title": "Optionnel"}

Exemple de réponse pour "ouvre le bloc-notes, écris bonjour et sauvegarde sur le bureau" :
[
  {"action": "open_app", "app": "notepad"},
  {"action": "wait", "seconds": 1.0},
  {"action": "shortcut", "keys": ["ctrl", "n"]},
  {"action": "wait", "seconds": 0.5},
  {"action": "type_text", "text": "Bonjour, j'exécute vos ordres.", "app_title": "bloc-notes"},
  {"action": "wait", "seconds": 0.5},
  {"action": "shortcut", "keys": ["ctrl", "s"]},
  {"action": "wait", "seconds": 1.0},
  {"action": "type_text", "text": "{FOLDER:bureau}\\\\bonjour_jarvis.txt"},
  {"action": "wait", "seconds": 0.5},
  {"action": "shortcut", "keys": ["enter"]}
]

Ne renvoie aucun texte explicatif en dehors du tableau JSON brut.
"""

def copier_dans_presse_papier(texte):
    """Copie proprement du texte dans le presse-papier Windows (supporte AZERTY/Accents/Underscores)."""
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(texte, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"[OS AGENT] Erreur presse-papier : {e}")
        return False

def est_fenetre_jarvis(hwnd):
    """Détermine si la fenêtre appartient au processus JARVIS ou à sa console parente pour éviter de s'auto-cibler."""
    try:
        # Récupérer le PID du processus de la fenêtre
        _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
        this_pid = os.getpid()
        
        if win_pid == this_pid:
            return True
            
        # Vérifier le processus parent (la console cmd qui a lancé le .bat)
        try:
            import psutil
            this_proc = psutil.Process(this_pid)
            parent_proc = this_proc.parent()
            if parent_proc and win_pid == parent_proc.pid:
                return True
        except ImportError:
            pass
            
        # Vérifier par le titre de la console ou fenêtre JARVIS
        title = win32gui.GetWindowText(hwnd).lower()
        if "j.a.r.v.i.s" in title or "jarvis" in title:
            # Sauf s'il s'agit d'un fichier contenant le nom dans l'éditeur
            if not any(ext in title for ext in [".txt", ".py", ".md", ".json", ".env"]):
                return True
    except Exception:
        pass
    return False

def trouver_fenetre_par_titre(titre_partiel):
    """Recherche la poignée (hwnd) de la première fenêtre avec une gestion intelligente des alias de titres et l'exclusion des fenêtres de JARVIS."""
    tp = titre_partiel.lower().strip()
    
    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            # Ne jamais cibler la console ou l'interface de JARVIS lui-même !
            if est_fenetre_jarvis(hwnd):
                return True
                
            title = win32gui.GetWindowText(hwnd).lower()
            
            # Gestion intelligente des alias de terminaux/cmd sous Windows
            if tp in ["invite de commandes", "cmd", "terminal", "console"]:
                targets = ["invite de commandes", "cmd.exe", "cmd", "terminal", "powershell", "wt.exe"]
                if any(t in title for t in targets):
                    extra.append(hwnd)
            # Gestion intelligente du Bloc-notes sous Windows
            elif tp in ["bloc-notes", "notepad"]:
                targets = ["bloc-notes", "notepad", "sans titre", "txt"]
                if any(t in title for t in targets):
                    extra.append(hwnd)
            # Gestion intelligente de la Calculatrice sous Windows
            elif tp in ["calculatrice", "calc", "calculator"]:
                targets = ["calculatrice", "calculator", "calc"]
                if any(t in title for t in targets):
                    extra.append(hwnd)
            # Cas standard
            elif tp in title:
                extra.append(hwnd)
        return True
    
    hwnds = []
    win32gui.EnumWindows(callback, hwnds)
    return hwnds[0] if hwnds else None

def activer_fenetre(hwnd):
    """Met la fenêtre ciblée au premier plan de façon robuste (avec fallback ultime par clic de souris sur la barre de titre si SetForegroundWindow échoue)."""
    if win32gui.GetForegroundWindow() == hwnd:
        return True
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        
        # Activer directement la fenêtre
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        print(f"[OS AGENT] SetForegroundWindow direct a échoué : {e}")
        # Fallback 1 : Attachement de thread d'entrée
        try:
            import win32process
            fore_hwnd = win32gui.GetForegroundWindow()
            if fore_hwnd:
                fore_thread = win32process.GetWindowThreadProcessId(fore_hwnd)[0]
                this_thread = win32api.GetCurrentThreadId()
                if fore_thread != this_thread:
                    win32process.AttachThreadInput(this_thread, fore_thread, True)
                    win32gui.SetForegroundWindow(hwnd)
                    win32process.AttachThreadInput(this_thread, fore_thread, False)
                else:
                    win32gui.SetForegroundWindow(hwnd)
            else:
                win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as ex:
            print(f"[OS AGENT] Échec de l'activation par thread : {ex}")
            
            # Fallback 2 (ULTIME) : Clic physique sécurisé sur la barre de titre de la fenêtre cible
            try:
                rect = win32gui.GetWindowRect(hwnd)
                # Cliquer en haut à gauche de la fenêtre (barre de titre), typiquement x + 150 pour éviter le menu système, et y + 15
                click_x = rect[0] + 150
                click_y = rect[1] + 15
                
                # S'assurer que les coordonnées sont bien à l'intérieur de l'écran
                sw, sh = pyautogui.size()
                click_x = max(0, min(click_x, sw - 5))
                click_y = max(0, min(click_y, sh - 5))
                
                print(f"[OS AGENT] Fallback Ultime : Clic sur la barre de titre à ({click_x}, {click_y}) pour forcer le focus.")
                original_pos = pyautogui.position()
                pyautogui.moveTo(click_x, click_y)
                pyautogui.click()
                pyautogui.moveTo(original_pos[0], original_pos[1])
                return True
            except Exception as ex_click:
                print(f"[OS AGENT] Échec du clic fallback ultime : {ex_click}")
                return False

def resoudre_chemin_dossier(nom_dossier):
    """Résout dynamiquement n'importe quel nom de dossier ou de disque sous Windows."""
    import unicodedata
    def clean(s):
        return "".join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn').lower().strip()
    
    n = clean(nom_dossier)
    user_profile = os.environ.get('USERPROFILE', '')
    
    # 1. Dossiers utilisateurs standards
    standard_maps = {
        "bureau": "Desktop",
        "desktop": "Desktop",
        "documents": "Documents",
        "document": "Documents",
        "telechargements": "Downloads",
        "downloads": "Downloads",
        "download": "Downloads",
        "images": "Pictures",
        "pictures": "Pictures",
        "photos": "Pictures",
        "photo": "Pictures",
        "musique": "Music",
        "music": "Music",
        "videos": "Videos",
        "video": "Videos"
    }
    
    if n in standard_maps:
        from core.dossiers import dossier_connu
        resolved = dossier_connu(n) or os.path.join(user_profile, standard_maps[n])
        print(f"[OS AGENT] Dossier standard résolu : {nom_dossier} -> {resolved}")
        return resolved
        
    # 2. Lecteurs disques (ex: "lecteur d", "disque d", "d:")
    drive_match = re.search(r'(?:disque|lecteur)?\s*([a-z])\s*(?::)?$', n)
    if drive_match:
        drive_letter = drive_match.group(1).upper()
        drive_path = f"{drive_letter}:\\"
        if os.path.exists(drive_path):
            print(f"[OS AGENT] Lecteur disque résolu : {nom_dossier} -> {drive_path}")
            return drive_path
            
    # 3. Dossier personnalisé (Recherche rapide à profondeur 2)
    # Niveau 1 de l'utilisateur (C:\Users\<utilisateur>\*)
    try:
        for item in os.listdir(user_profile):
            path = os.path.join(user_profile, item)
            if os.path.isdir(path) and clean(item) == n:
                print(f"[OS AGENT] Dossier niveau 1 trouvé : {item} -> {path}")
                return path
    except Exception:
        pass
        
    # Niveau 2 (dans les répertoires principaux)
    from core.dossiers import dossiers_personnels, dossier_connu
    for parent in dossiers_personnels():
        subdir = os.path.basename(parent)
        if os.path.exists(parent) and os.path.isdir(parent):
            try:
                for item in os.listdir(parent):
                    path = os.path.join(parent, item)
                    if os.path.isdir(path) and clean(item) == n:
                        print(f"[OS AGENT] Dossier niveau 2 trouvé : {subdir}/{item} -> {path}")
                        return path
            except Exception:
                continue
                
    # 4. Fallback si introuvable : utiliser le bureau
    fallback = dossier_connu("bureau")
    print(f"[OS AGENT] Dossier '{nom_dossier}' introuvable. Fallback sur le Bureau : {fallback}")
    return fallback

async def dessiner_curseur_sur_hud(x, y, duree=1.0):
    """Envoie un signal WebSocket pour déplacer le curseur virtuel sur le HUD."""
    send_action_to_frontend = getattr(builtins, "send_action_to_frontend", None)
    if send_action_to_frontend:
        sw, sh = pyautogui.size()
        rx = int((x / sw) * 100)
        ry = int((y / sh) * 100)
        await send_action_to_frontend({
            "action": "draw_virtual_cursor",
            "x": rx,
            "y": ry,
            "duration": duree
        })

async def envoyer_log_hud(log_msg):
    """Envoie des logs de diagnostic au bandeau supérieur du HUD."""
    send_action_to_frontend = getattr(builtins, "send_action_to_frontend", None)
    if send_action_to_frontend:
        await send_action_to_frontend({
            "action": "os_agent_status",
            "log": log_msg,
            "active": True
        })

async def masquer_bandeau_hud():
    """Masque la bannière d'autopilote une fois la tâche achevée."""
    send_action_to_frontend = getattr(builtins, "send_action_to_frontend", None)
    if send_action_to_frontend:
        await send_action_to_frontend({
            "action": "os_agent_status",
            "log": "",
            "active": False
        })

async def executer_sequence_actions(sequence):
    """Exécute une suite d'étapes d'autopilote OS de façon hautement résiliente."""
    original_mouse_pos = pyautogui.position()
    last_hwnd = None
    
    try:
        for i, step in enumerate(sequence):
            action = step.get("action", "")
            print(f"[OS AGENT] Étape {i+1} : {step}")
            
            # --- PERSISTANCE DU FOCUS ---
            app_title = step.get("app_title", "")
            if app_title:
                hwnd = trouver_fenetre_par_titre(app_title)
                if hwnd:
                    last_hwnd = hwnd
                    activer_fenetre(hwnd)
                    # Déplacer le curseur virtuel au centre de la fenêtre ciblée pour illustrer visuellement l'activité de l'IA
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        cx = (rect[0] + rect[2]) // 2
                        cy = (rect[1] + rect[3]) // 2
                        await dessiner_curseur_sur_hud(cx, cy, duree=0.6)
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)
            elif last_hwnd and action in ["type_text", "shortcut"]:
                activer_fenetre(last_hwnd)
                # Déplacer le curseur virtuel sur la fenêtre réactivée
                try:
                    rect = win32gui.GetWindowRect(last_hwnd)
                    cx = (rect[0] + rect[2]) // 2
                    cy = (rect[1] + rect[3]) // 2
                    await dessiner_curseur_sur_hud(cx, cy, duree=0.4)
                except Exception:
                    pass
                await asyncio.sleep(0.2)
                
            # 1. LANCEMENT D'APPLICATION
            if action == "open_app":
                app = step.get("app", "").lower().strip()
                await envoyer_log_hud(f"Lancement de l'application : {app.upper()}")
                
                # Normalisation d'alias pour les consoles/terminaux Windows
                if app in ["cmd", "cmd.exe", "invite de commandes", "invite de commande", "console"]:
                    app_to_launch = "cmd.exe"
                elif app in ["powershell", "powershell.exe"]:
                    app_to_launch = "powershell.exe"
                else:
                    app_to_launch = app

                if app_to_launch in ["cmd.exe", "powershell.exe"]:
                    try:
                        # 0x00000010 = CREATE_NEW_CONSOLE pour forcer l'ouverture dans une nouvelle fenêtre console indépendante
                        subprocess.Popen([app_to_launch], creationflags=0x00000010)
                    except Exception:
                        try:
                            subprocess.Popen(f"start {app_to_launch}", shell=True)
                        except Exception:
                            pyautogui.hotkey('win', 'r')
                            await asyncio.sleep(0.3)
                            pyautogui.write(app_to_launch)
                            pyautogui.press('enter')
                elif app_to_launch in _APPS_CATALOGUE:
                    info = _APPS_CATALOGUE[app_to_launch]
                    _demarrer_appli_travail(info["label"], info["noms"], info["hints"])
                else:
                    # Application inconnue du catalogue : le nom vient d'un plan
                    # généré par le LLM. On ne le passe SURTOUT PAS à un shell
                    # (`shell=True` exécutait n'importe quelle commande, ex.
                    # « cmd /c del /s /q C:\\Users\\... »). On valide le nom, puis
                    # on passe par la boîte « Exécuter » de Windows, qui n'ouvre
                    # qu'un programme et n'interprète ni « && », ni « | », ni « ; ».
                    import re as _re_app
                    _nom_app = str(app_to_launch).strip()
                    if _re_app.fullmatch(r"[A-Za-z0-9 ._\-]{1,60}", _nom_app):
                        pyautogui.hotkey('win', 'r')
                        await asyncio.sleep(0.3)
                        pyautogui.write(_nom_app)
                        pyautogui.press('enter')
                    else:
                        print(f"[AUTOPILOT] ⛔ Nom d'application refusé (caractères suspects) : {app_to_launch!r}")
                
                # Attente et déplacement du curseur virtuel sur la nouvelle fenêtre
                await asyncio.sleep(1.0)
                hwnd = trouver_fenetre_par_titre(app)
                if hwnd:
                    last_hwnd = hwnd
                    activer_fenetre(hwnd)
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        cx = (rect[0] + rect[2]) // 2
                        cy = (rect[1] + rect[3]) // 2
                        await dessiner_curseur_sur_hud(cx, cy, duree=0.8)
                    except Exception:
                        pass
                
            # 2. SAISIE DE TEXTE (Sécurisée via Presse-Papier pour AZERTY)
            elif action == "type_text":
                text = step.get("text", "")
                
                # Résolution dynamique des dossiers et lecteurs : format {FOLDER:nom_dossier}
                folder_matches = re.findall(r'\{FOLDER:(.*?)\}', text)
                for folder_name in folder_matches:
                    resolved_path = resoudre_chemin_dossier(folder_name)
                    text = text.replace(f'{{FOLDER:{folder_name}}}', resolved_path)
                
                # Normalisation des doubles antislashs indésirables sous Windows (ex: N:\\joytokey -> N:\joytokey)
                if text.startswith('\\\\'):
                    text = '\\\\' + text[2:].replace('\\\\', '\\')
                else:
                    text = text.replace('\\\\', '\\')
                
                await envoyer_log_hud(f"Saisie de texte : '{text[:30]}...'")
                
                if copier_dans_presse_papier(text):
                    pyautogui.hotkey('ctrl', 'v')
                else:
                    pyautogui.write(text, interval=0.03)
                
            # 3. RACCOURCI CLAVIER
            elif action == "shortcut":
                keys = step.get("keys", [])
                await envoyer_log_hud(f"Raccourci clavier : {' + '.join(keys)}")
                await asyncio.sleep(0.2)
                
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                elif len(keys) == 2:
                    pyautogui.hotkey(keys[0], keys[1])
                elif len(keys) == 3:
                    pyautogui.hotkey(keys[0], keys[1], keys[2])
                
            # 4. CLIC DE SOURIS
            elif action == "click":
                x = step.get("x")
                y = step.get("y")
                
                if x is not None and y is not None:
                    if app_title:
                        hwnd = trouver_fenetre_par_titre(app_title)
                        if hwnd:
                            rect = win32gui.GetWindowRect(hwnd)
                            x = rect[0] + x
                            y = rect[1] + y
                    
                    await envoyer_log_hud(f"Déplacement & Clic sur ({x}, {y})")
                    original_mouse_pos = pyautogui.position()
                    
                    await dessiner_curseur_sur_hud(x, y, duree=0.8)
                    await asyncio.sleep(0.8)
                    
                    pyautogui.moveTo(x, y)
                    pyautogui.click()
                    pyautogui.moveTo(original_mouse_pos[0], original_mouse_pos[1])
                    
            # 5. TEMPORISATION
            elif action == "wait":
                sec = step.get("seconds", 1.0)
                await envoyer_log_hud(f"Attente de {sec}s...")
                await asyncio.sleep(sec)
                
    except Exception as e:
        print(f"[OS AGENT ERROR] Exception durant l'exécution : {e}")
        await envoyer_log_hud(f"Erreur Autopilote : {e}")
        await asyncio.sleep(2.0)
        execution_error = e
    else:
        execution_error = None
    finally:
        pyautogui.moveTo(original_mouse_pos[0], original_mouse_pos[1])
        await masquer_bandeau_hud()
        
        # Confirmation vocale de la fin de l'exécution
        parler = getattr(builtins, "parler", None)
        if parler:
            if execution_error:
                parler(f"Désolé{nom_espace()}, une erreur est survenue pendant l'autopilote OS.")
            else:
                parler(f"J'ai terminé l'exécution de l'autopilote OS{nom_virgule()}.")
        
        # Réinitialiser le timeout de session pour que JARVIS reste actif après l'exécution
        builtins.dernier_message = time.time()

def _resumer_plan(sequence, maximum=4):
    """« ouvrir notepad, taper « Bonjour… », raccourci ctrl+s » : résumé lisible du plan."""
    morceaux = []
    for step in sequence[:maximum]:
        action = step.get("action", "")
        if action == "open_app":
            morceaux.append(f"ouvrir {step.get('app', '?')}")
        elif action == "type_text":
            texte = str(step.get("text", ""))
            morceaux.append(f"taper « {texte[:40]}{'…' if len(texte) > 40 else ''} »")
        elif action == "shortcut":
            morceaux.append(f"raccourci {'+'.join(step.get('keys', [])) if isinstance(step.get('keys'), list) else step.get('keys', '?')}")
        elif action == "click":
            morceaux.append("clic")
        elif action == "wait":
            continue
        else:
            morceaux.append(action)
    reste = len([s for s in sequence if s.get("action") != "wait"]) - len(morceaux)
    if reste > 0:
        morceaux.append(f"et {reste} autre{'s' if reste > 1 else ''} étape{'s' if reste > 1 else ''}")
    return ", ".join(morceaux) or "aucune étape"


async def lancer_autopilote(instruction):
    """Point d'entrée principal pour décoder l'instruction et lancer la séquence."""
    print(f"[OS AGENT] Lancement de la planification pour : {instruction}")
    
    prompt = f"L'utilisateur souhaite réaliser cette tâche sur son ordinateur :\n\"{instruction}\"\nGénère le tableau JSON des actions correspondantes."
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=CHOSEN_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json"
                )
            )
        )
        
        sequence = json.loads(response.text)
        if not isinstance(sequence, list):
            sequence = sequence.get("steps", [])
            
        if not sequence:
            return f"Je n'ai pas pu dresser un plan d'actions valide pour cette tâche{nom_virgule()}."
            
        print(f"[OS AGENT] Séquence planifiée avec succès ({len(sequence)} étapes)")
        # Le plan vient de l'IA et prend la main sur la souris et le clavier (y compris pour
        # taper dans une invite de commandes) : il est annoncé et confirmé avant exécution.
        from core.confirmation import demander_confirmation
        if not await demander_confirmation(None, f"Autopilote : {_resumer_plan(sequence)}. Je lance ?"):
            return f"Autopilote annulé{nom_virgule()}."
        from core.web_bridge import demarrer_tache_fond
        demarrer_tache_fond(executer_sequence_actions(sequence))
        
        return f"C'est parti{nom_espace()}, j'active l'autopilote OS. Regardez mon curseur virtuel à l'écran."
        
    except Exception as e:
        print(f"[OS AGENT ERROR] Impossible de planifier la tâche : {e}")
        return f"Erreur lors de la planification de l'autopilote : {e}"
