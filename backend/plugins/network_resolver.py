"""
network_resolver.py — Commandes vocales pour le radar réseau JARVIS
"""
import asyncio
import json
import unicodedata
import builtins
from core.interlocuteur import nom_virgule

_radar_active = False
_radar_task = None
# None = première itération (baseline), set() ensuite
_prev_high_ips = None
_prev_scan_ips = None


def _clean(t: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', t)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


async def _diffuser_clients(data: dict) -> None:
    if builtins.CONNECTED_CLIENTS:
        msg = json.dumps(data)
        await asyncio.gather(
            *[ws.send(msg) for ws in builtins.CONNECTED_CLIENTS],
            return_exceptions=True
        )


async def _speak(text: str) -> None:
    """Déclenche la parole TTS de façon sûre (sync ou async)."""
    try:
        if not hasattr(builtins, 'parler'):
            return
        result = builtins.parler(text)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        print(f"[RADAR] Speak error: {e}")


async def _radar_loop() -> None:
    global _radar_active, _prev_high_ips, _prev_scan_ips
    while _radar_active:
        try:
            from module.network_radar import get_radar_data
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, get_radar_data)

            # ── Alerte vocale : nouvelles connexions à risque élevé ──────────
            current_high = {c['ip'] for c in data if c['risk'] == 'high'}
            if _prev_high_ips is not None:
                new_high = current_high - _prev_high_ips
                if new_high:
                    for c in data:
                        if c['ip'] in new_high:
                            proc = c['process'].replace('.exe', '')
                            asyncio.create_task(_speak(
                                f"Alerte{nom_virgule()} ! Connexion à risque élevé détectée "
                                f"vers {c['country']} via {proc}."
                            ))
                            break
            _prev_high_ips = current_high

            # ── Alerte vocale : scan de ports ────────────────────────────────
            current_scan = {c['ip'] for c in data if c.get('port_scan')}
            if _prev_scan_ips is not None:
                new_scan = current_scan - _prev_scan_ips
                if new_scan:
                    ip = next(iter(new_scan))
                    asyncio.create_task(_speak(
                        f"Attention{nom_virgule()}. Tentative de scan de ports détectée depuis {ip}."
                    ))
            _prev_scan_ips = current_scan

            await _diffuser_clients({"action": "network_radar_update", "connections": data})

        except asyncio.CancelledError:
            break
        except RuntimeError as e:
            if "shutdown" in str(e) or "closed" in str(e):
                break
            print(f"[RADAR] Loop error: {e}")
        except Exception as e:
            print(f"[RADAR] Loop error: {e}")
        try:
            await asyncio.sleep(6)
        except asyncio.CancelledError:
            break


async def resoudre_connexions_reseau(cmd: str):
    global _radar_active, _radar_task, _prev_high_ips, _prev_scan_ips
    t = _clean(cmd)

    # Il faut parler du radar ou du trafic du réseau : « connexion » seul visait aussi
    # « coupe la connexion wifi » (→ « Radar réseau désactivé »).
    import re as _re
    if not ("radar" in t or _re.search(r"\b(connexions? (reseau|actives?|du pc|de l'ordinateur)|trafic( reseau)?|carte (du )?reseau|qui est connecte)\b", t)):
        return None

    mots_hide = ["cache", "ferme", "stop", "arrete", "desactive", "masque", "quitte", "coupe", "eteins"]
    if any(m in t for m in mots_hide):
        _radar_active = False
        if _radar_task and not _radar_task.done():
            _radar_task.cancel()
        await _diffuser_clients({"action": "network_radar_hide"})
        return "Radar réseau désactivé."

    mots_show = ["montre", "affiche", "active", "lance", "ouvre", "voir", "demarre", "radar reseau", "connexions"]
    if any(m in t for m in mots_show) or t in ("radar", "carte reseau", "carte du reseau"):
        from module.network_radar import get_radar_data, get_radar_summary
        # Réinitialiser : la 1ère itération de la boucle servira de baseline
        _prev_high_ips = None
        _prev_scan_ips = None
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_radar_data)
        await _diffuser_clients({"action": "network_radar_show", "connections": data})
        _radar_active = True
        if _radar_task and not _radar_task.done():
            _radar_task.cancel()
        _radar_task = asyncio.create_task(_radar_loop())
        return get_radar_summary(data)

    return None


builtins.resoudre_connexions_reseau = resoudre_connexions_reseau
