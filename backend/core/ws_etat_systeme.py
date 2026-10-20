"""État du système pour le HUD : moteurs d'IA, voix, services, ressources, et tests à la demande.

Messages (frontend -> backend) :
  {"type": "get_system_status"}                  -> {"type": "system_status", ...}
  {"type": "system_test", "cible": "all|micro|<moteur>"} -> {"type": "system_test_result", ...}

Les tests n'ont aucun effet sur le PC : ils envoient des requêtes minuscules aux moteurs d'IA
(quelques jetons) et écoutent le micro 1,5 s sans rien enregistrer.
"""

import asyncio
import json
import os
import sys
import time

import core.shared as shared


def _console():
    mod = sys.modules.get("core.console_ui")
    return getattr(mod, "_CONSOLE", None) if mod else None


def _pause(cle):
    try:
        from core.api_quota import _quota_mgr
        return _quota_mgr.pause_restante(cle)
    except Exception:
        return 0


def _moteurs():
    c = _console()
    dernier = (c.moteur or "") if c else ""
    liste = []

    gem_cles = []
    try:
        from core.api_quota import _quota_mgr
        gem_cles = [k for k in list(_quota_mgr._cooldowns) if k.startswith("gemini")]
    except Exception:
        pass
    gem_pause = max([_pause(k) for k in gem_cles] or [0])
    gem_ok = bool(getattr(shared, "client", None))
    liste.append({"id": "gemini", "nom": "Gemini", "detail": dernier if dernier.startswith("Gemini") else "",
                  "etat": "absent" if not gem_ok else "pause" if gem_pause else "actif" if dernier.startswith("Gemini") else "pret",
                  "pause": gem_pause})

    try:
        from core.llm_registry import _engines
        for e in _engines:
            ok = bool(e.is_configured())
            pause = _pause(e.name)
            actif = bool(dernier) and e.label.split(" ")[0] in dernier
            liste.append({"id": e.name, "nom": e.label.split(" (")[0],
                          "detail": e.label[e.label.find("(") + 1:-1] if "(" in e.label else "",
                          "etat": "absent" if not ok else "pause" if pause else "actif" if actif else "pret",
                          "pause": pause})
    except Exception:
        pass

    grok = bool(getattr(shared, "grok_client", None))
    liste.append({"id": "grok", "nom": "Grok", "detail": "", "pause": _pause("grok"),
                  "etat": "absent" if not grok else "pause" if _pause("grok") else "pret"})
    ollama = c.ollama if c else None
    liste.append({"id": "ollama", "nom": "Ollama (local)", "detail": ollama or "", "pause": 0,
                  "etat": "libre" if not ollama else "actif"})
    return liste


def _ressources():
    res = {"cpu": None, "ram": None, "gpu": None, "vram": None, "vram_go": None}
    try:
        import psutil
        res["cpu"] = psutil.cpu_percent(None)
        res["ram"] = psutil.virtual_memory().percent
    except Exception:
        pass
    c = _console()
    if c and c.gpu:
        res["gpu"], res["vram"] = c.gpu
    return res


def collecter_etat():
    c = _console()
    clients = getattr(shared, "CONNECTED_CLIENTS", set()) - getattr(shared, "CLIENTS_EXTENSION", set())
    audio = sys.modules.get("core.audio_stream")
    muet = bool(getattr(shared, "MIC_MUTED", False))
    voix = c.voix if c and c.voix and time.time() - c.voix[2] < 600 else None
    try:
        from core.config import VOIX_ACTUELLE
        tts = "edge-tts · " + ("Henri" if VOIX_ACTUELLE == "homme" else "Denise")
    except Exception:
        tts = "edge-tts"
    souvenirs = None
    try:
        vm = sys.modules.get("module.vector_memory")
        if vm and getattr(vm, "_collection", None):
            souvenirs = vm._collection.count()
    except Exception:
        pass
    musique = getattr(shared, "MUSIQUE_EN_COURS", None) or {}
    return {
        "type": "system_status",
        "t": time.time(),
        "version": getattr(shared, "CURRENT_VERSION", ""),
        "moteurs": _moteurs(),
        "voix": {
            "micro": (c.micro_nom if c and c.micro_nom else None),
            "muet": muet,
            "niveau": 0.0 if muet else float(getattr(audio, "NIVEAU_MICRO", 0.0) or 0.0),
            "etat": "muet" if muet else "parle" if getattr(shared, "ETAT_HUD", "") == "speaking"
            else "reflechit" if getattr(shared, "is_thinking", False) else "ecoute" if getattr(shared, "jarvis_actif", False) else "veille",
            "locuteur": {"nom": voix[0], "score": voix[1]} if voix else None,
            "mot_eveil": "jarvis",
            "synthese": tts,
        },
        "services": {
            "interfaces": len(clients),
            "souvenirs": souvenirs,
            "home_assistant": bool(os.getenv("HA_URL", "").strip() and os.getenv("HA_TOKEN", "").strip()),
            "antivirus": bool(getattr(shared, "AV_LIVE_PROTECTION_ENABLED", False)),
            "musique": musique.get("status") or "Stopped",
            "alarme": c.alarme if c else None,
        },
        "ressources": _ressources(),
    }


async def ws_get_system_status(websocket, data=None):
    await websocket.send(json.dumps(collecter_etat(), ensure_ascii=False))


# ── Tests ────────────────────────────────────────────────────────────────────
def _tester_moteur(mid):
    """(ok, détail, secondes) — requête minuscule ; bloquant, à lancer dans un thread."""
    t0 = time.time()
    try:
        if mid == "gemini":
            cli = getattr(shared, "client", None)
            if not cli:
                return False, "clé absente ou moteur désactivé", 0.0
            r = cli.models.generate_content(model=shared.MODELS_LIST[0], contents="Réponds juste : ok")
            return bool(getattr(r, "text", "")), shared.MODELS_LIST[0], time.time() - t0
        if mid == "groq":
            cli = getattr(shared, "groq_client", None)
            if not cli:
                return False, "clé absente ou moteur désactivé", 0.0
            cli.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": "ok"}],
                                        max_tokens=300)
            return True, "gpt-oss-120b", time.time() - t0
        if mid == "mistral":
            cli = getattr(shared, "mistral_client", None)
            if not cli:
                return False, "clé absente ou moteur désactivé", 0.0
            cli.chat.complete(model="ministral-8b-latest", messages=[{"role": "user", "content": "ok"}], max_tokens=5)
            return True, "ministral-8b", time.time() - t0
        if mid == "claude":
            cli = getattr(shared, "anthropic_client", None)
            if not cli:
                return False, "clé absente ou moteur désactivé", 0.0
            cli.messages.create(model="claude-sonnet-5", max_tokens=5, messages=[{"role": "user", "content": "ok"}])
            return True, "claude-sonnet-5", time.time() - t0
        if mid == "grok":
            cli = getattr(shared, "grok_client", None)
            if not cli:
                return False, "clé absente ou moteur désactivé", 0.0
            cli.chat.completions.create(model="grok-4.6", messages=[{"role": "user", "content": "ok"}], max_tokens=5)
            return True, "grok-4.6", time.time() - t0
        if mid == "ollama":
            import urllib.request
            with urllib.request.urlopen(shared.OLLAMA_URL + "/api/tags", timeout=2) as r:
                n = len(json.load(r).get("models", []))
            return True, f"{n} modèle{'s' if n > 1 else ''} installé{'s' if n > 1 else ''}", time.time() - t0
    except Exception as e:
        msg = str(e)
        quota = any(k in msg.lower() for k in ("429", "quota", "rate", "limit"))
        return False, ("quota atteint" if quota else f"{type(e).__name__}: {msg[:80]}"), time.time() - t0
    return False, "moteur inconnu", 0.0


def _tester_micro():
    """Écoute le niveau du micro pendant 1,5 s (aucun enregistrement)."""
    audio = sys.modules.get("core.audio_stream")
    if getattr(shared, "MIC_MUTED", False):
        return False, "micro coupé", 0.0
    if audio is None:
        return False, "flux audio non démarré", 0.0
    mesures = []
    t0 = time.time()
    while time.time() - t0 < 1.5:
        mesures.append(float(getattr(audio, "NIVEAU_MICRO", 0.0) or 0.0))
        time.sleep(0.05)
    pic = max(mesures or [0.0])
    if pic <= 0.0:
        return False, "aucun signal (micro débranché ?)", time.time() - t0
    return True, f"signal reçu · pic {pic * 100:.0f} %", time.time() - t0


async def ws_system_test(websocket, data):
    cible = (data or {}).get("cible", "all")
    ids = [m["id"] for m in _moteurs() if m["etat"] != "absent"] if cible == "all" else [cible]
    boucle = asyncio.get_running_loop()
    if cible in ("all", "micro"):
        ids = ids + ["micro"] if cible == "all" else ["micro"]
    for mid in ids:
        if mid in ("groq", "mistral", "claude", "grok", "gemini") and _pause(mid if mid != "gemini" else "gemini") > 0:
            resultat = (False, "en pause (quota)", 0.0)
        elif mid == "micro":
            resultat = await boucle.run_in_executor(None, _tester_micro)
        elif mid == "voix":
            from core.speech import parler
            parler("Test de la synthèse vocale : je vous entends et vous m'entendez.")
            resultat = (True, "phrase envoyée à la synthèse vocale", 0.0)
        else:
            resultat = await boucle.run_in_executor(None, _tester_moteur, mid)
        ok, detail, duree = resultat
        await websocket.send(json.dumps({"type": "system_test_result", "id": mid, "ok": ok, "detail": detail,
                                         "duree": round(duree, 2)}, ensure_ascii=False))
    await websocket.send(json.dumps({"type": "system_test_result", "id": "fin", "ok": True, "detail": "", "duree": 0}))
    await ws_get_system_status(websocket)
