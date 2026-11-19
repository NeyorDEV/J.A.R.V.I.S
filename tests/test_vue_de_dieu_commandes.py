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


def recherche_parking(phrase, monkeypatch, tmp_path, parkings, geo=None, installee=False):
    """« trouve-moi un parking… » de bout en bout, géocodage, données et vue de Dieu remplacés (rien n'est téléchargé ni ouvert)."""
    import json
    from core import web_bridge
    from module import gev_donnees_fr as don
    (tmp_path / "parkings.json").write_text(json.dumps(parkings), encoding="utf-8")
    monkeypatch.setattr(don, "DOSSIER", str(tmp_path))
    monkeypatch.setattr(don, "age", lambda nom: 0.0)   # fichier « frais » : pas de téléchargement
    async def geocode(lieu):
        return geo if geo is not None else {"lat": 45.4397, "lon": 4.3872, "nom": "Saint-Étienne, Loire, France", "importance": 0.7, "rang": 16}
    monkeypatch.setattr(web_bridge, "geocode_lieu_detaille", geocode)
    monkeypatch.setattr(r.vdd, "installee", lambda: installee)
    ouvertures = []
    async def montrer(lat, lon, ouvrir):
        ouvertures.append((lat, lon, ouvrir))
    monkeypatch.setattr(r, "_montrer_parkings", montrer)
    async def lancer():
        rep = await r.resoudre_vue_de_dieu(phrase)
        await asyncio.sleep(0)   # laisse partir la tâche « montrer »
        return rep
    return asyncio.run(lancer()), ouvertures


def _parking(nom, lat, lon, places=100, libres=None, statut=None):
    return [nom, "", lat, lon, places, 0, 0, 0, 0, None, None, "X", "", libres, "", statut]


def test_trouve_un_parking_repond_a_la_voix(monkeypatch, tmp_path):
    rep, ouvertures = recherche_parking("ouvre la vue de Dieu et trouve-moi un parking ouvert à Saint-Étienne", monkeypatch, tmp_path,
                                        [_parking("Hôtel de ville", 45.440, 4.388, 325), _parking("Loin", 48.85, 2.35)])
    assert rep.startswith("Près de Saint-Étienne, le plus proche : Hôtel De Ville") or rep.startswith("Près de Saint-Étienne, le plus proche : Hôtel de ville")
    assert "disponibilité en direct non communiquée" in rep and "ne peux pas garantir" in rep and ouvertures == []   # vue non installée : rien à ouvrir


def test_trouve_un_parking_montre_la_zone_si_la_vue_est_installee(monkeypatch, tmp_path):
    rep, ouvertures = recherche_parking("ouvre la vue de dieu et trouve moi un parking libre à nantes", monkeypatch, tmp_path,
                                        [_parking("Talensac", 47.2185, -1.5546, 320, 217, "ouvert")], {"lat": 47.2184, "lon": -1.5536, "nom": "Nantes, Loire-Atlantique", "importance": 0.8}, installee=True)
    assert "217 places libres sur 320" in rep and ouvertures == [(47.2184, -1.5536, True)]


def test_lieu_inconnu(monkeypatch, tmp_path):
    rep, _ = recherche_parking("trouve moi un parking à zzzzville", monkeypatch, tmp_path, [], {"lat": 0, "lon": 0, "nom": "Zzz", "importance": 0.05})
    assert rep.startswith("Je ne trouve pas « zzzzville » sur la carte")


def test_lieu_precis_introuvable_retombe_sur_la_ville(monkeypatch, tmp_path):
    import json
    from core import web_bridge
    from module import gev_donnees_fr as don
    (tmp_path / "parkings.json").write_text(json.dumps([_parking("Talensac", 47.2185, -1.5546, 320, 217, "ouvert")]), encoding="utf-8")
    monkeypatch.setattr(don, "DOSSIER", str(tmp_path))
    monkeypatch.setattr(don, "age", lambda nom: 0.0)
    demandes = []
    async def geocode(lieu):
        demandes.append(lieu)
        return {"lat": 47.2184, "lon": -1.5536, "nom": "Nantes, France", "importance": 0.8} if lieu == "nantes" else {"lat": 0, "lon": 0, "nom": "Une gare", "importance": 0.05}
    monkeypatch.setattr(web_bridge, "geocode_lieu_detaille", geocode)
    monkeypatch.setattr(r.vdd, "installee", lambda: False)
    rep = asyncio.run(r.resoudre_vue_de_dieu("où me garer près de la gare de Nantes"))
    assert demandes == ["la gare de nantes", "nantes"] and rep.startswith("Près de Nantes, le plus proche : Talensac")
