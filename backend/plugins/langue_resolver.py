"""langue_resolver.py — « passe en anglais », « parle en français », « switch to English » : change la langue de JARVIS à chaud (core/i18n.py).

Change la reconnaissance vocale, la voix, le prompt, la traduction des réponses ; prévient le HUD pour qu'il change ses textes.
"""
import builtins
import re
import unicodedata

from core import i18n

_VERBE = r"(?:passe|parle|reponds|repond|mets|met|change|bascule|repasse|speak|talk|answer|reply|switch|change to|go)"
_ANGLAIS = re.compile(rf"\b{_VERBE}\b[^.]{{0,25}}\b(?:anglais|english)\b")
_FRANCAIS = re.compile(rf"\b{_VERBE}\b[^.]{{0,25}}\b(?:francais|french)\b")


def _langue_demandee(t: str):
    if _ANGLAIS.search(t):
        return "en"
    if _FRANCAIS.search(t):
        return "fr"
    return None


def prevenir_hud(code: str) -> None:
    try:
        from core.web_bridge import diffuser_web_sync
        diffuser_web_sync({"action": "langue", "langue": code})
    except Exception:
        pass


async def resoudre_langue(cmd: str):
    t = "".join(c for c in unicodedata.normalize("NFD", cmd.lower()) if unicodedata.category(c) != "Mn")
    t = re.sub(r"[-'’]", " ", t)
    code = _langue_demandee(t)
    if not code:
        return None
    if code == i18n.langue():
        return "I am already speaking English." if code == "en" else "Je parle déjà français."
    i18n.definir(code)
    prevenir_hud(code)
    return "Switching to English. I will understand and answer in English now." if code == "en" else "Je repasse en français."


builtins.resoudre_langue = resoudre_langue
