"""Initialisation des modèles audio au démarrage : Silero VAD, biométrie vocale et openWakeWord."""

import builtins
import os

import core.shared as shared


def initialiser_vad_biometrie():
    """Charge Silero VAD et la biométrie vocale ; fixe le locuteur initial (guest si des empreintes existent)."""
    builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER

    try:
        from core.vad import init_models, SileroVAD, SpeakerBiometrics, VAD_MODEL_PATH, SPEAKER_MODEL_PATH, VOICEPRINTS_DIR
        init_models()

        cfg_vad = {}
        try:
            config_path = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
            if os.path.exists(config_path):
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg_vad = json.load(f)
        except Exception:
            pass

        if os.path.exists(VAD_MODEL_PATH) and cfg_vad.get("use_silero_vad", True):
            shared.VAD_MODEL = SileroVAD(VAD_MODEL_PATH)
            print("✔  [VAD] Silero VAD initialisé avec succès.")
        else:
            shared.VAD_MODEL = None
            print("ℹ  [VAD] Silero VAD désactivé (mode repli sur l'énergie VAD par défaut).")
        if os.path.exists(SPEAKER_MODEL_PATH):
            shared.VOICE_BIOMETRICS = SpeakerBiometrics(SPEAKER_MODEL_PATH, VOICEPRINTS_DIR)
            print("✔  [BIOMETRICS] Biométrie vocale initialisée avec succès.")
            voiceprints = shared.VOICE_BIOMETRICS.load_voiceprints()
            if voiceprints:
                shared.ACTIVE_SPEAKER = "guest"
                builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER
                print(f"🎙  [BIOMETRICS] Empreintes chargées : {list(voiceprints.keys())}. Mode initial : guest")
            else:
                shared.ACTIVE_SPEAKER = "neyor"
                builtins.ACTIVE_SPEAKER = shared.ACTIVE_SPEAKER
                print("🎙  [BIOMETRICS] Aucune empreinte vocale trouvée. Mode par défaut : neyor")
    except Exception as e:
        print(f"❌  [VAD/BIOMETRICS] Erreur lors de l'initialisation : {e}")


def initialiser_wakeword():
    """Charge openWakeWord (détection locale du mot de réveil) selon jarvis_config.json."""
    try:
        _cfg_ww = {}
        try:
            import json as _json_ww
            _cfg_ww_path = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
            if os.path.exists(_cfg_ww_path):
                with open(_cfg_ww_path, "r", encoding="utf-8") as f:
                    _cfg_ww = _json_ww.load(f)
        except Exception:
            pass

        shared._USE_LLM_INTENT = bool(_cfg_ww.get("use_llm_intent", True))

        if _cfg_ww.get("use_openwakeword", True):
            from core.wakeword import init_wakeword, WakeWordDetector
            init_wakeword()
            shared.WAKEWORD_MODEL = WakeWordDetector()
            shared.WAKEWORD_THRESHOLD = float(_cfg_ww.get("wakeword_threshold", 0.35))
            _ww_nom = next(iter(shared.WAKEWORD_MODEL.model.models), "?")
            print(f"✔  [WAKEWORD] openWakeWord '{_ww_nom}' initialisé (seuil {shared.WAKEWORD_THRESHOLD}). Le STT n'est appelé qu'après détection locale.")    
        else:
            print("ℹ  [WAKEWORD] openWakeWord désactivé via config (use_openwakeword=false).")
    except Exception as e:
        shared.WAKEWORD_MODEL = None
        print(f"ℹ  [WAKEWORD] openWakeWord indisponible ({e}). Comportement historique : STT sur chaque phrase.")
