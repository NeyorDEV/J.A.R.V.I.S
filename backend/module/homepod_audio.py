"""
JARVIS — Sortie audio HomePod via AirPlay (pyatv)

Sert les fichiers MP3 de TTS via un mini serveur HTTP local,
puis les stream au HomePod avec pyatv. Connexion persistante
pour éviter le scan réseau à chaque phrase.
"""

import asyncio
import os
import socket
import threading
import time
import http.server
import socketserver

import pyatv
import pyatv.const

# ── Configuration ─────────────────────────────────────────────────────────────
HOMEPOD_IP   = os.getenv("HOMEPOD_IP", None)
HTTP_PORT    = int(os.getenv("HOMEPOD_HTTP_PORT", "8766"))

# ── Serveur HTTP local (sert les MP3 au HomePod) ──────────────────────────────
class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        _dir = os.path.dirname(os.path.abspath(__file__))
        _root = os.path.dirname(_dir) if os.path.basename(_dir) == "module" else _dir
        super().__init__(*args, directory=_root, **kwargs)

    def log_message(self, *args): pass
    def log_error(self, *args):   pass

def _start_http_server():
    with socketserver.TCPServer(("", HTTP_PORT), _SilentHandler) as httpd:
        httpd.serve_forever()

_http_thread = threading.Thread(target=_start_http_server, daemon=True)
_http_thread.start()

# ── Connexion persistante HomePod ─────────────────────────────────────────────
_atv        = None   # connexion pyatv active
_atv_lock   = asyncio.Lock()

def _get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

async def _connecter() -> bool:
    """Scanne le réseau et établit la connexion AirPlay."""
    global _atv
    try:
        loop = asyncio.get_event_loop()
        if HOMEPOD_IP:
            devices = await pyatv.scan(loop, hosts=[HOMEPOD_IP], timeout=5)
        else:
            devices = await pyatv.scan(loop, timeout=5)

        if not devices:
            print("[HOMEPOD] Aucun appareil trouvé sur le réseau.")
            return False

        device = devices[0]
        print(f"[HOMEPOD] Connexion à {device.name} ({device.address})...")
        _atv = await pyatv.connect(device, loop)
        print(f"[HOMEPOD] Connecté — sortie audio active.")
        return True
    except Exception as e:
        print(f"[HOMEPOD] Erreur connexion : {e}")
        _atv = None
        return False

async def _get_atv():
    """Retourne la connexion active, reconnecte si nécessaire."""
    global _atv
    async with _atv_lock:
        if _atv is not None:
            try:
                # Vérification légère : le push_updater doit être joignable
                _ = _atv.metadata
                return _atv
            except Exception:
                _atv = None

        ok = await _connecter()
        return _atv if ok else None

# ── Durée MP3 ─────────────────────────────────────────────────────────────────
def _duree_mp3(path: str) -> float:
    """Retourne la durée en secondes. Utilise mutagen si dispo, sinon estime."""
    try:
        from mutagen.mp3 import MP3
        return MP3(path).info.length
    except Exception:
        pass
    # Estimation : edge_tts encode à ~48 kbps
    try:
        return max(1.0, os.path.getsize(path) / 6000)
    except Exception:
        return 3.0

# ── Lecture sur HomePod ───────────────────────────────────────────────────────
async def jouer_sur_homepod(mp3_path: str, stop_checker) -> bool:
    """
    Stream le fichier mp3_path vers le HomePod via AirPlay.
    stop_checker : callable sans argument → True si on doit interrompre.
    Retourne True si la lecture a démarré, False en cas d'échec.
    """
    atv = await _get_atv()
    if atv is None:
        return False

    local_ip = _get_local_ip()
    filename  = os.path.basename(mp3_path)
    url       = f"http://{local_ip}:{HTTP_PORT}/{filename}"
    duree     = _duree_mp3(mp3_path)

    try:
        await atv.stream.play_url(url)
    except Exception as e:
        print(f"[HOMEPOD] Erreur play_url : {e}")
        # Connexion probablement morte — on réinitialise pour la prochaine fois
        global _atv
        _atv = None
        return False

    # Attendre la fin de la lecture en vérifiant STOP_PARLER toutes les 50 ms
    debut = time.monotonic()
    while (time.monotonic() - debut) < duree:
        if stop_checker():
            try:
                await atv.remote_control.pause()
            except Exception:
                pass
            break
        await asyncio.sleep(0.05)

    return True
