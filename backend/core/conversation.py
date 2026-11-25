"""Conversation continue : JARVIS reste à l'écoute tant que la discussion dure, sans qu'on redise « Jarvis ».

La session (shared.jarvis_actif) existait déjà, avec un délai fixe (shared.SESSION_TIMEOUT). Ici :
- délai prolongé quand JARVIS vient de poser une question (la réponse arrive, il ne se rendort pas avant) ;
- mode continu (« active la conversation continue ») : la session ne se ferme qu'après 5 minutes de silence ou sur une phrase de fin ;
- fin par le sens : « c'est tout », « à plus tard », « bonne nuit »… (phrase courte) referment la session tout de suite.
Pur sauf le réglage `conversation_continue` de jarvis_config.json (chemin de core/i18n). Testé : tests/test_conversation.py.
"""
import json
import re
import unicodedata

DELAI_CONTINU = 300.0     # s de silence avant de se rendormir en mode continu
BONUS_QUESTION = 25.0     # s ajoutées quand la dernière phrase de JARVIS est une question
MAX_MOTS_FIN = 7          # « ce sera tout pour la météo, et mets de la musique » n'est pas une fin

_FINS = re.compile(
    r"\b(?:c'est tout|ce sera tout|ca sera tout|c'est bon merci|merci c'est bon|merci c'est tout|c'est bon pour moi|j'ai fini|j'ai termine|on s'arrete la|laisse tomber|"
    r"a plus tard|a tout a l'heure|a bientot|a demain|au revoir|bonne nuit|bonne soiree|bonne journee|"
    r"that'?s all|that will be all|that'?s it|see you later|see you tomorrow|goodbye|good night|never mind)\b")


def _norm(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower().replace("’", "'")) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^\w' ]", " ", t)).strip()


def est_fin(texte: str) -> bool:
    t = re.sub(r"\bjarvis\b", " ", _norm(texte))
    t = re.sub(r"\s+", " ", t).strip()
    return bool(t) and len(t.split()) <= MAX_MOTS_FIN and bool(_FINS.search(t))


def attend_une_reponse(derniere_phrase: str) -> bool:
    """La dernière phrase de JARVIS se termine par une question."""
    return str(derniere_phrase or "").rstrip().endswith("?")


def delai_session(base: float, attend_reponse: bool = False, continu: bool = False) -> float:
    if continu:
        return max(base, DELAI_CONTINU)
    return base + (BONUS_QUESTION if attend_reponse else 0.0)


def _config_chemin() -> str:
    from core import i18n
    return i18n._CONFIG


def mode_continu() -> bool:
    try:
        with open(_config_chemin(), encoding="utf-8") as f:
            return bool(json.load(f).get("conversation_continue"))
    except Exception:
        return False


def definir_continu(actif: bool) -> bool:
    try:
        try:
            with open(_config_chemin(), encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        cfg["conversation_continue"] = bool(actif)
        with open(_config_chemin(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[CONVERSATION] Réglage non sauvegardé : {e}")
        return False


def delai_courant(base: float) -> float:
    """Délai de session à appliquer maintenant (lit le mode continu et la dernière phrase dite). Jamais d'exception : en cas de doute, le délai de base."""
    try:
        from core.repeter import derniere_reponse
        return delai_session(base, attend_une_reponse(derniere_reponse()), mode_continu())
    except Exception:
        return base
