"""Détection des applications installées et appel WhatsApp."""

import asyncio
import os

import pyautogui

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


async def action_whatsapp_appel(contact):
    try:
        parler(f"J'appelle {contact} sur WhatsApp{nom_virgule()}.")
        # Lancement de l'app via le protocole
        os.system("start whatsapp://")
        await asyncio.sleep(6) # On laisse le temps a l'app de s'ouvrir et se focuser
        
        # Recherche du contact (Ctrl+F)
        pyautogui.hotkey('ctrl', 'f')
        await asyncio.sleep(1)
        pyautogui.typewrite(contact)
        await asyncio.sleep(2)
        pyautogui.press('enter')
        await asyncio.sleep(3) # On attend que la conversation s'affiche bien
        
        # Utilisation du raccourci clavier officiel pour l'appel audio (plus fiable que la vision)
        print(f"[WHATSAPP] Envoi du raccourci d'appel (Ctrl+Shift+C)...")
        pyautogui.hotkey('ctrl', 'shift', 'c')
        
        # On ajoute quand meme un petit clic de vision en secours si le raccourci ne suffit pas
        await asyncio.sleep(2)
        print(f"[WHATSAPP] Verification par vision au cas ou...")
        await jarvis_vision_cliquer("clique sur le bouton 'Appel vocal' ou l icone de telephone qui vient de s afficher en haut a droite")
        
        return True
    except Exception as e:
        print(f"[WHATSAPP ERROR] {e}")
        parler(f"Desole{nom_espace()}, je n'ai pas pu lancer l'appel WhatsApp. {e}")
        return False
