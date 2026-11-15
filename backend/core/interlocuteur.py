"""Nom de la personne qui parle à JARVIS, et identité de son créateur.

JARVIS s'adresse à la personne qui lui a donné l'instruction : le profil reconnu par
la biométrie vocale (« Neyor », « Clara »...), ou le créateur pour le clavier du HUD
local. Un invité non reconnu n'est pas nommé.

Seules les informations relatives au créateur (son identité, ses droits) restent
écrites en dur, avec CREATEUR / NOM_CREATEUR.
"""

import builtins
import re
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
    infos = [str(i).strip() for i in infos if str(i).strip()]
    age = _age_depuis_naissance(infos)
    if age is None:
        return infos
    # L'âge est recalculé chaque jour depuis la date de naissance : la ligne « Age : N ans » écrite à la main est remplacée
    return [f"Age : {age} ans" if re.match(r"(?i)^[aâ]ge\b", i) else i for i in infos] if any(re.match(r"(?i)^[aâ]ge\b", i) for i in infos) else [f"Age : {age} ans", *infos]


_MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]


def _age_depuis_naissance(infos):
    """Âge en années d'après une ligne « Date de naissance : 23 Avril 2007 » (accents facultatifs), ou None."""
    import unicodedata
    from datetime import date
    for ligne in infos:
        t = "".join(c for c in unicodedata.normalize("NFD", ligne.lower()) if unicodedata.category(c) != "Mn")
        m = re.search(r"naissance\s*:?\s*(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
        if m and m.group(2) in _MOIS:
            j, mois, an = int(m.group(1)), _MOIS.index(m.group(2)) + 1, int(m.group(3))
            auj = date.today()
            return auj.year - an - ((auj.month, auj.day) < (mois, j))
    return None


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
