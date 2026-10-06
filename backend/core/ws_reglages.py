"""Messages WebSocket de la page Paramètres (lecture/écriture de la configuration)."""

import json
import os

import core.shared as shared
from core.ai_clients import _cle_valide, recharger_clients_ia, _sauvegarder_env


# Sentinelle renvoyée à la place des vraies clés API : l'interface affiche que la
# clé existe sans jamais recevoir sa valeur. Si elle nous la renvoie telle quelle
# lors d'une sauvegarde, cela signifie « inchangée » et on conserve l'existante.
_MASQUE_CLE = "••••••••••••"


def _masquer_cle(valeur: str) -> str:
    if not valeur:
        return ""
    return _MASQUE_CLE + (valeur[-4:] if len(valeur) > 8 else "")


async def ws_get_settings(websocket, data):
    """Message WS « get_settings » : envoie la config (clés API masquées) et la liste des micros."""
    import json as _j
    try:
        _p = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
        with open(_p, "r", encoding="utf-8") as _f:
            config_data = _j.load(_f)
    except Exception:
        config_data = {}

    # Clés API : on n'envoie JAMAIS leur valeur réelle sur le
    # WebSocket, seulement un masque indiquant qu'elles existent.
    # (Auparavant un simple message suffisait à toutes les voler.)
    config_data["api_keys"] = {
        nom: _masquer_cle(os.getenv(nom, ""))
        for nom in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
                    "YOUTUBE_API_KEY", "XAI_API_KEY", "SERPAPI_API_KEY",
                    "ANTHROPIC_API_KEY", "MISTRAL_API_KEY")
    }
    # État d'activation des API
    config_data["api_gemini_enabled"] = config_data.get("api_gemini_enabled", _cle_valide(os.getenv("GEMINI_API_KEY")))
    config_data["api_groq_enabled"] = config_data.get("api_groq_enabled", _cle_valide(os.getenv("GROQ_API_KEY")))
    config_data["api_youtube_enabled"] = config_data.get("api_youtube_enabled", _cle_valide(os.getenv("YOUTUBE_API_KEY")))
    config_data["api_grok_enabled"] = config_data.get("api_grok_enabled", _cle_valide(os.getenv("XAI_API_KEY")))
    config_data["api_serpapi_enabled"] = config_data.get("api_serpapi_enabled", _cle_valide(os.getenv("SERPAPI_API_KEY")))
    config_data["api_anthropic_enabled"] = config_data.get("api_anthropic_enabled", _cle_valide(os.getenv("ANTHROPIC_API_KEY")))
    config_data["api_mistral_enabled"] = config_data.get("api_mistral_enabled", _cle_valide(os.getenv("MISTRAL_API_KEY")))

    # Charger la liste des micros réels via pyaudio — même logique que detecter_microphone()
    mic_list = []
    try:
        import pyaudio as _py, re as _re
        _pya = _py.PyAudio()
        _raw = []
        for _i in range(_pya.get_device_count()):
            try:
                _info = _pya.get_device_info_by_index(_i)
                if _info.get("maxInputChannels", 0) > 0:
                    _nom = _info.get("name", f"Micro {_i}")
                    _nom_low = _nom.lower().strip()
                    _exclus = ["mappeur de sons", "capture audio principal", "mixage", "stereo mix", "ivcam", "entrée ligne", "line input", "realtek hd audio mic input"]
                    if any(x in _nom_low for x in _exclus):
                        continue
                    _propre = _re.sub(r'\d+-\s*', '', _nom)
                    _propre = _re.sub(r'sur casque', '', _propre, flags=_re.IGNORECASE)
                    _propre = _propre.replace("Headset Microphone", "Microphone")
                    _propre = _re.sub(r'\(\s*\)', '', _propre)
                    _propre = _re.sub(r'\s+', ' ', _propre).strip()
                    if _propre.lower() in ["microphone", ""]:
                        continue
                    _raw.append({"index": _i, "clean_name": _propre})
            except: pass
        _pya.terminate()
        # Déduplication par longueur décroissante
        _raw.sort(key=lambda d: len(d["clean_name"]), reverse=True)
        _seen = set()
        _filtered = []
        for _dev in _raw:
            _nl = _dev["clean_name"].lower()
            if not any(_nl in _s or _s.startswith(_nl) for _s in _seen):
                _seen.add(_nl)
                _filtered.append(_dev)
        _filtered.sort(key=lambda d: d["index"])
        mic_list = [{"index": d["index"], "name": d["clean_name"]} for d in _filtered]
    except: pass
    config_data["mic_list"] = mic_list

    await websocket.send(json.dumps({"type": "settings_data", "data": config_data}))


async def ws_update_settings(websocket, data):
    """Message WS « update_settings » : sauvegarde les réglages et recharge ce qui en dépend."""
    settings = data.get("settings", {})
    import json as _j
    _p = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            config_data = _j.load(_f)
    except Exception:
        config_data = {}
    old_mic_index = config_data.get("mic_device_index")

    # Séparer les clés d'API pour les enregistrer dans le fichier .env
    if "api_keys" in settings:
        api_keys = settings.pop("api_keys")
        # On ignore les clés renvoyées masquées : elles signifient
        # « inchangée ». Sans ce filtre, ouvrir puis sauvegarder les
        # réglages écrasait les vraies clés par la chaîne de masque.
        api_keys = {
            k: v for k, v in (api_keys or {}).items()
            if isinstance(v, str) and _MASQUE_CLE not in v
        }
        if api_keys:
            # Mettre à jour le fichier .env
            _sauvegarder_env(api_keys)
            # Recharger les variables et réinitialiser les clients d'IA à chaud
            recharger_clients_ia()

    config_data.update(settings)
    with open(_p, "w", encoding="utf-8") as _f:
        _j.dump(config_data, _f, ensure_ascii=False, indent=4)
    if "mic_device_index" in settings and settings["mic_device_index"] != old_mic_index:
        shared.MIC_NEED_RELOAD = True
    if "av_live_protection" in settings:
        shared.AV_LIVE_PROTECTION_ENABLED = settings["av_live_protection"]
    # Recharger l'identité globalement
    import builtins
    builtins.USER_NAME = config_data.get("user_name", "neyor")
    builtins.USER_AGE = config_data.get("user_age", "37")

    # Recharger les apps personnalisées
    try:
        from controller.app_launcher import _charger_custom_apps
        _charger_custom_apps()
    except: pass
    print("[WEB] Parametres mis a jour avec succes.")
