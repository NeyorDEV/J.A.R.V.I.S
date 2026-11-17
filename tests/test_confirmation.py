"""Réponse vocale à une confirmation : stricte pour les actions destructrices, simple pour une question."""
import pytest

from core.confirmation import interpreter_reponse

ACCORDS_NETS = ["oui", "Oui.", "oui, vas-y", "ouais", "ok", "d'accord", "oui merci", "oui, je confirme", "oui s'il te plaît", "vas-y fais-le", "oui pas de souci",
                "oui, tout à fait", "oui jarvis", "c'est bon", "confirme", "go"]
REFUS_NETS = ["non", "Non.", "non merci", "annule", "stop", "surtout pas", "pas question", "laisse tomber", "oui non attends", "non, n'y va pas", "attends", "ce n'est pas bon"]
OUI_AVEC_RESERVE = ["oui mais mets Marie en copie", "oui, et mets Marie en copie", "oui, mets Marie en copie", "oui plutôt demain", "oui sauf le dossier photos", "oui si tu veux",
                    "oui, c'est bon ?", "oui ou non ?", "oui qu'est-ce que tu fais", "oui avec une copie", "oui puis ferme tout"]
SANS_RAPPORT = ["quelle heure est-il", "mets de la musique", "active la vue de dieu"]


@pytest.mark.parametrize("phrase", ACCORDS_NETS)
def test_accord_net_valide_en_mode_strict(phrase):
    assert interpreter_reponse(phrase, strict=True) is True


@pytest.mark.parametrize("phrase", REFUS_NETS)
def test_refus_en_mode_strict(phrase):
    assert interpreter_reponse(phrase, strict=True) is False


@pytest.mark.parametrize("phrase", OUI_AVEC_RESERVE)
def test_oui_avec_condition_ou_demande_vaut_refus_en_mode_strict(phrase):
    assert interpreter_reponse(phrase, strict=True) is False


@pytest.mark.parametrize("phrase", SANS_RAPPORT)
def test_phrase_sans_rapport_n_est_pas_consommee(phrase):
    assert interpreter_reponse(phrase, strict=True) is None
    assert interpreter_reponse(phrase, strict=False) is None


def test_mode_simple_question_garde_la_regle_historique():
    assert interpreter_reponse("oui mais mets Marie en copie", strict=False) is True   # simple question non destructive
    assert interpreter_reponse("non merci", strict=False) is False
    assert interpreter_reponse("oui", strict=False) is True


def test_vide():
    assert interpreter_reponse("", strict=True) is None
    assert interpreter_reponse("   ", strict=False) is None
