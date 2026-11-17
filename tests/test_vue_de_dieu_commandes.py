"""Commandes vocales de la Vue de Dieu : « ouvre la vue de Dieu avec… » et pilotage des couches (analyse des phrases, sans ouvrir l'appli)."""
import asyncio
import builtins

import pytest

builtins.CONNECTED_CLIENTS = []   # attendu par le resolver à l'import (injecté par JARVIS au démarrage)
from plugins import vue_de_dieu_resolver as r  # noqa: E402


@pytest.mark.parametrize("phrase,attendu", [
    ("lance la vue de dieu avec les bouchons activés", ["bouchons"]),
    ("ouvre la vue de dieu avec les carburants et les bornes allumées", ["carburants", "bornes"]),
    ("active la vue de dieu avec le scan seveso", ["scan seveso"]),
    ("lance la vue de dieu avec la couche seveso activée", ["seveso"]),
    ("ouvre la vue de dieu avec le trafic routier d'ouvert", ["trafic routier"]),   # transcription fréquente de « ouvert »
    ("active la vue de dieu", []),
    ("ferme la vue de dieu", []),
])
def test_couches_demandees(phrase, attendu):
    assert r._couches_demandees(r._clean(phrase)) == attendu


class Faux:
    """Remplace l'envoi à l'appli : mémorise l'ordre et répond comme la page."""
    def __init__(self, reponses):
        self.ordres, self.reponses = [], list(reponses)

    async def __call__(self, cmd, delai=6.0):
        self.ordres.append(cmd)
        return self.reponses.pop(0) if self.reponses else None


def pilotage(phrase, reponses, monkeypatch):
    faux = Faux(reponses)
    monkeypatch.setattr(r, "_ordre", faux)
    return asyncio.run(r._pilotage(r._clean(phrase))), faux.ordres


def test_active_une_couche(monkeypatch):
    rep, ordres = pilotage("active la couche carburants", [(True, "Couche Prix des carburants activée.")], monkeypatch)
    assert rep == "Couche Prix des carburants activée." and ordres == [{"op": "couche", "nom": "carburants", "etat": True}]


def test_desactive_toutes_les_couches(monkeypatch):
    rep, ordres = pilotage("désactive toutes les couches", [(True, "3 couches désactivées.")], monkeypatch)
    assert rep == "3 couches désactivées." and ordres[0]["op"] == "toutes_off"


def test_phrase_qui_n_est_pas_une_couche_retombe_sur_les_autres_resolvers(monkeypatch):
    rep, _ = pilotage("éteins le micro", [(False, "Je ne trouve pas de couche « micro ».")], monkeypatch)
    assert rep is None
    rep, ordres = pilotage("montre la météo", [], monkeypatch)
    assert rep is None and ordres == []   # « météo » reste au resolver météo, sans même interroger l'appli


def test_article_les_n_est_pas_coupe(monkeypatch):
    _, ordres = pilotage("active les séismes", [(True, "ok")], monkeypatch)
    assert ordres[0]["nom"] == "seismes"   # pas « s seismes »
