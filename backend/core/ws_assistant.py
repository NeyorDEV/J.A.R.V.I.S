"""Assistant de premier lancement (HUD) : état de la configuration et test d'une clé d'IA sans l'enregistrer.

Messages (frontend -> backend) :
  {"type": "get_setup_state"}                                  -> {"type": "setup_state", ...}
  {"type": "setup_test_key", "moteur": "gemini|groq|mistral", "cle": "..."} -> {"type": "setup_key_result", ...}

L'enregistrement (clés dans .env, prénom, voix, micro) passe par « update_settings » (core/ws_reglages.py).
Une clé n'est jamais renvoyée au frontend ni écrite dans les journaux.
"""

import asyncio
import json
import os
import time

import core.shared as shared
from core.ai_clients import cle_utilisable

_CLES_MOTEURS = ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "XAI_API_KEY")


def _config():
    try:
        with open(os.path.join(shared.RACINE_PROJET, "jarvis_config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def etat_assistant():
    cfg = _config()
    utilisables = {c: cle_utilisable(os.getenv(c, "")) for c in _CLES_MOTEURS}
    try:
        from core.config import VOIX_ACTUELLE
    except Exception:
        VOIX_ACTUELLE = "homme"
    return {
        "type": "setup_state",
        # À ouvrir si JARVIS ne peut répondre avec aucun moteur et que l'assistant n'a pas été terminé (ou si JARVIS_ASSISTANT_FORCE=1, pour les essais)
        "besoin": os.getenv("JARVIS_ASSISTANT_FORCE", "") == "1"
        or (not any(utilisables.values()) and not cfg.get("assistant_termine", False)),
        "nom": cfg.get("user_name", ""),
        "voix": VOIX_ACTUELLE,
        "cles": {c: ok for c, ok in utilisables.items()},
    }


async def ws_get_setup_state(websocket, data=None):
    await websocket.send(json.dumps(etat_assistant(), ensure_ascii=False))


def _tester_cle(moteur, cle):
    """(ok, détail, secondes). Requête minuscule avec une clé fournie, sans toucher aux clients de JARVIS."""
    t0 = time.time()
    cle = (cle or "").strip()
    if not cle_utilisable(cle) or len(cle) < 12:
        return False, "clé vide ou trop courte", 0.0
    try:
        if moteur == "gemini":
            from google import genai
            client = genai.Client(api_key=cle)
            derniere = None
            for modele in list(shared.MODELS_LIST)[:3]:
                try:
                    r = client.models.generate_content(model=modele, contents="Réponds juste : ok")
                    if getattr(r, "text", ""):
                        return True, modele, time.time() - t0
                except Exception as e:  # modèle indisponible : on essaie le suivant ; clé refusée : on s'arrête
                    derniere = e
                    if any(k in str(e).lower() for k in ("api key", "api_key", "permission", "unauthenticated", "401", "403")):
                        break
            raise derniere or RuntimeError("aucune réponse")
        if moteur == "groq":
            from openai import OpenAI
            OpenAI(api_key=cle, base_url="https://api.groq.com/openai/v1", max_retries=0).chat.completions.create(
                model="openai/gpt-oss-120b", messages=[{"role": "user", "content": "ok"}], max_tokens=300)
            return True, "gpt-oss-120b", time.time() - t0
        if moteur == "mistral":
            from mistralai.client import Mistral
            Mistral(api_key=cle).chat.complete(model="ministral-8b-latest", messages=[{"role": "user", "content": "ok"}], max_tokens=5)
            return True, "ministral-8b", time.time() - t0
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("api key", "api_key", "unauthorized", "401", "403", "invalid", "permission")):
            return False, "clé refusée par le service", time.time() - t0
        if any(k in msg for k in ("429", "quota", "rate", "limit")):
            return True, "clé valide (quota momentanément atteint)", time.time() - t0
        return False, f"{type(e).__name__} : connexion impossible ?", time.time() - t0
    return False, "moteur inconnu", 0.0


async def ws_setup_test_key(websocket, data):
    moteur = (data or {}).get("moteur", "")
    boucle = asyncio.get_running_loop()
    ok, detail, duree = await boucle.run_in_executor(None, _tester_cle, moteur, (data or {}).get("cle", ""))
    await websocket.send(json.dumps({"type": "setup_key_result", "moteur": moteur, "ok": ok, "detail": detail,
                                     "duree": round(duree, 2)}, ensure_ascii=False))
