"""Nom de la personne qui parle à JARVIS, et identité de son créateur.

JARVIS s'adresse à la personne qui lui a donné l'instruction : le profil reconnu par
la biométrie vocale (« Neyor », « Clara »...), ou le créateur pour le clavier du HUD
local. Un invité non reconnu n'est pas nommé.

Seules les informations relatives au créateur (son identité, ses droits) restent
écrites en dur, avec CREATEUR / NOM_CREATEUR.
"""

import builtins

import core.shared as shared

CREATEUR = "neyor"          # identifiant du profil vocal du créateur (dossier voiceprints/neyor)
NOM_CREATEUR = "Neyor"      # forme affichée ; prononcée « Néyor » (voir core/speech.py)


def profil_actif():
    """Identifiant du profil qui parle actuellement : « neyor », « clara », « guest »..."""
    return getattr(builtins, "ACTIVE_SPEAKER", None) or shared.ACTIVE_SPEAKER


def nom_interlocuteur():
    """Prénom de la personne qui parle (« Neyor », « Clara »...), ou "" pour un invité."""
    profil = profil_actif()
    if not profil or profil == "guest":
        return ""
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
