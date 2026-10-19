try:
    import pyautogui
except ImportError:
    pyautogui = None
import time
try:
    import psutil
except ImportError:
    psutil = None
try:
    import requests
except ImportError:
    requests = None
import os
import re
import subprocess

# SPOTIFY
# ==========================================

def _amener_spotify_devant():
    """Amène la fenêtre Spotify devant les autres ; vrai si elle existe."""
    import win32gui, win32con
    candidats = []
    def _rappel_fenetre(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            titre = win32gui.GetWindowText(hwnd)
            if "Spotify" in titre:
                candidats.append(hwnd)
    win32gui.EnumWindows(_rappel_fenetre, None)
    if not candidats:
        return False
    hwnd = candidats[0]
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        return True
    except Exception:
        return False

def spotify_jouer_playlist(playlist_uri: str = "") -> bool:
    """Ouvre Spotify et joue une playlist ou un titre depuis son URI ou son lien web.
    Appelable depuis du code synchrone (executer_action_pc).
    Vrai en cas de succès."""
    try:
        # Convertir URL web open.spotify.com → URI native spotify:
        if playlist_uri.startswith("https://open.spotify.com/"):
            m = re.search(r'/(track|playlist|album|artist)/([A-Za-z0-9]+)', playlist_uri)
            if m:
                playlist_uri = f"spotify:{m.group(1)}:{m.group(2)}"

        deja_ouvert = False
        try:
            deja_ouvert = _amener_spotify_devant()
        except Exception:
            pass

        if playlist_uri:
            # Le protocole spotify: est géré par Windows → ouvre l'app et navigue
            subprocess.Popen(["explorer", playlist_uri], shell=False)
            time.sleep(3)
        elif not deja_ouvert:
            chemin = os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")
            if os.path.exists(chemin):
                subprocess.Popen([chemin])
            else:
                subprocess.Popen(["explorer", "spotify:"], shell=False)
            time.sleep(4)

        try:
            _amener_spotify_devant()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[SPOTIFY] Playlist non lancée : {e}")
        return False
