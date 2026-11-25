"""Conversation continue (core/conversation.py, plugins/conversation_resolver.py) : fin par le sens, délais de session, mode continu."""
import asyncio

import pytest

import core.shared as shared
from core import conversation as C


@pytest.mark.parametrize("phrase,fin", [
    ("c'est tout", True),
    ("Jarvis, ce sera tout, merci", True),
    ("merci c'est bon", True),
    ("à plus tard", True),
    ("bonne nuit Jarvis", True),
    ("that's all", True),
    ("goodbye", True),
    ("merci", False),                                               # un simple merci ne ferme pas la session
    ("mets de la musique", False),
    ("c'est tout à fait ça, ajoute du lait à la liste de courses", False),   # trop long pour être une fin
    ("", False),
])
def test_est_fin(phrase, fin):
    assert C.est_fin(phrase) is fin


def test_attend_une_reponse():
    assert C.attend_une_reponse("Voulez-vous que je continue ?")
    assert C.attend_une_reponse("Quelle heure ? ")
    assert not C.attend_une_reponse("Il est dix heures.") and not C.attend_une_reponse("")


def test_delais():
    assert C.delai_session(20, False, False) == 20
    assert C.delai_session(20, True, False) == 20 + C.BONUS_QUESTION
    assert C.delai_session(20, False, True) == C.DELAI_CONTINU
    assert C.delai_session(20, True, True) == C.DELAI_CONTINU   # le mode continu l'emporte, pas de cumul


def test_mode_continu_se_souvient_et_delai_courant():
    assert C.mode_continu() is False
    assert C.delai_courant(20) == 20
    assert C.definir_continu(True) and C.mode_continu()
    assert C.delai_courant(20) == C.DELAI_CONTINU
    assert C.definir_continu(False) and not C.mode_continu()


def test_delai_courant_prolonge_apres_une_question(monkeypatch):
    from core import repeter
    monkeypatch.setattr(repeter, "derniere_reponse", lambda *a, **k: "Je lance la musique ?")
    assert C.delai_courant(20) == 20 + C.BONUS_QUESTION
    monkeypatch.setattr(repeter, "derniere_reponse", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boum")))
    assert C.delai_courant(20) == 20   # jamais d'exception : délai de base


def test_resolver_active_desactive_et_ferme_la_session(monkeypatch):
    from plugins import conversation_resolver as R
    assert "activée" in asyncio.run(R.resoudre_conversation("active la conversation continue")) and C.mode_continu()
    assert "désactivée" in asyncio.run(R.resoudre_conversation("désactive la conversation continue")) and not C.mode_continu()
    monkeypatch.setattr(shared, "jarvis_actif", True)
    assert "votre service" in asyncio.run(R.resoudre_conversation("Jarvis, c'est tout"))
    assert shared.jarvis_actif is False
    monkeypatch.setattr(shared, "jarvis_actif", True)
    assert asyncio.run(R.resoudre_conversation("mets de la musique")) is None
    assert shared.jarvis_actif is True
