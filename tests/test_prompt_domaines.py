"""Prompt système par domaines (core/prompt_builder.py) : le noyau est toujours là, le catalogue d'actions suit la phrase, et le doute envoie tout."""
import builtins

import pytest

try:   # dépendances de l'appli absentes de la CI minimale : fichier ignoré
    from core import prompt_builder as pb
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


@pytest.fixture(autouse=True)
def createur(monkeypatch):
    monkeypatch.setattr(builtins, "ACTIVE_SPEAKER", "neyor", raising=False)
    monkeypatch.setattr(pb, "composer_contexte_memoire", lambda: "")
    import core.shared as shared
    monkeypatch.setattr(shared, "historique", [])


def _p(texte=None):
    return pb.composer_prompt_systeme(souvenirs="", texte=texte)


def test_sans_phrase_tout_le_catalogue():
    p = _p(None)
    for action in ("spotify_rechercher", "alarme_set", "read_emails", "ha_action", "antivirus_scan", "dom_sequence", "rechercher_fichier"):
        assert f'"{action}"' in p


def test_question_noyau_seulement():
    p = _p("quelle est la capitale du Japon")
    assert "REGLE ABSOLUE" in p and "VOUVOIEMENT" in p and "auto_memoriser" in p   # noyau + apprentissage continu
    assert '"spotify_rechercher"' not in p and '"alarme_set"' not in p and '"read_emails"' not in p
    assert len(p) < len(_p(None)) * 0.5


def test_domaine_suit_la_phrase():
    p = _p("réveille-moi demain à 7 heures")
    assert '"alarme_set"' in p and '"spotify_rechercher"' not in p and '"read_emails"' not in p
    p = _p("lis mes mails")
    assert '"read_emails"' in p and '"alarme_set"' not in p


def test_plusieurs_domaines():
    p = _p("allume la lumière et mets du jazz")
    assert '"ha_action"' in p and '"spotify_rechercher"' in p and '"read_emails"' not in p


def test_ordre_inconnu_recoit_tout():
    assert _p("fais un truc incroyable") == _p(None)   # pas une question, aucun domaine reconnu : jamais d'action rendue impossible


def test_le_contexte_de_la_conversation_compte(monkeypatch):
    import core.shared as shared

    class Part:
        text = "mets de la musique"

    class Msg:
        role, parts = "user", [Part()]
    monkeypatch.setattr(shared, "historique", [Msg()])
    assert '"spotify_suivant"' in _p("et la deuxième ?")      # sans l'historique : question seule, aucun catalogue
    monkeypatch.setattr(shared, "historique", [])
    assert '"spotify_suivant"' not in _p("et la deuxième ?")


def test_la_fin_du_prompt_reste_la_regle_absolue():
    p = _p("quelle heure est-il demain")
    assert p.index("REGLE ABSOLUE") > p.index("REGLES DE SECURITE JSON") and p.index("CONSIGNE DE TEMPS") > p.index("REGLE ABSOLUE")
