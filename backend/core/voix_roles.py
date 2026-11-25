"""Plusieurs voix : une pour les alertes (grave, rapide), une pour le quotidien, une pour la lecture longue.

Chaque rôle règle le genre de la voix edge-tts, la vitesse et la hauteur. Par défaut : « quotidien » = la voix choisie par l'utilisateur, comme avant ;
« alerte » = la même voix, plus grave et plus vive ; « lecture » = la même voix, un peu plus posée. Réglable dans jarvis_config.json :
    "voix_roles": {"lecture": {"genre": "femme", "rate": "+5%", "pitch": "+0Hz"}}
ou à la voix (« voix de lecture féminine », plugins/voix_roles_resolver.py).
Le rôle d'une phrase : celui que l'appelant donne (parler(texte, role="alerte")), sinon « alerte » si elle commence par Alerte / Attention…, « lecture » si elle est longue.
Pur (testé : tests/test_voix_roles.py) ; le chemin du fichier de réglages est celui de core/i18n.
"""
import json
import re

ROLES = ("alerte", "quotidien", "lecture")
SEUIL_LECTURE = 300   # caractères : au-delà, une phrase dite d'un bloc est une lecture
_DEFAUTS = {"alerte": {"rate": "+25%", "pitch": "-12Hz"},
            "quotidien": {"rate": "+20%", "pitch": "+0Hz"},
            "lecture": {"rate": "+8%", "pitch": "+0Hz"}}
_ALERTE = re.compile(r"^\W*(?:alerte|attention|urgent|danger|avertissement|warning|alert)\b", re.IGNORECASE)
_RATE = re.compile(r"^[+-]\d{1,3}%$")
_PITCH = re.compile(r"^[+-]\d{1,3}Hz$")


def role_de(texte: str, force: str | None = None) -> str:
    if force in ROLES:
        return force
    if _ALERTE.match(texte or ""):
        return "alerte"
    return "lecture" if len(texte or "") > SEUIL_LECTURE else "quotidien"


def _config() -> dict:
    from core import i18n
    try:
        with open(i18n._CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def reglage(role: str, genre_defaut: str) -> dict:
    """{'genre', 'rate', 'pitch'} du rôle : valeurs par défaut, surchargées par « voix_roles » de jarvis_config.json (valeurs invalides ignorées)."""
    r = dict(_DEFAUTS.get(role, _DEFAUTS["quotidien"]), genre=genre_defaut)
    voulu = (_config().get("voix_roles") or {}).get(role)
    if isinstance(voulu, dict):
        if voulu.get("genre") in ("homme", "femme"):
            r["genre"] = voulu["genre"]
        if isinstance(voulu.get("rate"), str) and _RATE.match(voulu["rate"]):
            r["rate"] = voulu["rate"]
        if isinstance(voulu.get("pitch"), str) and _PITCH.match(voulu["pitch"]):
            r["pitch"] = voulu["pitch"]
    return r


def definir(role: str, genre: str) -> bool:
    """Choisit le genre de la voix d'un rôle et le sauvegarde. False si le rôle ou le genre est inconnu."""
    if role not in ROLES or genre not in ("homme", "femme"):
        return False
    return _ecrire(lambda d: d.setdefault("voix_roles", {}).setdefault(role, {}).update(genre=genre))


def reinitialiser() -> bool:
    return _ecrire(lambda d: d.pop("voix_roles", None))


def _ecrire(modifier) -> bool:
    from core import i18n
    try:
        try:
            with open(i18n._CONFIG, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        modifier(d)
        with open(i18n._CONFIG, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[VOIX] Réglage non sauvegardé : {e}")
        return False
