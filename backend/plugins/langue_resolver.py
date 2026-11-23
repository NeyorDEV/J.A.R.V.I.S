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


def carte_redemarrage() -> None:
    """Carte du HUD avec le bouton « redémarrer » (la phrase dite et la carte disent la même chose)."""
    try:
        from core.web_bridge import diffuser_web_sync
        titre, avis = i18n.avis_redemarrage()
        diffuser_web_sync({"action": "ctx_card", "title": titre, "text": avis, "type": "info", "icon": "◈", "duration": 30000,
                           "bouton": {"libelle": i18n.libelle_redemarrer(), "type": "restart"}})
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
    carte_redemarrage()
    return i18n.avis_redemarrage()[1]   # dit dans la nouvelle langue : redémarrer JARVIS pour que la console et le reste suivent


builtins.resoudre_langue = resoudre_langue
