"""Commandes vocales Steam : « lance Portal sur Steam », « joue à Counter-Strike », « mes jeux Steam »,
« ouvre ma bibliothèque Steam ». Le jeu est trouvé dans les jeux réellement installés (controller/steam_controller.py)."""

import asyncio
import builtins
import re

from core.interlocuteur import nom_virgule
from controller import steam_controller as steam

_VERBES = (r"(?:lance|lancer|demarre|demarrer|joue a|jouer a|ouvre|ouvrir|mets|mettre|"
           r"je veux jouer a|on joue a|on lance|je lance)")
_MOTIF_LANCER = re.compile(
    rf"^(?:jarvis[ ,]+)?(?:s'il te plait[ ,]+)?(?:peux[- ]tu |pourrais[- ]tu )?{_VERBES}(?: moi)?\s+"
    r"(?:le jeu |le |la |les |l'|a |un |une )?(.+?)(?:\s+(?:sur|dans|avec|via)\s+steam)?\s*[.?!]?$")


def _est_une_appli_du_pc(requete):
    """« lance discord » est une application, pas un jeu Steam : on laisse le lanceur d'applications."""
    try:
        from controller.app_launcher import _APPS_CATALOGUE
    except Exception:
        return False
    q = steam.normaliser(requete)
    for cle, info in _APPS_CATALOGUE.items():
        if q in (steam.normaliser(cle), steam.normaliser(info.get("label", ""))):
            return True
    return False


async def resoudre_steam_jeux(texte):
    t = steam.normaliser(texte)
    mentionne_steam = bool(re.search(r"\bsteam\b", t))

    # Bibliothèque / boutique / liste des jeux : seulement si Steam est nommé
    if mentionne_steam:
        if re.search(r"\b(bibliotheque|library)\b", t) and re.search(r"\b(ouvre|ouvrir|affiche|montre)\b", t):
            await asyncio.to_thread(steam.ouvrir, "bibliotheque")
            return f"J'ouvre votre bibliothèque Steam{nom_virgule()}."
        if re.search(r"\b(boutique|magasin|store)\b", t) and re.search(r"\b(ouvre|ouvrir|affiche|montre)\b", t):
            await asyncio.to_thread(steam.ouvrir, "boutique")
            return f"J'ouvre la boutique Steam{nom_virgule()}."
        if re.search(r"\bjeux\b", t) and re.search(r"\b(quels|liste|mes|combien|dis|donne|affiche)\b", t) \
                and not re.search(r"\b(lance|joue|demarre)\b", t):
            jeux = sorted(steam.jeux_installes(force=True).values(), key=str.lower)
            if not jeux:
                return f"Je ne trouve aucun jeu installé sur Steam{nom_virgule()}."
            exemples = ", ".join(jeux[:6])
            suite = f", et {len(jeux) - 6} autres" if len(jeux) > 6 else ""
            return f"Vous avez {len(jeux)} jeux installés sur Steam, par exemple {exemples}{suite}{nom_virgule()}."

    m = _MOTIF_LANCER.match(texte.lower().strip().replace("’", "'"))
    if not m:
        # Les accents sont facultatifs dans les verbes : « joue à » devient « joue a » après normalisation
        m = _MOTIF_LANCER.match(t)
    if not m:
        return None
    requete = m.group(1).strip()
    if not requete or steam.normaliser(requete) in ("steam", "jeu", "un jeu", "mes jeux"):
        return None
    sur_steam = mentionne_steam
    if not sur_steam and _est_une_appli_du_pc(requete):
        return None

    etat, donnees = steam.trouver_jeu(requete)
    if etat == "ambigu":
        return f"J'hésite entre {', '.join(donnees)}{nom_virgule()} : dites-moi lequel."
    if etat == "inconnu":
        # Sans « Steam » dans la phrase, on ne devine rien : la phrase peut viser autre chose
        return f"Je ne trouve pas « {requete} » parmi vos jeux Steam{nom_virgule()}." if sur_steam else None
    appid, nom, score = donnees
    if not sur_steam and score < 0.9:
        return None  # ressemblance trop faible pour lancer un jeu sans qu'on ait dit « Steam »
    await asyncio.to_thread(steam.lancer_jeu, appid)
    return f"Je lance {nom} sur Steam{nom_virgule()}."


builtins.resoudre_steam_jeux = resoudre_steam_jeux
