"""conversation_resolver.py — « active la conversation continue », « c'est tout » / « à plus tard » : ferme la session tout de suite (core/conversation.py)."""
import builtins
import re
import unicodedata

import core.shared as shared
from core import conversation
from core.interlocuteur import nom_virgule


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


async def resoudre_conversation(cmd: str):
    t = _norm(cmd.strip())
    if re.search(r"\bconversation (?:continue|permanente|ouverte)\b|\bmode conversation\b|\bcontinuous conversation\b", t):
        if re.search(r"\b(?:desactive|arrete|coupe|stoppe|enleve|quitte|disable|stop|turn off)\b", t):
            conversation.definir_continu(False)
            return f"Conversation continue désactivée{nom_virgule()} : je me rendors après quelques secondes de silence."
        conversation.definir_continu(True)
        return f"Conversation continue activée{nom_virgule()}. Je reste à l'écoute sans qu'il faille redire mon nom ; dites « c'est tout » pour me rendormir."
    if conversation.est_fin(cmd):
        shared.jarvis_actif = False   # la session se referme : il faudra redire « Jarvis »
        return f"À votre service{nom_virgule()}."
    return None


builtins.resoudre_conversation = resoudre_conversation
