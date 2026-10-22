"""Nom de la personne qui parle à JARVIS, et identité de son créateur.

JARVIS s'adresse à la personne qui lui a donné l'instruction : le profil reconnu par
la biométrie vocale (« Neyor », « Clara »...), ou le créateur pour le clavier du HUD
local. Un invité non reconnu n'est pas nommé.

Seules les informations relatives au créateur (son identité, ses droits) restent
écrites en dur, avec CREATEUR / NOM_CREATEUR.
"""

import builtins
import json
import os

import core.shared as shared

CREATEUR = "neyor"          # identifiant du profil vocal du créateur (dossier voiceprints/neyor)
NOM_CREATEUR = "Neyor"      # forme affichée ; prononcée « Néyor » (voir core/speech.py)


_cache_config = {"mtime": None, "donnees": {}}


def _config():
    """jarvis_config.json, relu seulement s'il a changé (appelé à chaque phrase prononcée)."""
    chemin = os.path.join(shared.RACINE_PROJET, "jarvis_config.json")
    try:
        mtime = os.path.getmtime(chemin)
        if mtime != _cache_config["mtime"]:
            with open(chemin, encoding="utf-8") as f:
                _cache_config["donnees"] = json.load(f)
            _cache_config["mtime"] = mtime
    except Exception:
        pass
    return _cache_config["donnees"]


def nom_createur():
    """Prénom du propriétaire de l'installation : réglage « user_name » (assistant de premier lancement,
    Paramètres), « Neyor » tant qu'il est vide."""
    nom = str(_config().get("user_name", "") or "").strip()
    return nom[:1].upper() + nom[1:] if nom else NOM_CREATEUR


def infos_createur():
    """Informations privées facultatives sur le propriétaire (« createur_infos » dans jarvis_config.json :
    une chaîne ou une liste de phrases), transmises aux IA. Rien n'est écrit dans le code."""
    infos = _config().get("createur_infos", [])
    if isinstance(infos, str):
        infos = [infos]
    return [str(i).strip() for i in infos if str(i).strip()]


def profil_actif():
    """Identifiant du profil qui parle actuellement : « neyor », « clara », « guest »..."""
    return getattr(builtins, "ACTIVE_SPEAKER", None) or shared.ACTIVE_SPEAKER


def nom_interlocuteur():
    """Prénom de la personne qui parle (« Neyor », « Clara »...), ou "" pour un invité."""
    profil = profil_actif()
    if not profil or profil == "guest":
        return ""
    if profil == CREATEUR:
        return nom_createur()
    return profil.capitalize()


def nom_espace():
    """« Neyor » précédé d'une espace, ou rien pour un invité : f"Très bien{nom_espace()}, je lance..." """
    nom = nom_interlocuteur()
    return f" {nom}" if nom else ""


def nom_virgule():
    """« , Neyor », ou rien pour un invité : f"Musique en pause{nom_virgule()}." """
    nom = nom_interlocuteur()
    return f", {nom}" if nom else ""


def nom_ou_utilisateur():
    """Prénom de la personne qui parle, ou « l'utilisateur » (pour les consignes envoyées aux IA)."""
    return nom_interlocuteur() or "l'utilisateur"
