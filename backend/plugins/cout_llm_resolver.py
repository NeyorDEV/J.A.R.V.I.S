"""cout_llm_resolver.py — « combien coûte gemini aujourd'hui », « mes dépenses d'IA », « budget ia » : dépenses Gemini du jour et du mois (core/usage_llm.py)."""
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule

_SUJET = r"(gemini|geminis|gemeni|jemini|djemini|ia|intelligence artificielle|llm)"   # la reconnaissance vocale écrit parfois « jemini », « djemini »…
_MOT = r"(depense|depenses|depense|cout|couts|coute|budget|facture|consommation|conso|tarif)"
_DEMANDE = re.compile(rf"\b{_MOT}\b.*\b{_SUJET}\b|\b{_SUJET}\b.*\b{_MOT}\b")


def _clean(t: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


async def resoudre_cout_llm(cmd: str):
    if not _DEMANDE.search(_clean(cmd)):
        return None
    from core.usage_llm import compteur
    return compteur().resume_parle().rstrip(" .") + nom_virgule() + "."


builtins.resoudre_cout_llm = resoudre_cout_llm
