"""Moteur de voix ElevenLabs (cloud, payant au-delà de l'offre gratuite) : désactivé tant que le réglage et la clé ne sont pas là.

Activation : ELEVENLABS_API_KEY dans .env (écrite à la main : le HUD ne peut pas l'écrire) ET dans jarvis_config.json :
    "elevenlabs": {"actif": true, "voice_id": "<identifiant d'une voix de ton compte>", "modele": "eleven_multilingual_v2", "stabilite": 0.5}
Chaque phrase dite part chez ElevenLabs (texte envoyé à un tiers) et consomme des crédits : à vérifier sur leur page de tarifs. NON essayé avec un vrai compte.
"""
import json
import os

import requests

from core import voix_registre

_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _config() -> dict:
    try:
        with open(os.path.join(_RACINE, "jarvis_config.json"), encoding="utf-8") as f:
            c = json.load(f).get("elevenlabs") or {}
    except Exception:
        c = {}
    return c if isinstance(c, dict) else {}


def disponible() -> bool:
    c = _config()
    return bool(c.get("actif")) and bool(os.getenv("ELEVENLABS_API_KEY", "").strip()) and bool(str(c.get("voice_id", "")).strip())


def _requete(texte: str, chemin: str) -> str:
    c = _config()
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{c['voice_id']}?output_format=mp3_44100_128",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
        json={"text": texte, "model_id": c.get("modele") or "eleven_multilingual_v2",
              "voice_settings": {"stability": float(c.get("stabilite", 0.5)), "similarity_boost": 0.75}},
        timeout=15)
    if r.status_code != 200 or len(r.content) < 200:
        raise RuntimeError(f"ElevenLabs a répondu {r.status_code}")   # le corps peut citer le compte : jamais journalisé
    with open(chemin, "wb") as f:
        f.write(r.content)
    return chemin


async def synthetiser(texte: str, base: str):
    return await voix_registre.synthese_http(_requete, texte, base + ".mp3")


def enregistrer():
    voix_registre.enregistrer("elevenlabs", 5, disponible, synthetiser)   # priorité 5 : avant edge-tts quand il est activé
