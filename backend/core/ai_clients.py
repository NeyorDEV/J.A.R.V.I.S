"""Clés API (.env), clients des moteurs IA (Gemini, Grok, Groq, Claude, Mistral) et rechargement à chaud."""

import builtins
import os

import google.genai as genai
from openai import OpenAI

import core.shared as shared


try:
    import anthropic as _anthropic_lib
except ImportError:
    _anthropic_lib = None

try:
    from mistralai.client import Mistral as _MistralClientClass
except ImportError:
    _MistralClientClass = None

# Validateur universel — une clé non renseignée = placeholder = agent ignoré
_API_PLACEHOLDERS = frozenset({"VOTRE_CLE_ICI", "Votre ID", "votre_id",
                                "VOTRE_TOKEN_ICI", "votre_token_ici", ""})


def _sauvegarder_env(data: dict) -> None:
    """Met à jour le fichier .env et met à jour os.environ en temps réel."""
    env_path = os.path.join(shared.RACINE_PROJET, ".env")
    lines = []
    existing_keys = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for idx, line in enumerate(lines):
            line_strip = line.strip()
            if line_strip and not line_strip.startswith("#") and "=" in line_strip:
                key, _ = line_strip.split("=", 1)
                existing_keys[key.strip()] = idx

    for key, value in data.items():
        os.environ[key] = str(value)
        line_content = f"{key}={value}\n"
        if key in existing_keys:
            lines[existing_keys[key]] = line_content
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            lines.append(line_content)
            existing_keys[key] = len(lines) - 1

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[CONFIG ENV] .env mis à jour avec : {list(data.keys())}")
    except Exception as e:
        print(f"[CONFIG ENV] Erreur écriture .env : {e}")


def recharger_clients_ia():
    from dotenv import load_dotenv
    load_dotenv(override=True)
    
    shared.GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
    shared.YOUTUBE_API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
    shared.XAI_API_KEY       = os.getenv("XAI_API_KEY", "")
    shared.SERPAPI_API_KEY   = os.getenv("SERPAPI_API_KEY", "")
    shared.GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
    shared.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    shared.MISTRAL_API_KEY   = os.getenv("MISTRAL_API_KEY", "")
    
    shared.gemini_actif = _cle_valide(shared.GEMINI_API_KEY)
    
    # Recharger TOUS les clients d'API, pas seulement Gemini.
    # Auparavant grok/groq/anthropic/mistral étaient déclarés `global` mais jamais
    # reconstruits : après avoir changé une clé dans les réglages, l'interface
    # annonçait « sauvegardé » alors que l'ancien client (ou None) restait utilisé
    # jusqu'au redémarrage complet.
    try:
        shared.client = genai.Client(api_key=shared.GEMINI_API_KEY) if shared.gemini_actif else None
        builtins.client = shared.client
        print(f"[IA RELOAD] Gemini : {'rechargé' if shared.client else 'désactivé (clé absente)'}.")
    except Exception as e:
        print(f"[IA RELOAD] Erreur rechargement Gemini : {e}")

    try:
        shared.grok_client = OpenAI(api_key=shared.XAI_API_KEY, base_url="https://api.x.ai/v1") \
            if _cle_valide(shared.XAI_API_KEY) else None
        print(f"[IA RELOAD] Grok : {'rechargé' if shared.grok_client else 'désactivé'}.")
    except Exception as e:
        shared.grok_client = None
        print(f"[IA RELOAD] Erreur rechargement Grok : {e}")

    try:
        shared.groq_client = OpenAI(api_key=shared.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") \
            if _cle_valide(shared.GROQ_API_KEY) else None
        print(f"[IA RELOAD] Groq : {'rechargé' if shared.groq_client else 'désactivé'}.")
    except Exception as e:
        shared.groq_client = None
        print(f"[IA RELOAD] Erreur rechargement Groq : {e}")

    try:
        shared.anthropic_client = _anthropic_lib.Anthropic(api_key=shared.ANTHROPIC_API_KEY) \
            if (_anthropic_lib and _cle_valide(shared.ANTHROPIC_API_KEY)) else None
        print(f"[IA RELOAD] Claude : {'rechargé' if shared.anthropic_client else 'désactivé'}.")
    except Exception as e:
        shared.anthropic_client = None
        print(f"[IA RELOAD] Erreur rechargement Claude : {e}")

    try:
        shared.mistral_client = _MistralClientClass(api_key=shared.MISTRAL_API_KEY) \
            if (_MistralClientClass and _cle_valide(shared.MISTRAL_API_KEY)) else None
        print(f"[IA RELOAD] Mistral : {'rechargé' if shared.mistral_client else 'désactivé'}.")
    except Exception as e:
        shared.mistral_client = None
        print(f"[IA RELOAD] Erreur rechargement Mistral : {e}")


def _cle_valide(key):
    return bool(key) and str(key).strip() not in _API_PLACEHOLDERS


builtins._cle_valide = _cle_valide


def initialiser_cles_et_clients():
    """Lit les clés API (.env), crée les clients des moteurs IA et les expose via builtins (démarrage)."""
    shared.GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")
    shared.YOUTUBE_API_KEY      = os.getenv("YOUTUBE_API_KEY")
    shared.XAI_API_KEY          = os.getenv("XAI_API_KEY")
    shared.SERPAPI_API_KEY      = os.getenv("SERPAPI_API_KEY")
    shared.GROQ_API_KEY         = os.getenv("GROQ_API_KEY")
    shared.ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
    shared.MISTRAL_API_KEY      = os.getenv("MISTRAL_API_KEY", "")
    SPOTIFY_MUSIQUE_URI  = os.getenv("SPOTIFY_MUSIQUE_URI", "")
    builtins.SPOTIFY_MUSIQUE_URI = SPOTIFY_MUSIQUE_URI
    shared.YOUTUBE_MUSIQUE_URL  = os.getenv("YOUTUBE_MUSIQUE_URL", "")
    builtins.YOUTUBE_MUSIQUE_URL = shared.YOUTUBE_MUSIQUE_URL

    shared.gemini_actif    = _cle_valide(shared.GEMINI_API_KEY)
    # Utilisation du client Gemini (supporte .aio pour l'asynchrone natif)
    shared.client          = genai.Client(api_key=shared.GEMINI_API_KEY) if shared.gemini_actif else None

    # Client Grok (xAI)
    shared.grok_client     = None
    if _cle_valide(shared.XAI_API_KEY):
        shared.grok_client = OpenAI(api_key=shared.XAI_API_KEY, base_url="https://api.x.ai/v1")

    # Client Groq (Llama 3.3)
    shared.groq_client     = None
    if _cle_valide(shared.GROQ_API_KEY):
        shared.groq_client = OpenAI(api_key=shared.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

    # Client Claude (Anthropic) — agent principal
    shared.anthropic_client = None
    if _anthropic_lib and _cle_valide(shared.ANTHROPIC_API_KEY):
        shared.anthropic_client = _anthropic_lib.Anthropic(api_key=shared.ANTHROPIC_API_KEY)

    # Client Mistral (modèle souverain français) — priorité 3, après Groq/Claude
    shared.mistral_client = None
    if _MistralClientClass and _cle_valide(shared.MISTRAL_API_KEY):
        shared.mistral_client = _MistralClientClass(api_key=shared.MISTRAL_API_KEY)

    CHOSEN_MODEL    = shared.MODELS_LIST[0]
    builtins.client = shared.client
    builtins.CHOSEN_MODEL = CHOSEN_MODEL
