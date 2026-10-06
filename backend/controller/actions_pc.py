"""Actions PC immédiates (musique, apps, volume, capture), détection des apps installées, appel WhatsApp."""

import asyncio
import os
import subprocess
import time
import webbrowser

import pyautogui

import core.shared as shared
from controller.app_launcher import _boulot_lancer
from controller.deezer_controller import deezer_lancer_playlist
from core.speech import parler
from module.vision_module import jarvis_vision_cliquer
from core.interlocuteur import nom_espace, nom_virgule


def lister_applications_installees():
    """Détecte les applications installées sur le PC à partir des raccourcis du menu Démarrer."""
    import win32com.client
    import pythoncom
    import os
    
    apps = []
    dossiers_start = [
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ]
    
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        seen_paths = set()
        
        for base_dir in dossiers_start:
            if not os.path.exists(base_dir):
                continue
                
            for root, dirs, files in os.walk(base_dir):
                for file in files:
                    if file.lower().endswith(".lnk"):
                        lnk_path = os.path.join(root, file)
                        try:
                            shortcut = shell.CreateShortcut(lnk_path)
                            target_path = shortcut.TargetPath
                            shortcut = None
                            if target_path and target_path.lower().endswith(".exe") and os.path.exists(target_path):
                                target_lower = target_path.lower()
                                if target_lower not in seen_paths:
                                    seen_paths.add(target_lower)
                                    name = file[:-4]
                                    apps.append({
                                        "nom": name,
                                        "chemin": target_path
                                    })
                        except Exception:
                            pass
        shell = None
        apps.sort(key=lambda x: x["nom"].lower())
    except Exception as e:
        print(f"[APPS SCAN] Erreur lors du scan : {e}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        
    return apps


def executer_action_pc(commande):
    cmd          = commande.lower()
    user_profile = os.environ.get('USERPROFILE', '')

    if "met de la musique" in cmd or "mets de la musique" in cmd:
        if "youtube" in cmd:
            url = shared.YOUTUBE_MUSIQUE_URL or "https://www.youtube.com/watch?v=Cr8K88UcO0s"
            webbrowser.open(url, new=2)
            time.sleep(5)
            pyautogui.press('f')
            return f"C'est parti{nom_espace()}, je lance votre musique sur YouTube."
            
        import json as _j
        musique_lien = None
        try:
            _p = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
            if os.path.exists(_p):
                with open(_p, "r", encoding="utf-8") as _f:
                    cfg_temp = _j.load(_f)
                    musique_lien = cfg_temp.get("musique_lien")
        except: pass

        if musique_lien:
            musique_lien_lower = musique_lien.lower()
            if "youtube.com" in musique_lien_lower or "youtu.be" in musique_lien_lower:
                webbrowser.open(musique_lien, new=2)
                time.sleep(5)
                pyautogui.press('f')
                return f"C'est parti{nom_espace()}, je lance votre musique sur YouTube."
            elif "spotify" in musique_lien_lower or musique_lien_lower.startswith("spotify:"):
                try:
                    from controller.spotify_controller import spotify_lancer_playlist
                    ok = spotify_lancer_playlist(musique_lien)
                    if ok:
                        return f"C'est parti{nom_espace()}, je lance votre musique sur Spotify."
                except: pass
                return f"Je n'ai pas réussi à ouvrir Spotify{nom_virgule()}."
            elif "deezer" in musique_lien_lower:
                try:
                    loop = asyncio.new_event_loop()
                    ok = loop.run_until_complete(deezer_lancer_playlist(musique_lien))
                    loop.close()
                except: ok = False
                if ok:
                    return f"C'est parti{nom_espace()}, je lance votre musique sur Deezer."
                return f"Je n'ai pas réussi à ouvrir Deezer{nom_virgule()}."
            else:
                webbrowser.open(musique_lien, new=2)
                return f"C'est parti{nom_espace()}, je lance votre lien de musique personnalisé dans le navigateur."
        else:
            try:
                loop = asyncio.new_event_loop()
                ok = loop.run_until_complete(deezer_lancer_playlist())
                loop.close()
            except Exception as e:
                print(f"[EXECUTER ACTION PC] Erreur lancement Deezer : {e}")
                ok = False
            if ok:
                return f"C'est parti{nom_espace()}, je lance votre playlist sur Deezer."
            return f"Je n'ai pas réussi à ouvrir Deezer{nom_virgule()}."

    # (Bloc YouTube PC supprimé pour éviter les conflits avec la TV)

    if "ouvre" in cmd or "lance" in cmd:
        if "chrome" in cmd:
            if _boulot_lancer("Chrome", ["chrome.exe"], 
                             chemins_hints=[r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", 
                                            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"], 
                             env_key="CHROME_PATH"):
                return "Chrome ouvert."
            return "Je n'ai pas trouvé Chrome sur votre PC."
            
        if "notepad" in cmd or "bloc-notes" in cmd:
            if _boulot_lancer("Notepad", ["notepad.exe"]):
                return "Bloc-notes ouvert."
            return "Je n'ai pas trouvé le Bloc-notes."
            
        if "explorateur" in cmd:
            try:
                subprocess.Popen(["explorer.exe"])
                return "Explorateur ouvert."
            except Exception:
                return "Erreur lors de l'ouverture de l'explorateur."

    if "volume" in cmd:
        if "monte" in cmd or "augmente" in cmd:
            for _ in range(5):
                pyautogui.press('volumeup')
            return "Volume augmente."
        if "baisse" in cmd:
            for _ in range(5):
                pyautogui.press('volumedown')
            return "Volume baisse."
        if "coupe" in cmd:
            pyautogui.press('volumemute')
            return "Son coupe."

    if "screenshot" in cmd or "capture" in cmd:
        if getattr(shared, "ACTIVE_SPEAKER", "neyor") == "guest":
            return "Accès refusé. La capture d'écran est désactivée en mode invité."
        path = os.path.join(user_profile, "Desktop", "screenshot.png")
        pyautogui.screenshot(path)
        return "Screenshot sauvegarde."

    if "eteins" in cmd or "shutdown" in cmd:
        # Géré par plugins/system_resolver.py
        pass

    return None


async def action_whatsapp_appel(contact):
    try:
        parler(f"J'appelle {contact} sur WhatsApp{nom_virgule()}.")
        # Lancement de l'app via le protocole
        os.system("start whatsapp://")
        time.sleep(6) # On laisse le temps a l'app de s'ouvrir et se focuser
        
        # Recherche du contact (Ctrl+F)
        pyautogui.hotkey('ctrl', 'f')
        time.sleep(1)
        pyautogui.typewrite(contact)
        time.sleep(2)
        pyautogui.press('enter')
        time.sleep(3) # On attend que la conversation s'affiche bien
        
        # Utilisation du raccourci clavier officiel pour l'appel audio (plus fiable que la vision)
        print(f"[WHATSAPP] Envoi du raccourci d'appel (Ctrl+Shift+C)...")
        pyautogui.hotkey('ctrl', 'shift', 'c')
        
        # On ajoute quand meme un petit clic de vision en secours si le raccourci ne suffit pas
        time.sleep(2)
        print(f"[WHATSAPP] Verification par vision au cas ou...")
        await jarvis_vision_cliquer("clique sur le bouton 'Appel vocal' ou l icone de telephone qui vient de s afficher en haut a droite")
        
        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        parler(f"Desole{nom_espace()}, je n'ai pas pu lancer l'appel WhatsApp. {e}")
        return False
