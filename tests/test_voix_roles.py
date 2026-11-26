"""Plusieurs voix (core/voix_roles.py, plugins/voix_roles_resolver.py) : rôle d'une phrase, réglages par défaut et personnalisés, commandes vocales. Aucun son, aucune synthèse."""
import asyncio
import json

import pytest

from core import voix_roles as V


@pytest.mark.parametrize("texte,force,role", [
    ("Il est dix heures.", None, "quotidien"),
    ("Alerte : disque presque plein.", None, "alerte"),
    ("Attention, la batterie est faible.", None, "alerte"),
    ("mot " * 100, None, "lecture"),
    ("Il est dix heures.", "lecture", "lecture"),
    ("Il est dix heures.", "inconnu", "quotidien"),
])
def test_role_de(texte, force, role):
    assert V.role_de(texte, force) == role


def test_reglages_par_defaut_gardent_la_voix_habituelle():
    assert V.reglage("quotidien", "homme") == {"genre": "homme", "rate": "+20%", "pitch": "+0Hz"}   # comme avant : rate +20 %
    assert V.reglage("alerte", "femme")["pitch"] == "-12Hz" and V.reglage("alerte", "femme")["genre"] == "femme"
    assert V.reglage("lecture", "homme")["rate"] == "+8%"


def test_reglage_personnalise_et_valeurs_invalides_ignorees(tmp_path):
    from core import i18n
    with open(i18n._CONFIG, "w", encoding="utf-8") as f:
        json.dump({"voix_roles": {"lecture": {"genre": "femme", "rate": "+5%", "pitch": "bizarre"}, "alerte": {"genre": "robot", "rate": "vite"}}}, f)
    lecture = V.reglage("lecture", "homme")
    assert lecture == {"genre": "femme", "rate": "+5%", "pitch": "+0Hz"}   # pitch invalide : défaut
    assert V.reglage("alerte", "homme") == {"genre": "homme", "rate": "+25%", "pitch": "-12Hz"}


def test_definir_et_reinitialiser():
    assert V.definir("lecture", "femme") and V.reglage("lecture", "homme")["genre"] == "femme"
    assert V.definir("alerte", "homme") and V.reglage("lecture", "homme")["genre"] == "femme"   # l'autre rôle ne bouge pas
    assert not V.definir("inconnu", "femme") and not V.definir("lecture", "robot")
    assert V.reinitialiser() and V.reglage("lecture", "homme")["genre"] == "homme"


def test_les_voix_edge_existent_pour_chaque_role_et_langue():
    from core import i18n
    for role in V.ROLES:
        for genre in ("homme", "femme"):
            assert i18n.voix_edge(V.reglage(role, genre)["genre"]).endswith("Neural")


@pytest.mark.parametrize("phrase,attendu", [
    ("mets la voix féminine pour la lecture", ("regler", ("lecture", "femme"))),
    ("voix des alertes masculine", ("regler", ("alerte", "homme"))),
    ("je veux une voix de femme pour le quotidien", ("regler", ("quotidien", "femme"))),
    ("teste les voix", ("test", None)),
    ("réinitialise les voix", ("reinit", None)),
    ("change la voix en féminine", None),   # réglage global : commandes_locales
    ("quelle heure est-il", None),
    ("teste ta voix", None),
])
def test_analyse_commandes_voix(phrase, attendu):
    from plugins import voix_roles_resolver as R
    assert R.analyser(R._norm(phrase)) == attendu


def test_resolver_regle_et_teste(monkeypatch):
    pytest.importorskip("edge_tts")   # core.speech : absent de l'environnement minimal de la CI
    from core import speech
    from plugins import voix_roles_resolver as R
    dit = []
    monkeypatch.setattr(speech, "parler", lambda t, **kw: dit.append((t, kw.get("role"))))
    assert "féminine" in asyncio.run(R.resoudre_voix_roles("mets la voix féminine pour la lecture"))
    assert V.reglage("lecture", "homme")["genre"] == "femme"
    assert "trois voix" in asyncio.run(R.resoudre_voix_roles("teste les voix"))
    assert [r for _, r in dit] == ["quotidien", "alerte", "lecture"]
    assert asyncio.run(R.resoudre_voix_roles("quelle heure est-il")) is None
