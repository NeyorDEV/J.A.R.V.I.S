import os
import builtins
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# --- VERSION ---
CURRENT_VERSION = "9.5.0"

# --- CLÉS API ---
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY")
XAI_API_KEY          = os.getenv("XAI_API_KEY")
SERPAPI_API_KEY      = os.getenv("SERPAPI_API_KEY")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")

_API_PLACEHOLDERS = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", "votre_token_ici", ""})

def cle_utilisable(key):
    return bool(key) and str(key).strip() not in _API_PLACEHOLDERS

# --- CONFIGURATION IA ---
MODELS_LIST     = ["gemini-3.8-flash", "gemini-3.7-flash","gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"]
CHOSEN_MODEL    = MODELS_LIST[0]

# --- CONFIGURATION VOIX ---
VOIX_ACTUELLE = "homme" # "homme" ou "femme"
try:  # voix choisie dans l'assistant de premier lancement (jarvis_config.json, clé « voix_jarvis »)
    import json as _json
    _chemin = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "jarvis_config.json")
    with open(_chemin, encoding="utf-8") as _f:
        _voix = _json.load(_f).get("voix_jarvis")
    if _voix in ("homme", "femme"):
        VOIX_ACTUELLE = _voix
except Exception:
    pass

# --- CONSTANTES ---
SESSION_TIMEOUT = 30
WAKE_WORD = "jarvis"

# Exportation vers builtins pour compatibilité descendante immédiate
builtins.cle_utilisable = cle_utilisable
builtins.CHOSEN_MODEL = CHOSEN_MODEL
builtins.MODELS_LIST = MODELS_LIST

# --- SINGLE POINT OF TRUTH BROWSER (MONKEY PATCH WEBBROWSER FOR OPERA GX) ---
import webbrowser
import subprocess

_original_open = webbrowser.open

def _custom_open(url, *args, **kwargs):
    # Opera GX, s'il est installé pour l'utilisateur courant
    opera_gx_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Opera GX", "opera.exe")
    if os.path.exists(opera_gx_path):
        try:
            # Lancement direct via subprocess pour forcer le bon navigateur
            subprocess.Popen([opera_gx_path, url])
            return True
        except Exception as e:
            print(f"[NAVIGATEUR] Erreur de lancement Opera GX : {e}")
    # Fallback standard si Opera GX n'est pas installé ou indisponible
    return _original_open(url, *args, **kwargs)

webbrowser.open = _custom_open
