"""Recherche de parkings à la voix (module/gev_parkings.py) : reconnaissance de la phrase, classement par distance, phrase dite. Sans réseau."""
import pytest

from module import gev_parkings as gp


@pytest.mark.parametrize("phrase,lieu,libre,gratuit,ouvert", [
    ("trouve moi un parking ouvert a saint etienne", "saint etienne", False, False, True),
    ("ouvre la vue de dieu et trouve moi un parking ouvert a saint etienne", "saint etienne", False, False, True),
    ("ou est ce que je peux me garer pres de la gare de lyon", "la gare de lyon", False, False, False),
    ("cherche un parking gratuit a nantes", "nantes", False, True, False),
    ("y a t-il un parking libre autour de la place bellecour", "la place bellecour", True, False, False),
    ("trouve moi un parking a proximite de l'hotel de ville", "l hotel de ville", False, False, False),
    ("cherche un parking dans le centre de clermont ferrand", "clermont ferrand", False, False, False),
])
def test_demandes_reconnues(phrase, lieu, libre, gratuit, ouvert):
    assert gp.demande(phrase) == {"lieu": lieu, "libre": libre, "gratuit": gratuit, "ouvert": ouvert}


@pytest.mark.parametrize("phrase", [
    "active les parkings", "montre les parkings a saint etienne", "affiche la couche parkings en direct", "trouve un parking",   # commande de couche, ou pas de lieu
    "cherche un parking dans la vue de dieu", "quelle heure est il a paris", "mets de la musique a fond", "trouve moi un restaurant a lyon",
])
def test_phrases_ignorees(phrase):
    assert gp.demande(phrase) is None


def _p(nom, lat, lon, places=100, gratuit=0, libres=None, statut=None):
    return [nom, "", lat, lon, places, gratuit, 0, 0, 0, None, None, "X", "", libres, "", statut]


PARKINGS = [_p("Proche", 45.440, 4.388, libres=0, statut="complet"), _p("Loin", 45.470, 4.388), _p("Moyen", 45.445, 4.390, libres=30, statut="ouvert"),
            _p("Gratuit", 45.452, 4.391, gratuit=1), _p("Ferme", 45.4402, 4.3881, libres=None, statut="ferme"), _p("Hors zone", 48.85, 2.35)]


def test_classement_par_distance_et_filtres():
    noms = lambda **kw: [p[0] for _, p in gp.classer(PARKINGS, 45.4397, 4.3872, **kw)]   # noqa: E731
    assert noms() == ["Proche", "Ferme", "Moyen"]
    assert noms(ouvert=True) == ["Proche", "Moyen", "Gratuit"]   # « Ferme » écarté ; « Proche » (complet, mais ouvert) reste
    assert noms(libre=True) == ["Moyen", "Gratuit"]              # « Proche » est complet, « Ferme » fermé ; le comptage confirmé passe devant
    assert noms(gratuit=True) == ["Gratuit"]


def test_rayon_elargi_puis_vide():
    assert gp.classer([_p("A", 45.50, 4.39)], 45.4397, 4.3872)[0][1][0] == "A"   # ~7 km : au-delà de 3 km, élargi à 9 km
    assert gp.classer([_p("B", 46.5, 4.39)], 45.4397, 4.3872) == []


def test_phrase_dite_sans_promettre_plus_que_les_donnees():
    p = gp.phrase("Saint-Étienne", gp.classer(PARKINGS, 45.4397, 4.3872, ouvert=True), ouvert=True)
    assert p.startswith("Près de Saint-Étienne, le plus proche : Proche, à ") and "complet" in p and "30 places libres sur 100" in p
    sans_direct = gp.phrase("Lyon", [(0.3, _p("Sans comptage", 45.7, 4.8, places=200))], ouvert=True)
    assert "200 places, disponibilité en direct non communiquée" in sans_direct and "ne peux pas garantir" in sans_direct
    assert "aucun parking gratuit près de Paris" in gp.phrase("Paris", [], gratuit=True)
    assert gp.phrase("X", [(0.3, _p("Un", 45, 4, libres=1, statut="ouvert"))]).count("1 place libre sur 100") == 1
