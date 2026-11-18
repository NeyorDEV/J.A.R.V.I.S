"""Locuteur d'une commande (core/locuteur.py) : le clavier du HUD est le créateur, la voix garde la biométrie."""
import pytest

from core.locuteur import locuteur_effectif


@pytest.mark.parametrize("de_confiance,from_voice,courant,attendu", [
    (True, False, "guest", "neyor"),    # clavier du HUD alors que JARVIS est en « invité » au démarrage : la régression du 17/11
    (True, False, "clara", "neyor"),
    (False, True, "clara", "clara"),    # voix : la biométrie décide
    (False, True, "guest", "guest"),
    (True, True, "guest", "guest"),     # routine ou voix de confiance : la voix l'emporte, jamais d'élévation
    (False, False, "", "guest"),
])
def test_locuteur(de_confiance, from_voice, courant, attendu):
    assert locuteur_effectif(de_confiance, from_voice, courant) == attendu


def test_profils_enroles(tmp_path):
    from core.locuteur import profils_enroles
    assert not profils_enroles(str(tmp_path / "absent"))      # dossier absent : premier lancement
    assert not profils_enroles(str(tmp_path))                 # dossier vide
    (tmp_path / "neyor").mkdir()
    assert not profils_enroles(str(tmp_path))                 # profil vide : rien d'exploitable à protéger
    (tmp_path / "neyor" / "sample_1.wav").write_bytes(b"x")
    assert profils_enroles(str(tmp_path))                     # un profil existe : jamais « neyor » par défaut pour tout le monde
