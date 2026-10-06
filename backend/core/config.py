import os
import builtins
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# --- VERSION ---
CURRENT_VERSION = "8.9.5"

# --- RÉSEAU ---
def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# --- CLÉS API ---
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY")
XAI_API_KEY          = os.getenv("XAI_API_KEY")
SERPAPI_API_KEY      = os.getenv("SERPAPI_API_KEY")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")
ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")

_API_PLACEHOLDERS = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id", "VOTRE_TOKEN_ICI", "votre_token_ici", ""})

def _cle_valide(key):
    return bool(key) and str(key).strip() not in _API_PLACEHOLDERS

# --- CONFIGURATION IA ---
MODELS_LIST     = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-flash-latest", "gemini-pro-latest"]
CHOSEN_MODEL    = MODELS_LIST[0]

# --- CONFIGURATION VOIX ---
VOIX_ACTUELLE = "homme" # "homme" ou "femme"

# --- CONSTANTES ---
SESSION_TIMEOUT = 30
WAKE_WORD = "jarvis"
_skip_pc_audio = False

# Exportation vers builtins pour compatibilité descendante immédiate
builtins._cle_valide = _cle_valide
builtins.CHOSEN_MODEL = CHOSEN_MODEL
builtins.MODELS_LIST = MODELS_LIST

# --- SINGLE POINT OF TRUTH BROWSER (MONKEY PATCH WEBBROWSER FOR OPERA GX) ---
import webbrowser
import subprocess

_original_open = webbrowser.open

def _custom_open(url, *args, **kwargs):
    # Chemin détecté de l'exécutable Opera GX sur le PC de neyor
    opera_gx_path = r"C:\Users\mylan\AppData\Local\Programs\Opera GX\opera.exe"
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
