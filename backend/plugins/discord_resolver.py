"""Commandes vocales Discord (module/discord_service.py) :
  « envoie salut à tous dans le salon annonces »            (webhook ou bot : un salon configuré)
  « écris à Léo sur discord que je suis en retard »          (fenêtre Discord, en votre nom : option à activer)
Chaque envoi demande une confirmation à voix haute et sur le HUD, et est inscrit au journal d'audit."""

import asyncio
import builtins
import re
import unicodedata

from core.interlocuteur import nom_virgule
from module import discord_service as dc


def _normaliser(texte):
    """Minuscule sans accents, SANS changer la longueur : les positions valent aussi pour le texte d'origine."""
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower().replace("’", "'")) if unicodedata.category(c) != "Mn")


def _nettoyer(message):
    return message.strip().strip("«»\"'“” :,").strip()


_DEBUT = r"^(?:jarvis[ ,]+)?(?:s'il te plait[ ,]+)?(?:peux[- ]tu |pourrais[- ]tu )?"
_SALON = re.compile(_DEBUT + r"(?:envoie|ecris|poste|publie|balance)(?: le message| un message| ceci)?\s+(.+?)\s+"
                    r"(?:dans|sur|vers)\s+(?:le |la )?(?:salon|canal|channel)\s+(.+?)(?:\s+(?:sur|de|du) discord)?\s*[.?!]?$")
_SALON_DISCORD = re.compile(_DEBUT + r"(?:envoie|ecris|poste|publie|balance)(?: le message| un message)?\s+(.+?)\s+"
                            r"(?:dans|sur|vers)\s+(?:le |la )?(.+?)\s+sur discord\s*[.?!]?$")
_PERSONNE_A = re.compile(_DEBUT + r"(?:envoie|ecris|dis)(?: un message| le message)?\s+(?:a|à)\s+(.+?)\s+sur discord"
                         r"(?:\s+que|\s*:|\s+)\s*(.+?)\s*[.?!]?$")
_PERSONNE_B = re.compile(_DEBUT + r"(?:envoie|ecris)\s+(.+?)\s+(?:a|à)\s+(.+?)\s+sur discord\s*[.?!]?$")


async def _confirmer(question):
    from core.confirmation import demander_confirmation
    return await demander_confirmation(None, question)


async def resoudre_discord(texte):
    original = texte.strip().replace("’", "'")
    t = _normaliser(original)
    if "discord" not in t and not re.search(r"\b(salon|canal|channel)\b", t):
        return None

    # 1. Salon configuré (webhook ou bot)
    m = _SALON.match(t) or _SALON_DISCORD.match(t)
    if m:
        message = _nettoyer(original[m.start(1):m.end(1)])
        nom = original[m.start(2):m.end(2)].strip()
        if not message:
            return None
        trouve = dc.trouver_salon(nom)
        if not trouve:
            if not dc.salons():
                return (f"Aucun salon Discord n'est configuré{nom_virgule()} : ajoutez-en un dans "
                        "Paramètres, rubrique Discord.")
            return f"Je ne connais pas le salon « {nom} »{nom_virgule()}. Mes salons : {', '.join(list(dc.salons())[:6])}."
        alias, valeur = trouve
        if not await _confirmer(f"Envoyer « {message[:120]} » dans le salon {alias} ?"):
            return "D'accord, je n'envoie rien."
        ok, detail = await asyncio.to_thread(dc.envoyer_salon, valeur, message)
        _journal(alias, "salon:" + (dc.type_cible(valeur) or "?"), message, ok)
        return f"Message envoyé dans {alias}{nom_virgule()}." if ok else f"Je n'ai pas pu envoyer le message : {detail}."

    # 2. Quelqu'un, en pilotant la fenêtre Discord (option désactivée par défaut)
    m = _PERSONNE_A.match(t)
    if m:
        destinataire = original[m.start(1):m.end(1)].strip()
        message = _nettoyer(original[m.start(2):m.end(2)])
    else:
        m = _PERSONNE_B.match(t)
        if not m:
            return None
        message = _nettoyer(original[m.start(1):m.end(1)])
        destinataire = original[m.start(2):m.end(2)].strip()
    if not destinataire or not message:
        return None
    if not dc.envoi_fenetre_autorise():
        return ("L'envoi en votre nom par Discord est désactivé : c'est une zone grise des conditions de Discord. "
                "Vous pouvez l'activer dans Paramètres, rubrique Discord, ou utiliser un salon par webhook.")
    if not await _confirmer(f"Écrire « {message[:120]} » à {destinataire} sur Discord ? "
                            "Discord ouvrira la première conversation qui correspond à ce nom."):
        return "D'accord, je n'envoie rien."
    ok, detail = await asyncio.to_thread(dc.envoyer_par_fenetre, destinataire, message)
    _journal(destinataire, "fenetre", message, ok)
    return f"Message envoyé à {destinataire}{nom_virgule()}." if ok else f"Je n'ai pas pu envoyer le message : {detail}."


def _journal(cible, voie, message, ok):
    try:
        from core.audit_log import consigner
        consigner("discord_envoi", cible=cible, voie=voie, longueur=len(message), ok=ok)  # jamais le contenu
    except Exception:
        pass


builtins.resoudre_discord = resoudre_discord
