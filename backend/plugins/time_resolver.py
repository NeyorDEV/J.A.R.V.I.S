import builtins
import datetime
import pytz
import re

from core.interlocuteur import nom_virgule

_FUSEAUX = {
    "new york": "America/New_York",
    "london": "Europe/London", "londres": "Europe/London",
    "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "tokyo": "Asia/Tokyo", "sydney": "Australia/Sydney",
    "dubai": "Asia/Dubai", "moscou": "Europe/Moscow"
}


async def resoudre_temps_localement(texte):
    """Gère l'heure mondiale et les infos monétaires."""
    t = texte.lower().strip()
    
    # HEURE (« quelle heure est-il à Tokyo » n'était pas compris : seul « heure à » l'était)
    # (mais « à quelle heure part le train pour Paris » ne demande pas l'heure de Paris)
    if re.search(r"(quelle heure est[- ]il|quelle heure il est|l['’ ]heure|\bheure (a|à|au|en)\b)", t):
        for ville, zone in _FUSEAUX.items():
            if ville in t:
                tz = pytz.timezone(zone)
                heure = datetime.datetime.now(tz).strftime("%H:%M")
                return f"Il est actuellement {heure} à {ville.title()}{nom_virgule()}."

    # (Les monnaies sont traitées par plugins/extras.py)
    return None

# Injection builtins
builtins.resoudre_temps_localement = resoudre_temps_localement
