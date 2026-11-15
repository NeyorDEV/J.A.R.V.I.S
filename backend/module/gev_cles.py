"""Clés des services branchés sur God's Eye View par JARVIS (Météo-France, Windy), saisies dans le panneau « POWER UP » de la Vue de Dieu.

Le panneau écrit dans le .env de l'appli (data/gods_eye_view/app/.env, voir le plugin jarvisCles de module/vue_de_dieu.py) : on le relit ici, avec repli sur l'environnement
de JARVIS (son propre .env). Rien n'est copié dans l'environnement de l'appli, qui afficherait la clé « configurée en externe » (lecture seule).
"""
import os
import re

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_GEV = os.path.join(RACINE, "data", "gods_eye_view", "app", ".env")


def lire(nom: str) -> str:
    """Valeur de la clé `nom` : .env de l'appli d'abord, sinon environnement de JARVIS ; chaîne vide si absente."""
    try:
        with open(ENV_GEV, encoding="utf-8") as f:
            for ligne in f:
                m = re.match(r"\s*(?:export\s+)?" + re.escape(nom) + r"\s*=\s*(\S*)\s*$", ligne)
                if m and m.group(1):
                    return m.group(1)
    except OSError:
        pass
    return (os.environ.get(nom) or "").strip()
