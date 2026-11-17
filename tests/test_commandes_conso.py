"""Commandes vocales « quota Groq » et « dépenses Gemini » : phrases reconnues, et phrases voisines laissées aux autres résolveurs."""
import asyncio
import builtins

import pytest

builtins.CONNECTED_CLIENTS = []
from core import usage_llm, usage_stt  # noqa: E402
from plugins import cout_llm_resolver, quota_stt_resolver  # noqa: E402


@pytest.fixture(autouse=True)
def compteurs_vides(monkeypatch):
    monkeypatch.setattr(usage_stt, "_compteur", usage_stt.CompteurQuota())
    monkeypatch.setattr(usage_llm, "_compteur", usage_llm.CompteurLLM(surcharges={"m": [1.0, 1.0]}, usd_en_eur=1.0))


def dit(resolveur, phrase):
    return asyncio.run(resolveur(phrase))


@pytest.mark.parametrize("phrase", ["quota groq", "combien de requêtes j'ai envoyées à Groq", "consommation de la reconnaissance vocale", "état de la reconnaissance vocale", "limites de groq",
                                    "jarvis donne-moi le quota de grock.", "quota de grok", "combien de requêtes j'ai faites chez groc", "donne moi la consommation de groque"])
def test_quota_reconnu(phrase):
    assert "requêtes" in dit(quota_stt_resolver.resoudre_quota_stt, phrase)


def test_pas_de_ponctuation_doublee_avant_le_prenom():
    for resolveur, phrase in ((quota_stt_resolver.resoudre_quota_stt, "quota groq"), (cout_llm_resolver.resoudre_cout_llm, "budget ia")):
        r = dit(resolveur, phrase)
        assert ".," not in r and ". ," not in r and r.endswith(".") and not r.endswith("..")


def test_ecriture_approximative_precise_le_service():
    assert dit(quota_stt_resolver.resoudre_quota_stt, "donne-moi le quota de grock").startswith("Je suppose que vous parlez de Groq")
    assert not dit(quota_stt_resolver.resoudre_quota_stt, "quota groq").startswith("Je suppose")


@pytest.mark.parametrize("phrase", ["mets de la musique", "quelle est la limite de vitesse", "reconnais cette musique", "combien de temps pour aller à Lyon", "mets un son de grock"])
def test_quota_laisse_les_autres_phrases(phrase):
    assert dit(quota_stt_resolver.resoudre_quota_stt, phrase) is None


@pytest.mark.parametrize("phrase", ["combien coûte gemini aujourd'hui", "mes dépenses d'IA", "budget ia", "consommation gemini", "combien j'ai dépensé en intelligence artificielle", "le coût de l'ia", "combien coûte jemini", "donne-moi la consommation de djemini"])
def test_cout_reconnu(phrase):
    assert "Gemini" in dit(cout_llm_resolver.resoudre_cout_llm, phrase)


@pytest.mark.parametrize("phrase", ["mets de la musique", "coût du carburant", "quel est le budget courses", "ajoute du lait à la liste de courses", "combien de requêtes pour Groq"])
def test_cout_laisse_les_autres_phrases(phrase):
    assert dit(cout_llm_resolver.resoudre_cout_llm, phrase) is None
