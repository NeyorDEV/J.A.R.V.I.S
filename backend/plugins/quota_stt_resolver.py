"""quota_stt_resolver.py — « combien de requêtes Groq », « donne-moi le quota de Groq », « quota de la reconnaissance vocale » : où en est-on des limites de Groq (core/usage_stt.py).

La reconnaissance vocale écrit souvent « grock », « grok » ou « groc » pour « Groq » (et « Grok » est aussi le nom du modèle de xAI, secours de JARVIS) : ces écritures sont acceptées,
et JARVIS précise alors de quel service il parle.
"""
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule

_GROQ = r"(?:groq|grok|grock|groc|groque|grook|growk)"
_SERVICE = rf"(?:{_GROQ}|reconnaissance vocale|reconnaissance de la voix|transcription)"
_MOT = r"(?:quota|quotas|consommation|limites?|requetes?|conso)"
_DEMANDE = re.compile(
    rf"\b{_MOT}\b.*\b{_SERVICE}\b|"
    rf"\b{_SERVICE}\b.*\b{_MOT}\b|"
    rf"\bcombien (?:de )?(?:requetes|secondes|audio).*\b{_GROQ}\b|\betat (?:de )?(?:la )?reconnaissance vocale\b")
_AUTRE_ECRITURE = re.compile(r"\b(?:grok|grock|groc|groque|grook|growk)\b")


def _clean(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn").strip()


async def resoudre_quota_stt(cmd: str):
    t = _clean(cmd)
    if not _DEMANDE.search(t):
        return None
    from core.usage_stt import compteur
    prefixe = "Je suppose que vous parlez de Groq, la reconnaissance vocale. " if _AUTRE_ECRITURE.search(t) else ""
    return prefixe + compteur().resume_parle().rstrip(" .") + nom_virgule() + "."


builtins.resoudre_quota_stt = resoudre_quota_stt
