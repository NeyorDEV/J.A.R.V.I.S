"""Filtre des phrases que Whisper invente sur du bruit : à écarter, sans jamais bloquer une vraie commande."""
import pytest

from core.hallucinations import est_hallucination

A_ECARTER = [
    "Sous-titres réalisés par la communauté d'Amara.org", "Sous-titres par Amara.org", "Sous-titrage ST' 501", "Sous-titrage Société Radio-Canada", "Sous-titres société Radio-Canada",
    "Merci d'avoir regardé cette vidéo !", "Merci d'avoir regardé.", "N'oubliez pas de vous abonner à la chaîne", "Pensez à vous abonner", "Abonnez-vous", "À la prochaine vidéo !",
    "Merci.", "Merci beaucoup", "Merci à tous.", "Bonjour", "Thank you", "Sous-titrage", "…Sous-titres réalisés par la communauté d'Amara.org",
]
VRAIES_COMMANDES = [
    "active les sous-titres", "mets les sous titres", "passe à la prochaine vidéo", "jarvis merci d'avoir lancé la musique", "merci jarvis", "bonjour jarvis", "jarvis quelle heure est-il",
    "mets Radio-Canada", "abonne-moi à la newsletter", "ouvre la vue de dieu", "", "   ", "à la prochaine, jarvis",
]


@pytest.mark.parametrize("phrase", A_ECARTER)
def test_hallucination_ecartee(phrase):
    assert est_hallucination(phrase) is True


@pytest.mark.parametrize("phrase", VRAIES_COMMANDES)
def test_vraie_commande_conservee(phrase):
    assert est_hallucination(phrase) is False
