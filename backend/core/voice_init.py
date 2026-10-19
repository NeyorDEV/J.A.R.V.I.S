"""Initialisation des modèles audio au démarrage : Silero VAD, biométrie vocale."""

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


def charger_options_config():
    """Lit jarvis_config.json pour les options globales de traitement (dispatch d'intentions LLM)."""
    try:
        import json
        chemin = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
        cfg = {}
        if os.path.exists(chemin):
            with open(chemin, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        shared._USE_LLM_INTENT = bool(cfg.get("use_llm_intent", True))
    except Exception:
        pass
