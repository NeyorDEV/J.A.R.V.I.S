"""Découpage d'un enregistrement d'enrôlement en extraits COURTS (1 s), pour compléter le profil vocal.

Pourquoi : le modèle de reconnaissance du locuteur (CAM++) donne une ressemblance plus basse sur une phrase courte que sur une longue, même pour la même voix. Mesuré sur les enregistrements d'enrôlement
du créateur (extraits découpés, comparés aux autres enregistrements) : 0,56 en moyenne pour 0,8 s, 0,60 pour 1 s, 0,69 pour 1,5 s, 0,81 pour 3 s ; or les commandes (« jarvis répète ») durent environ 1 s alors que
l'enrôlement demande des phrases de 4 s : la moitié des commandes d'une seconde tombaient sous le seuil de 0,60 et passaient pour une voix inconnue. Ajouter au profil des extraits d'1 s tirés des
enregistrements d'enrôlement amène 81 % des phrases d'1 s au-dessus de 0,60 (100 % au-dessus de 0,55) SANS baisser le seuil ; un imposteur (autre profil) ne se rapproche pas (0,32 au plus).
Pur et sans numpy : testé dans tests/test_voix_extraits.py.
"""
import array
import math

DUREE_S = 1.0
PAS_S = 0.4
DEBUT_S = 0.3             # on saute le tout début (souffle, clic du micro)
ENERGIE_MIN = 400.0       # RMS (échelle 16 bits) en dessous de laquelle une fenêtre est du silence
MAX_PAR_ENREGISTREMENT = 6


def _rms(pcm: bytes) -> float:
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    return math.sqrt(sum(x * x for x in a) / len(a)) if len(a) else 0.0


def extraits_courts(pcm: bytes, rate: int = 16000, duree: float = DUREE_S, pas: float = PAS_S, debut: float = DEBUT_S,
                    energie_min: float = ENERGIE_MIN, maximum: int = MAX_PAR_ENREGISTREMENT) -> list:
    """Fenêtres de `duree` secondes (PCM 16 bits mono) prises tous les `pas` secondes, sans les passages quasi silencieux ; au plus `maximum`, réparties sur toute la phrase."""
    n, p, d = int(duree * rate) * 2, max(2, int(pas * rate) * 2), int(debut * rate) * 2
    candidats = [pcm[i:i + n] for i in range(d, len(pcm) - n + 1, p)]
    candidats = [c for c in candidats if _rms(c) >= energie_min]
    if len(candidats) > maximum:   # on garde `maximum` fenêtres régulièrement espacées plutôt que les premières
        candidats = [candidats[round(k * (len(candidats) - 1) / (maximum - 1))] for k in range(maximum)] if maximum > 1 else candidats[:1]
    return candidats
