"""J.A.R.V.I.S — point d'entrée.

Ce fichier ne fait qu'orchestrer le démarrage, dans un ordre précis :
  1. console + bannière (avant les imports lourds),
  2. moteur de parole, modèles audio (VAD, biométrie, wake word),
  3. modules du projet (dans l'ordre d'origine : certains lisent l'environnement
     ou `builtins` au moment de leur import),
  4. clés API et clients des moteurs IA,
  5. main() : frontend, serveur WebSocket + écoute vocale (start_ia), fenêtre.

La logique vit dans backend/ (core/, module/, controller/, plugins/) ; l'état
partagé entre ces modules est dans backend/core/shared.py.
"""
import os
import sys

# Injection des dossiers backend/ et tools/ dans le path pour conserver les imports existants
_backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
_tools_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools')
if _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)
if _tools_path not in sys.path:
    sys.path.insert(0, _tools_path)

# Configuration de l'encodage standard en UTF-8 pour supporter les emojis et caractères spéciaux sur Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import threading
import asyncio
import warnings

import core.shared as shared
from core.console_ui import installer_console, TeeLogger

# ── Banner affiché immédiatement avant les imports lourds ──────
installer_console()

# Masquer l'avertissement de dépréciation de pkg_resources (pygame/setuptools) avant tout import
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

# ── Imports lourds en parallèle via threads (gain ~0.6-0.8s) ───
import importlib, concurrent.futures as _cf
from core.interlocuteur import NOM_CREATEUR

def _import(name):
    return importlib.import_module(name)

with _cf.ThreadPoolExecutor(max_workers=4) as _pool:
    _f_genai   = _pool.submit(_import, "google.genai")
    _f_edge    = _pool.submit(_import, "edge_tts")
    _f_pygame  = _pool.submit(_import, "pygame")
    _f_sr      = _pool.submit(_import, "speech_recognition")
    genai      = _f_genai.result()
    edge_tts   = _f_edge.result()
    sr         = _f_sr.result()
    try:
        pygame = _f_pygame.result()
    except Exception:
        pygame = None
        print("[AVERTISSEMENT] pygame non installe — l'audio TTS sera desactive.")

# ── Modules du projet : ORDRE D'IMPORT D'ORIGINE CONSERVÉ ───────────────────
# Plusieurs modules figent des valeurs au moment de leur import (variables
# d'environnement lues avant/après un load_dotenv(), attributs de builtins
# présents ou non...). Les importer dans un autre ordre changerait leur config.
import controller.homepod_controller  # noqa: F401  (lit HOMEPOD_* avant le chargement du .env)
from dotenv import load_dotenv
import builtins

import core.config  # noqa: F401  (charge le .env, injecte builtins._cle_valide / CHOSEN_MODEL)
import core.speech as speech
# Ancrage robuste du moteur de parole
parler = getattr(builtins, "parler", None)
if parler is None:
    from core.speech import parler
builtins.parler = parler

threading.Thread(target=speech.gestionnaire_parole_worker, daemon=True).start()

# --- INITIALISATION DE SILERO VAD, BIOMÉTRIE VOCALE ET OPENWAKEWORD ---
from core.voice_init import initialiser_vad_biometrie, initialiser_wakeword
initialiser_vad_biometrie()
initialiser_wakeword()

import module.file_manager
builtins.resoudre_chemin = module.file_manager.resoudre_chemin
from module.alarm_manager import set_parler_callback, demarrer_daemon_alarmes
import plugins.list_manager  # noqa: F401
from module.memory_manager import _charger_historique_recent
from controller.spotify_controller import spotify_lancer_playlist
builtins.spotify_lancer_playlist = spotify_lancer_playlist
import controller.deezer_controller  # noqa: F401
from controller.app_launcher import _APPS_CATALOGUE
import module.image_generator  # noqa: F401
import module.chess_manager  # noqa: F401
import chess  # noqa: F401

# ── Plugins de résolution : importés en arrière-plan (gain ~1.4s) ─
from core.chargement_plugins import _charger_plugins
threading.Thread(target=_charger_plugins, daemon=True).start()

builtins._APPS_CATALOGUE = _APPS_CATALOGUE

import module.google_services  # noqa: F401
import module.vision_module  # noqa: F401  (avant builtins.client : voir module)
import module.sports_web  # noqa: F401  (avant builtins.client : voir module)
import module.image_search  # noqa: F401
import module.vector_memory  # noqa: F401
from module.browser_service import AutonomousBrowser
shared.browser_agent = AutonomousBrowser()
builtins.browser_agent = shared.browser_agent
import module.visual_web_agent  # noqa: F401
import antivirus_scanner  # noqa: F401
import pyautogui  # noqa: F401
import subprocess  # noqa: F401
import time

# --- Flux d'acquisition micro (extrait dans core/audio_stream.py) ---
import core.audio_stream  # noqa: F401  (avertit si pyaudio est absent)
import websockets

# ── Pont WebSocket vers le HUD (envoi depuis n'importe quel thread) ─────────
import core.web_bridge  # noqa: F401  (injecte send_web_*, envoyer_image_web... dans builtins)
import module.winget_manager  # noqa: F401
import module.competences  # noqa: F401
from openai import OpenAI  # noqa: F401

try:
    import cv2  # noqa: F401
except ImportError:
    cv2 = None

try:
    import psutil
except ImportError:
    psutil = None
shared.psutil = psutil

import core.ai_clients  # noqa: F401  (anthropic / mistralai optionnels ; injecte builtins._cle_valide)

# Google APIs (Gmail, Drive, Calendar) : optionnels
try:
    from google.oauth2.credentials import Credentials  # noqa: F401
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: F401
    from google.auth.transport.requests import Request  # noqa: F401
    from googleapiclient.discovery import build  # noqa: F401
except ImportError:
    print("[AVERTISSEMENT] google-auth-oauthlib non installe — Gmail/Drive/Calendar desactives.")
    print("  -> Pour l'installer : pip install google-auth-oauthlib google-api-python-client")

# --- pycaw (volume systeme Windows) et screen-brightness-control : optionnels ---
# (chargés au démarrage comme avant : initialisation COM dans le thread principal)
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: F401
    from comtypes import CLSCTX_ALL  # noqa: F401
except ImportError:
    pass
try:
    import screen_brightness_control  # noqa: F401
except ImportError:
    pass

# Chargement des variables d'environnement
load_dotenv()

# ── Clés API et clients des moteurs IA ──────────────────────────────────────
from core.ai_clients import get_local_ip, initialiser_cles_et_clients
shared.LOCAL_IP = get_local_ip()
initialiser_cles_et_clients()

# Météo / Home Assistant / MCP : importés APRÈS la lecture des clés (ils rechargent
# le .env avec override=True, ce qui ne doit pas influencer les clés lues ci-dessus).
import module.meteo_domotique  # noqa: F401
import core.ha_mcp_client  # noqa: F401
import core.mcp_client  # noqa: F401
import core.api_quota  # noqa: F401
import core.prompt_builder  # noqa: F401
import core.confirmation  # noqa: F401
import core.llm_registry  # noqa: F401

# ── WebSocket / HUD ─────────────────────────────────────────────────────────
builtins.CONNECTED_CLIENTS = shared.CONNECTED_CLIENTS
builtins.FORCE_LOCAL_MODE = False

shared.historique = _charger_historique_recent()

# Resolver local du globe : injecté dans builtins au même moment qu'avant (le
# plugin globe_resolver.py, chargé en arrière-plan, injecte aussi ce nom).
import module.globe_local  # noqa: F401

# ── Mixer audio ─────────────────────────────────────────────────────────────
if pygame:
    pygame.init()
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
else:
    print("[INFO] Pygame absent — demarrage sans audio TTS.")

# ── Météo/musique & cache webview ───────────────────────────────────────────
from module.weather_music_service import CLIENT_LOCATION, broadcast_weather_stats, broadcast_music_stats
shared.CLIENT_LOCATION = CLIENT_LOCATION
from core.webview_cache import vider_cache_webview_si_nouvelle_version

# ── Services du backend (après tout le reste, comme leur code dans l'ancien main.py)
from core.ws_handler import ws_handler
from core.ecoute import ecouter
from core.llm_chat import generer_salutation_demarrage
from core.micro import monitor_claps
from core.lancement import (
    afficher_statut_services, liberer_ports_occupes, lancer_frontend, ouvrir_interface,
    start_mobile_http_server,
)
from module.antivirus_live import boucle_antivirus_live
from module.domotique_sim import broadcast_ha_stats, update_homepods_metadata_loop
from module.system_stats import broadcast_system_stats
import module.cortex_service  # noqa: F401  (abonnement aux nouveaux souvenirs du cortex 3D)


def start_ia():
    threading.Thread(target=monitor_claps, daemon=True).start()

    # Légère attente pour s'assurer du bon ordonnancement avec les messages du thread claps
    time.sleep(0.15)
    nb_conv = len(shared.historique) // 2 if hasattr(shared, "historique") else 0
    print(f"[CONV] {nb_conv} conversations chargées en mémoire")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_ws():
        shared.WS_LOOP = asyncio.get_running_loop()
        print("[WEB] Serveur WebSocket de communication démarré.")

        # Lancer le monitoring système en arrière-plan
        asyncio.create_task(broadcast_system_stats())
        asyncio.create_task(broadcast_weather_stats())
        asyncio.create_task(broadcast_music_stats())
        asyncio.create_task(broadcast_ha_stats())
        asyncio.create_task(update_homepods_metadata_loop())
        asyncio.create_task(boucle_antivirus_live())

        # Le gestionnaire de parole est déjà lancé au démarrage du script


        async with websockets.serve(ws_handler, "0.0.0.0", 8765):
            await asyncio.Future()

    threading.Thread(target=lambda: asyncio.run(start_ws()), daemon=True).start()

    # On attend un tout petit peu que le thread WS soit prêt
    time.sleep(1.5)
    # Accueil vocal : phrase générée par l'IA (différente à chaque démarrage), dans un
    # thread pour ne pas retarder l'écoute ; phrase de secours si l'IA ne répond pas.
    def _accueil():
        texte = generer_salutation_demarrage()
        if not texte:
            salutation = "Bonjour" if 5 <= time.localtime().tm_hour < 18 else "Bonsoir"
            texte = f"{salutation} {NOM_CREATEUR}. Je suis prêt. Que puis-je faire pour vous ?"
        speech.parler(texte)
    threading.Thread(target=_accueil, daemon=True).start()


    # On lance l'écoute (qui est bloquante dans ce thread)
    ecouter()


# ==========================================
# LANCEMENT — MODE CONSOLE + FRONTEND WEB
# ==========================================
# Ursina desactive : l'interface est maintenant le frontend Three.js
# dans le dossier frontend/ (npm run dev -> http://localhost:5173)
# Le WebSocket est deja demarre par start_ia() sur ws://localhost:8765

def main():
    afficher_statut_services()

    # Initialisation Système d'Alarmes
    set_parler_callback(parler)
    demarrer_daemon_alarmes()

    # Lancement de la découverte TV en arrière-plan (non-bloquant)
    import threading
    # Plus besoin de découverte TV avec le mode ADB Direct

    liberer_ports_occupes()

    frontend_process, FRONTEND_URL = lancer_frontend()

    # Lancer les services en arriere-plan
    threading.Thread(target=start_mobile_http_server, daemon=True).start()
    threading.Thread(target=start_ia, daemon=True).start()

    # Nettoyage automatique du cache WebView2 si version changée
    vider_cache_webview_si_nouvelle_version(shared.CURRENT_VERSION)

    ouvrir_interface(frontend_process, FRONTEND_URL)


if __name__ == "__main__":
    sys.stdout = TeeLogger()
    sys.stderr = sys.stdout
    main()
