"""Transcription locale (faster-whisper, GPU) : premier palier de core/ecoute_outils.transcribe_audio_groq, Groq puis Google en secours.

Mesuré le 17/11/2026 sur la RTX 4070 Super : 0,15 s par phrase, même texte que Groq, sans quota ni envoi de la voix à un tiers.
Jamais d'exception vers l'appelant : modèle absent, pas de GPU CUDA, mémoire vidéo pleine → None, et JARVIS retombe sur Groq.
Désactivable : "stt_local": false dans jarvis_config.json. Le modèle se charge en tâche de fond (prechauffer) ; tant qu'il n'est pas prêt, Groq répond.
"""
import json
from core import i18n
import os
import threading
import time

import numpy as np

MODELE = "large-v3-turbo"
_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_verrou = threading.Lock()
_modele = None
_hors_service = False   # chargement échoué : on n'essaie plus avant le prochain démarrage


def active() -> bool:
    try:
        with open(os.path.join(_RACINE, "jarvis_config.json"), encoding="utf-8") as f:
            return bool(json.load(f).get("stt_local", True))
    except Exception:
        return True


def _charger():
    """Charge le modèle une fois (CUDA seulement : le gros modèle sur CPU serait plus lent que Groq)."""
    global _modele, _hors_service
    with _verrou:
        if _modele is not None or _hors_service:
            return _modele
        try:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() < 1:
                raise RuntimeError("pas de GPU CUDA")
            from faster_whisper import WhisperModel
            t0 = time.monotonic()
            _modele = WhisperModel(MODELE, device="cuda", compute_type="float16")
            print(f"[STT] Modèle local « {MODELE} » prêt en {time.monotonic() - t0:.1f} s.")
        except Exception as e:
            _hors_service = True
            print(f"[STT] Transcription locale indisponible ({e}) : Groq / Google seulement.")
        return _modele


def prechauffer():
    """À appeler dans un thread au démarrage."""
    if active():
        _charger()


def transcrire(raw_audio_bytes, sample_rate=16000, prompt=None):
    """PCM 16 bits mono -> texte en minuscules, ou None (désactivé, pas prêt, erreur, silence)."""
    if _hors_service or _modele is None or not active():
        return None   # pas prêt : on n'attend pas le chargement, Groq répond
    try:
        a = np.frombuffer(raw_audio_bytes, dtype=np.int16).astype(np.float32) / 32768
        if sample_rate != 16000 and len(a):
            a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * 16000 / sample_rate)), np.arange(len(a)), a).astype(np.float32)
        with _verrou:   # un seul calcul à la fois sur le GPU (écoute normale + transcription d'un « stop »)
            segments, _ = _modele.transcribe(a, language=i18n.stt_whisper(), initial_prompt=prompt or None, condition_on_previous_text=False)
            return " ".join(s.text.strip() for s in segments).strip().lower()   # "" = le modèle a entendu du silence (≠ None : indisponible)
    except Exception as e:
        print(f"[STT] Transcription locale en échec : {e}")
        return None
