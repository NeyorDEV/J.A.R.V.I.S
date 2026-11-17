"""repetition_resolver.py — « répète », « redis », « j'ai pas compris » : JARVIS redit sa dernière réponse (core/repeter.py)."""
import builtins

from core.interlocuteur import nom_virgule
from core.repeter import derniere_reponse, est_demande_repetition, ignorer_prochaine


async def resoudre_repetition(cmd: str):
    if not est_demande_repetition(cmd):
        return None
    texte = derniere_reponse()
    if not texte:
        rien = f"Je n'ai rien dit récemment{nom_virgule()}."
        ignorer_prochaine(rien)
        return rien
    ignorer_prochaine(texte)   # la répétition ne devient pas une nouvelle « dernière réponse »
    return texte


builtins.resoudre_repetition = resoudre_repetition
