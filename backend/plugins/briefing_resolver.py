"""briefing_resolver.py — « ma journée », « mon briefing » : date, météo, agenda, tâches, alarmes et mails en une phrase (module/briefing.py)."""
import asyncio
import builtins
import unicodedata
from datetime import datetime

from core.interlocuteur import nom_interlocuteur
from module import briefing


async def resoudre_briefing(cmd: str):
    t = "".join(c for c in unicodedata.normalize("NFD", cmd.lower().strip()) if unicodedata.category(c) != "Mn")
    if not briefing.demande(t):
        return None
    cles = list(briefing.SOURCES)
    valeurs = await asyncio.gather(*(asyncio.to_thread(briefing.SOURCES[c]) for c in cles))
    return briefing.composer(datetime.now(), nom=nom_interlocuteur(), **dict(zip(cles, valeurs)))


builtins.resoudre_briefing = resoudre_briefing
