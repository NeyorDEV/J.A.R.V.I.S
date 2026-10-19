"""Diffusion des statistiques CPU/RAM au HUD et alertes de charge."""

import asyncio
import json
import time

import core.shared as shared
from core.web_bridge import envoyer_carte_contextuelle


async def diffuser_stats_systeme():
    """Diffuse les stats CPU/RAM et envoie des alertes contextuelles si nécessaire.

    (Cette définition écrase une première version située plus haut dans le fichier ;
    la garde psutil de celle-ci y a été rapatriée — sans elle, si psutil manquait,
    l'appel levait une AttributeError toutes les 2 s dans un `except: pass` et les
    jauges restaient plates sans le moindre diagnostic.)
    """
    if shared.psutil is None:
        try:
            import psutil as ps
            shared.psutil = ps
        except ImportError:
            print("[SYS] psutil non disponible. Monitoring CPU/RAM désactivé.")
            return

    print("[SYS] Suivi du CPU et de la RAM lancé...")
    shared.psutil.cpu_percent(interval=None)   # amorce la mesure différentielle

    last_alert_time = 0
    erreurs_consecutives = 0
    while True:
        try:
            if shared.CONNECTED_CLIENTS:
                cpu = shared.psutil.cpu_percent(interval=None)
                ram = shared.psutil.virtual_memory().percent

                # Stats classiques (pour les jauges)
                msg = json.dumps({"action": "system_stats", "cpu": cpu, "ram": ram})
                clients = list(shared.CONNECTED_CLIENTS)
                if clients:
                    await asyncio.gather(*[ws.send(msg) for ws in clients], return_exceptions=True)

                # Alerte contextuelle si CPU > 90%
                if cpu > 90 and (time.time() - last_alert_time > 60):
                    await envoyer_carte_contextuelle(
                        "Alerte Système",
                        f"Charge CPU critique détectée : {cpu}%. Les performances de JARVIS peuvent être affectées.",
                        type_carte="alert",
                        icon="⚠",
                        duree=15000
                    )
                    last_alert_time = time.time()
            erreurs_consecutives = 0
        except Exception as e:
            # On ne spamme pas la console, mais on ne masque plus totalement la panne
            erreurs_consecutives += 1
            if erreurs_consecutives in (1, 10) or erreurs_consecutives % 100 == 0:
                print(f"[SYS] Monitoring en échec ({erreurs_consecutives}x) : {e}")
        await asyncio.sleep(2)
