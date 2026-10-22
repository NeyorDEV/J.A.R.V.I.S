"""État partagé de JARVIS entre main.py et les modules du backend.

Ces valeurs étaient auparavant des variables globales de main.py. Elles vivent
ici pour que tous les modules lisent et modifient le MÊME état : on y accède
toujours via `shared.NOM` (jamais `from core.shared import NOM`, qui copierait
la valeur au moment de l'import et ne verrait plus les mises à jour).

Les valeurs ci-dessous sont celles en vigueur à la fin de l'initialisation de
main.py ; celles calculées au démarrage (clients IA, modèles VAD, historique...)
y sont affectées par main.py et core/ai_clients.py.
"""

import asyncio
import os
import threading

# Racine du projet (dossier contenant main.py) : backend/core/ -> backend/ -> racine
RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Traitement des commandes ─────────────────────────────────────────────────
traiter_lock = asyncio.Lock()
historique = []                     # remplacé au démarrage par l'historique récent
_derniere_reponse_streamed = False
phrases_streamed = []
is_thinking = False
_USE_LLM_INTENT = True              # Dispatch d'intentions par function calling Gemini (fallback resolvers)
MODE_IRON_MAN = False
VOIX_ACTUELLE = "homme"             # "homme" ou "femme"
attente_nom_dossier = False
attente_nom_app = False

# ── Session vocale / micro ───────────────────────────────────────────────────
WAKE_WORD = "jarvis"
SESSION_TIMEOUT = 20.0
jarvis_actif = False
dernier_message = 0
dernier_parle_time = 0
STOP_PARLER = False
is_listening = False
is_speaking = False
MIC_MUTED = False
MIC_NEED_RELOAD = False
CLAP_THRESHOLD = 1200

# ── Modèles audio (affectés par core/voice_init.py) ──────────────────────────
VAD_MODEL = None
VOICE_BIOMETRICS = None
ACTIVE_SPEAKER = "neyor"
# Globe 3D affiché ? (signalé par le frontend, message « globe_state ») — sert au zoom vocal
GLOBE_VISIBLE = False
SPEAKER_ANNOUNCED = None
DERNIER_LOCUTEUR = None   # (profil, instant) de la dernière voix reconnue (core/ecoute.py)
ETAT_HUD = None            # dernier état envoyé au HUD : idle / listening / thinking / speaking
MUSIQUE_EN_COURS = None    # {"title", "artist", "status"} du morceau Deezer (weather_music_service)
ENROLEMENT_CLAVIER = False  # « enregistre ma voix » tapé au clavier du HUD → enrôlement du créateur

# ── Clés API et clients des moteurs IA (affectés par core/ai_clients.py) ─────
GEMINI_API_KEY = None
YOUTUBE_API_KEY = None
XAI_API_KEY = None
SERPAPI_API_KEY = None
GROQ_API_KEY = None
ANTHROPIC_API_KEY = None
MISTRAL_API_KEY = None
YOUTUBE_MUSIQUE_URL = ""
gemini_actif = False
client = None
grok_client = None
groq_client = None
anthropic_client = None
mistral_client = None
MODELS_LIST = [
    "gemini-3.5-flash-lite",   # Rapide, parfait pour usage vocal (succède à 3.1-flash-lite)
    "gemini-3.8-flash",        # Fallback puissant — le Flash le plus récent (meilleur que 3.7, même délai)
    "gemini-flash-latest",
    "gemini-pro-latest",
]
# Ollama (LLMs locaux — fallback 100% offline)
OLLAMA_URL = "http://127.0.0.1:11434"
# Mesuré sur RTX 4070 Super (12 Go) : gemma4:12b = meilleur français, 1re phrase ~2 s ;
# gemma4 (e4b) en secours = ~1 s, chargement 14 s au lieu de 45 s
OLLAMA_MODELS = ["gemma4:12b", "gemma4:latest"]

# ── WebSocket / interface ────────────────────────────────────────────────────
WS_LOOP = None
CONNECTED_CLIENTS = set()
CLIENTS_EXTENSION = set()           # connexions de l'extension Chrome (pas des HUD)
interface_deja_connectee = False
PENDING_SCREEN_CAPTURES = {}
BACKGROUND_TASKS = set()
_WEBVIEW_WINDOW = None
# Passer à True si WebView2 est définitivement cassé sur votre système
FORCE_BROWSER_MODE = False
# Version utilisée pour l'invalidation du cache WebView2
CURRENT_VERSION = "9.5.0"

# ── Divers ───────────────────────────────────────────────────────────────────
_plugins_prets = threading.Event()  # levé quand tous les plugins sont importés
browser_agent = None                # AutonomousBrowser, créé au démarrage
psutil = None                       # module psutil (importé au démarrage s'il est installé)
CLIENT_LOCATION = None              # dict partagé avec module.weather_music_service
CHESS_GAME = None
CHESS_GAME_ACTIVE = False
AV_LIVE_PROTECTION_ENABLED = False
AV_LIVE_REPORTED_THREATS = set()

# --- SIMULATION PROTOCOLE DOMOTIQUE (Maison de neyor) ---
SIMULATED_DOMOTIC_STATES = {
    # Lumières (1er Étage)
    "light.salon": "off",
    "light.plafond": "off",
    "light.canapes": "off",
    "light.lampadaire": "off",
    "light.lampe_de_chevet_2": "off",
    "light.grosse_boule": "off",
    "light.petite_boule": "off",
    "light.lsc_smart_led_strip_rgbic_cctic_5m": "off", # cuisine
    "light.cuisine_2": "off",
    "light.bureau": "off",
    "light.pc": "off",
    "light.pc_2": "off",
    "light.chambre_parentale": "off",
    "light.plafond_2": "off",

    # Prises (1er Étage)
    "switch.prise_salon": "off",
    "switch.prise_bureau": "off",
    "switch.prise_cuisine": "off",

    # Entités ajoutées plus tard
    "light.veranda": "off",
    "light.sdb_parents": "off",
    "light.garage": "off",
    "light.couloir": "off",
    "light.chambre_1": "off",
    "light.chambre_2": "off",
    "light.toilettes": "off",
    "light.sdb": "off",

    # Capteurs de Températures
    "temp.salon": 20.5,
    "temp.cuisine": 21.2,
    "temp.parents": 19.8,
    "temp.veranda": 16.8,
    "temp.garage": 14.5,
    "temp.couloir": 19.5,
    "temp.chambre_1": 20.0,
    "temp.chambre_2": 20.2,
    "temp.sdb": 22.5,

    # Lecteurs Audio (HomePods)
    "media_player.homepod_salon": "playing",
    "media_player.homepod_chambre": "paused",
}
