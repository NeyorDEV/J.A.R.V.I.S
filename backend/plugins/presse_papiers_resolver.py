"""presse_papiers_resolver.py — « traduis ce que j'ai copié », « résume le presse-papiers », « dicte : bonjour virgule… » (module/presse_papiers.py)."""
import asyncio
import builtins

from core.interlocuteur import nom_virgule
from module import presse_papiers as pp

_VERBES = {"traduire": "Traduit", "resumer": "Résumé", "corriger": "Corrigé", "formater": "Mis en forme"}


async def resoudre_presse_papiers(cmd: str):
    t = pp.norm(cmd)
    analyse = pp.analyser_presse_papiers(t)
    if analyse is None:
        return None
    action, langue = analyse
    texte = await asyncio.to_thread(pp.lire_presse_papiers)
    if not texte.strip():
        return f"Votre presse-papiers est vide{nom_virgule()}."
    if action == "lire":
        return texte if len(texte) <= 400 else texte[:400].rsplit(" ", 1)[0] + "… Le reste est dans votre presse-papiers."
    resultat = await pp.transformer(action, langue, texte)
    if not resultat:
        return f"Je n'ai pas réussi à traiter ce texte{nom_virgule()}, réessayez dans un instant."
    await asyncio.to_thread(pp.ecrire_presse_papiers, resultat)
    if len(resultat) <= 280:
        return f"{_VERBES[action]} et copié : {resultat}"
    return f"{_VERBES[action]}{nom_virgule()}, le résultat est dans votre presse-papiers."


async def resoudre_dictee(cmd: str):
    texte = pp.analyser_dictee(cmd)
    if texte is None:
        return None
    etat = await asyncio.to_thread(pp.dicter, texte)
    if etat == "jarvis":
        return f"La fenêtre active est la mienne{nom_virgule()}, cliquez d'abord dans l'application où écrire."
    if etat == "terminal":
        return f"Je ne dicte pas dans un terminal{nom_virgule()} : un retour à la ligne y lancerait une commande."
    return f"C'est écrit{nom_virgule()}."


builtins.resoudre_presse_papiers = resoudre_presse_papiers
builtins.resoudre_dictee = resoudre_dictee
