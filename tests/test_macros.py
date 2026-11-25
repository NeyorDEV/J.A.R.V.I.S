"""Macros vocales (module/macros.py) : création, découpe des étapes, refus des commandes dangereuses, test à blanc, lancement. Sans JARVIS lancé, sans effet sur le PC."""
import asyncio

import pytest

from module import macros as M


@pytest.fixture(autouse=True)
def _fichier_temporaire(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "FICHIER", str(tmp_path / "macros.json"))


def dire(phrase):
    return asyncio.run(M.resoudre_macros(phrase))


def test_separer_etapes():
    assert M.separer_etapes("baisse la lumiere, mets le volume a 30 puis lance la tele") == ["baisse la lumiere", "mets le volume a 30", "lance la tele"]
    assert M.separer_etapes("allume la lumiere et lance la tele") == ["allume la lumiere", "lance la tele"]
    # « et » dans une étape : pas coupé devant autre chose qu'un verbe de commande
    assert M.separer_etapes("cherche chat et chien") == ["cherche chat et chien"]


def test_creation_quand_je_dis():
    statut, mac = M.analyser_creation("Quand je dis mode cinéma, baisse la lumière, mets le volume à 30 puis lance la télé")
    assert statut == "ok"
    assert mac == {"nom": "mode cinema", "etapes": ["baisse la lumiere", "mets le volume a 30", "lance la tele"]}


def test_creation_cree_une_macro():
    statut, mac = M.analyser_creation("crée une macro bonne nuit : éteins la lumière puis mets de la musique douce")
    assert statut == "interdit"   # « éteins » : effet sur le PC, refusé comme pour les routines
    statut, mac = M.analyser_creation("crée une macro bonne nuit : baisse la lumière puis mets de la musique douce")
    assert statut == "ok" and mac["nom"] == "bonne nuit" and len(mac["etapes"]) == 2


@pytest.mark.parametrize("phrase,statut", [
    ("quand je dis travail, ferme les applications", "interdit"),
    ("quand je dis travail, envoie un mail à Clara", "interdit"),
    ("quand je dis travail, ", None),
    ("quelle heure est-il", None),
    ("crée une macro : lance la musique", "nom"),
])
def test_creation_refus_et_non_macro(phrase, statut):
    res = M.analyser_creation(phrase)
    assert (res[0] if res else None) == statut


def test_enregistrement_liste_et_suppression():
    assert "enregistrée" in dire("quand je dis mode cinéma, baisse la lumière puis lance la télé")
    assert "mode cinema" in dire("quelles sont mes macros")
    assert "remplacée" in dire("quand je dis mode cinéma, baisse la lumière")
    assert "supprimée" in dire("supprime la macro mode cinéma")
    assert M.charger() == []
    assert "Aucune macro" in dire("liste mes macros")


def test_test_a_blanc_ne_lance_rien(monkeypatch):
    dire("quand je dis mode cinéma, baisse la lumière puis lance la télé")
    lances = []
    monkeypatch.setattr(M, "lancer", lambda mac, executer=None: lances.append(mac))
    rep = dire("teste à blanc mode cinéma")
    assert "rien n'est exécuté" in rep and "baisse la lumiere" in rep and "lance la tele" in rep
    assert lances == []
    assert dire("simule ce programme") is None   # aucune macro de ce nom


def test_lancement_par_phrase_exacte_et_par_nom(monkeypatch):
    dire("quand je dis mode cinéma, baisse la lumière puis lance la télé")
    lances = []
    monkeypatch.setattr(M, "lancer", lambda mac, executer=None: lances.append(mac["nom"]))
    assert "C'est parti" in dire("Jarvis, mode cinéma !")
    assert "C'est parti" in dire("lance la macro mode cinéma")
    assert dire("mode cinéma pour ce soir") is None   # phrase exacte seulement, sans « macro »
    assert lances == ["mode cinema", "mode cinema"]


def test_les_etapes_sont_rejouees_dans_l_ordre_et_les_interdites_sautees():
    mac = {"nom": "x", "etapes": ["baisse la lumiere", "supprime tout", "lance la tele"]}   # fichier modifié à la main
    vues = []

    async def executer(etape):
        vues.append(etape)

    async def scenario():
        await M.lancer(mac, executer)

    asyncio.run(scenario())
    assert vues == ["baisse la lumiere", "lance la tele"]


def test_une_etape_en_erreur_ne_bloque_pas_les_suivantes():
    mac = {"nom": "x", "etapes": ["a", "b"]}
    vues = []

    async def executer(etape):
        vues.append(etape)
        if etape == "a":
            raise RuntimeError("boum")

    async def scenario():
        await M.lancer(mac, executer)

    asyncio.run(scenario())
    assert vues == ["a", "b"]
