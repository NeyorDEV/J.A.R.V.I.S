"""Registre des moteurs de voix : chaque moteur est une fonction enregistrée, essayée dans l'ordre jusqu'au premier qui rend un fichier audio.

Ajouter un moteur = un `enregistrer(...)`. Un moteur qui vient d'échouer est mis de côté `PAUSE_APRES_ECHEC` secondes : sans cela, internet coupé faisait attendre le délai
d'edge-tts (12 s) à CHAQUE phrase avant de passer à la voix Windows. L'ordre se règle par `"tts_ordre": ["edge_tts", "sapi"]` dans jarvis_config.json.

Même principe que le registre de moteurs de voix d'OpenJarvis (open-jarvis/OpenJarvis, Apache-2.0) et que core/llm_registry.py pour les IA.
Pur (testé : tests/test_voix_registre.py) : aucun moteur n'est importé ici.
"""
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

PAUSE_APRES_ECHEC = 30.0   # s
_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class Moteur:
    nom: str
    priorite: int                                              # plus petit = essayé d'abord
    disponible: Callable[[], bool]                             # clé présente, bibliothèque installée, réglage actif…
    synthetiser: Callable[[str, str], Awaitable[Optional[str]]]  # (texte, chemin_sans_extension) -> chemin du fichier, ou None
    en_panne_jusqua: float = 0.0


_MOTEURS: dict = {}


def enregistrer(nom, priorite, disponible, synthetiser):
    _MOTEURS[nom] = Moteur(nom, priorite, disponible, synthetiser)


def vider():
    _MOTEURS.clear()


def _ordre_configure():
    try:
        with open(os.path.join(_RACINE, "jarvis_config.json"), encoding="utf-8") as f:
            o = json.load(f).get("tts_ordre")
        return [str(n) for n in o] if isinstance(o, list) else []
    except Exception:
        return []


def ordre(maintenant=None):
    """Moteurs à essayer maintenant : ceux du réglage « tts_ordre » d'abord (dans cet ordre), puis les autres par priorité ; les moteurs en pause et indisponibles sont écartés."""
    t = time.monotonic() if maintenant is None else maintenant
    voulus = _ordre_configure()
    tous = sorted(_MOTEURS.values(), key=lambda m: (voulus.index(m.nom) if m.nom in voulus else len(voulus), m.priorite))
    sortie = []
    for m in tous:
        try:
            if m.en_panne_jusqua > t or not m.disponible():
                continue
        except Exception:
            continue
        sortie.append(m)
    return sortie


async def generer(texte: str, base: str, maintenant=None) -> Optional[str]:
    """Chemin du fichier audio du premier moteur qui réussit, ou None."""
    for m in ordre(maintenant):
        try:
            chemin = await m.synthetiser(texte, base)
            if chemin:
                return chemin
            raise RuntimeError("aucun fichier produit")
        except Exception as e:
            m.en_panne_jusqua = (time.monotonic() if maintenant is None else maintenant) + PAUSE_APRES_ECHEC
            print(f"[SPEECH] Moteur « {m.nom} » en échec ({type(e).__name__} : {str(e)[:90]}) : suivant pendant {int(PAUSE_APRES_ECHEC)} s.")
    return None


def noms():
    return [m.nom for m in sorted(_MOTEURS.values(), key=lambda m: m.priorite)]


async def synthese_http(fonction_bloquante, *args):
    """Exécute une synthèse bloquante (requête HTTP, moteur local) hors de la boucle asyncio."""
    return await asyncio.get_running_loop().run_in_executor(None, fonction_bloquante, *args)
