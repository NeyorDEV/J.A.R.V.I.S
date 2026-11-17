"""Suivi des coûts Gemini : tarifs, facturation du cache et de la réflexion, alertes du plafond, mesure des appels du SDK."""
import asyncio
from types import SimpleNamespace

import pytest

from core import mesure_gemini
from core.usage_llm import CompteurLLM, cout_usd, prix_modele

T0 = 1_800_000_000.0
JOUR = 86400.0


def test_prix_par_nom_de_modele_le_plus_precis_gagne():
    assert prix_modele("gemini-3.5-flash-lite")[:2] == (0.30, 2.50)
    assert prix_modele("models/gemini-3.8-flash")[:2] == (0.75, 3.75)
    assert prix_modele("gemini-flash-latest") is None and prix_modele("gemini-pro-latest") is None
    assert prix_modele("gemini-3.8-flash", {"gemini-3.8-flash": [1.5, 7.5, 0.15]}) == (1.5, 7.5, 0.15)


def test_cout_distingue_le_cache():
    prix = (1.0, 4.0, 0.1)   # $/M
    assert cout_usd(prix, 1_000_000, 0) == pytest.approx(1.0)
    assert cout_usd(prix, 1_000_000, 0, cache=1_000_000) == pytest.approx(0.1)
    assert cout_usd(prix, 1_000_000, 500_000, cache=400_000) == pytest.approx(0.6 * 1.0 + 0.4 * 0.1 + 0.5 * 4.0)
    assert cout_usd(prix, 100, 0, cache=500) == pytest.approx(100 * 0.1 / 1e6)   # le cache ne dépasse jamais l'entrée


def test_totaux_du_jour_et_du_mois_en_euros():
    c = CompteurLLM(surcharges={"m": [1.0, 2.0]}, usd_en_eur=0.5)
    c.noter("m", 1_000_000, 1_000_000, maintenant=T0)          # 1 + 2 = 3 $
    c.noter("m", 1_000_000, 0, maintenant=T0 + 60)             # 1 $
    e = c.etat(T0 + 120)
    assert e["appels_jour"] == 2 and e["jour_eur"] == pytest.approx(2.0)   # 4 $ x 0,5
    c.noter("m", 1_000_000, 0, maintenant=T0 + JOUR)           # le lendemain : même mois (T0 est le 15/01/2027 à 08h)
    e = c.etat(T0 + JOUR + 1)
    assert e["jour_eur"] == pytest.approx(0.5) and e["mois_eur"] == pytest.approx(2.5)


def test_alertes_80_puis_100_pour_cent_une_fois_par_jour():
    c = CompteurLLM(surcharges={"m": [1.0, 1.0]}, plafond_eur=1.0, usd_en_eur=1.0)
    assert c.noter("m", 500_000, 0, maintenant=T0) == []                      # 0,50 € (50 %)
    a = c.noter("m", 400_000, 0, maintenant=T0 + 1)                          # 0,90 € (90 %)
    assert [n for n, _ in a] == [80]
    assert c.noter("m", 10_000, 0, maintenant=T0 + 2) == []                  # pas de nouvelle alerte à 80 %
    a = c.noter("m", 200_000, 0, maintenant=T0 + 3)                          # 1,12 €
    assert [n for n, _ in a] == [100]
    a = c.noter("m", 600_000, 0, maintenant=T0 + JOUR)                       # le lendemain : 0,60 € (60 %), rien
    assert a == []


def test_modele_sans_tarif_compte_les_jetons_mais_pas_les_euros():
    c = CompteurLLM(usd_en_eur=1.0)
    c.noter("gemini-pro-latest", 1000, 500, maintenant=T0)
    e = c.etat(T0 + 1)
    assert e["jour_eur"] == 0 and e["entree_jour"] == 1000 and e["sortie_jour"] == 500 and e["sans_prix"] == ["gemini-pro-latest"]
    assert "gemini-pro-latest" in c.resume_parle(T0 + 1) and "pas de tarif" in c.resume_parle(T0 + 1)


def test_persistance(tmp_path):
    f = str(tmp_path / "llm.json")
    c = CompteurLLM(f, surcharges={"m": [1.0, 1.0]}, usd_en_eur=1.0)
    c.noter("m", 1_000_000, 0, maintenant=T0)
    c.enregistrer()
    assert CompteurLLM(f, surcharges={"m": [1.0, 1.0]}, usd_en_eur=1.0).etat(T0 + 1)["jour_eur"] == pytest.approx(1.0)


def test_resume_parle_sans_appel_et_avec_appels():
    c = CompteurLLM(surcharges={"m": [1.0, 1.0]}, usd_en_eur=1.0, plafond_eur=5.0)
    assert "Aucun appel" in c.resume_parle(T0) and "moins d'un centime" in c.resume_parle(T0)
    c.noter("m", 1_000_000, 0, maintenant=T0)
    t = c.resume_parle(T0 + 1)
    assert "environ 1.00 euros sur 1 appels" in t and "20 % du plafond de 5 euros" in t


# --- mesure des appels du SDK : on enveloppe de vraies méthodes factices, comme le fait installer() sur google.genai ---------------------------------------------------
class Reponse:
    def __init__(self, entree, sortie, cache=0, reflexion=0, outils=0):
        self.usage_metadata = SimpleNamespace(prompt_token_count=entree, candidates_token_count=sortie, cached_content_token_count=cache, thoughts_token_count=reflexion, tool_use_prompt_token_count=outils)


@pytest.fixture
def compteur_espion(monkeypatch):
    notes = []

    class Faux:
        def noter(self, modele, entree, sortie, cache=0, maintenant=None):
            notes.append((modele, entree, sortie, cache))
            return []
    import core.usage_llm as u
    monkeypatch.setattr(u, "compteur", lambda: Faux())
    return notes


def test_noter_additionne_reflexion_et_outils(compteur_espion):
    mesure_gemini._noter("gemini-x", Reponse(100, 20, cache=40, reflexion=30, outils=10))
    assert compteur_espion == [("gemini-x", 110, 50, 40)]   # entrée = prompt + outils ; sortie = texte + réflexion


def test_reponse_sans_usage_ou_objet_inattendu_ne_plante_pas(compteur_espion):
    mesure_gemini._noter("gemini-x", SimpleNamespace(usage_metadata=None))
    mesure_gemini._noter("gemini-x", object())
    assert compteur_espion == []


def test_modele_lu_dans_les_arguments():
    assert mesure_gemini._modele((), {"model": "gemini-a"}) == "gemini-a"
    assert mesure_gemini._modele(("gemini-b",), {}) == "gemini-b"
    assert mesure_gemini._modele((), {}) == ""


def test_installer_enveloppe_le_sdk_et_compte_flux_et_appels(compteur_espion, monkeypatch):
    genai_models = pytest.importorskip("google.genai.models")   # absent en CI (seulement pytest + requests) : test ignoré là
    reponses = {"sync": Reponse(10, 5), "flux": [SimpleNamespace(usage_metadata=None), Reponse(7, 3), Reponse(8, 4)], "async": Reponse(20, 6)}

    def generate_content(self, *, model, contents=None):
        return reponses["sync"]

    def generate_content_stream(self, *, model, contents=None):
        yield from reponses["flux"]

    async def a_generate_content(self, *, model, contents=None):
        return reponses["async"]

    async def a_generate_content_stream(self, *, model, contents=None):
        async def it():
            for x in reponses["flux"]:
                yield x
        return it()

    monkeypatch.setattr(genai_models.Models, "generate_content", generate_content)
    monkeypatch.setattr(genai_models.Models, "generate_content_stream", generate_content_stream)
    monkeypatch.setattr(genai_models.AsyncModels, "generate_content", a_generate_content)
    monkeypatch.setattr(genai_models.AsyncModels, "generate_content_stream", a_generate_content_stream)
    monkeypatch.setattr(mesure_gemini, "_installe", False)
    assert mesure_gemini.installer() is True

    assert genai_models.Models.generate_content(None, model="m1").usage_metadata.prompt_token_count == 10
    assert len(list(genai_models.Models.generate_content_stream(None, model="m2"))) == 3

    async def ex():
        await genai_models.AsyncModels.generate_content(None, model="m3")
        return [x async for x in await genai_models.AsyncModels.generate_content_stream(None, model="m4")]
    assert len(asyncio.run(ex())) == 3
    assert compteur_espion == [("m1", 10, 5, 0), ("m2", 8, 4, 0), ("m3", 20, 6, 0), ("m4", 8, 4, 0)]   # flux : seul le dernier usage (cumulé) est compté
