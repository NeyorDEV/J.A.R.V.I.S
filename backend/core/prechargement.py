"""Préchargement des grosses bibliothèques tierces, en parallèle, dès le début du démarrage.

Au premier lancement après une longue pause, le disque est « froid » : chaque import attend la lecture
de milliers de fichiers. Importer ces bibliothèques depuis plusieurs threads recouvre ces attentes ; le
thread principal, qui les importe ensuite dans l'ordre d'origine, les trouve déjà en mémoire (ou attend le
verrou d'import du module en cours de chargement). Uniquement des bibliothèques sans effet de bord au
chargement : ni comtypes / pycaw (initialisation COM : thread principal), ni modules du projet.
"""
import importlib
import threading

_GROUPES = (
    ("chromadb", "onnxruntime"),
    ("openai", "requests", "httpx"),
    ("cv2", "PIL.Image"),
    ("playwright.sync_api", "googleapiclient.discovery", "google_auth_oauthlib.flow"),
    ("sherpa_onnx", "psutil", "websockets", "chess"),
)


def _importer(noms):
    for nom in noms:
        try:
            importlib.import_module(nom)
        except Exception:
            pass  # absent ou cassé : l'import normal le signalera, comme avant


def lancer_prechargement():
    # numpy et scipy d'abord, ici et sans thread : importés en parallèle avec les autres bibliothèques (qui s'appuient
    # dessus), ils échouaient (« maximum recursion depth exceeded ») et l'audio perdait son filtre anti-repliement.
    try:
        import numpy  # noqa: F401
        import scipy.signal  # noqa: F401
    except Exception:
        pass
    for noms in _GROUPES:
        threading.Thread(target=_importer, args=(noms,), daemon=True, name="prechargement").start()
