"""Qui parle pour UNE commande. Pur (sans dépendance) : testé dans tests/test_locuteur.py."""


def locuteur_effectif(de_confiance: bool, from_voice: bool, courant: str) -> str:
    """Le clavier du HUD local (de_confiance, pas de voix) est le créateur ; sinon on garde le locuteur reconnu par la biométrie (« guest » par défaut)."""
    return "neyor" if (de_confiance and not from_voice) else (courant or "guest")


def profils_enroles(dossier: str) -> bool:
    """True si le dossier des empreintes vocales contient au moins un profil non vide. Sert à ne JAMAIS donner les droits du créateur à tout le monde
    quand la biométrie est absente ou illisible alors que des profils existent (seul un premier lancement, sans aucun profil, garde « neyor » par défaut)."""
    import os
    try:
        return any(os.listdir(os.path.join(dossier, p)) for p in os.listdir(dossier) if os.path.isdir(os.path.join(dossier, p)))
    except OSError:
        return False
