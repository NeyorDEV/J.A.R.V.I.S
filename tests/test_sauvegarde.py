"""Sauvegarde et restauration (core/sauvegarde.py + plugins/sauvegarde_resolver.py), dans un dossier temporaire : aucune vraie donnée touchée."""
import asyncio
import datetime
import os

import pytest

from core import sauvegarde as S


@pytest.fixture
def donnees(monkeypatch, tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(S, "_DATA", str(data))
    monkeypatch.setattr(S, "DOSSIER", str(data / "sauvegardes"))
    (data / "jarvis_memoire.json").write_text('{"a": 1}', encoding="utf-8")
    (data / "macros.json").write_text('{"macros": []}', encoding="utf-8")
    return data


def test_une_copie_par_jour(donnees):
    jour = datetime.date(2026, 11, 20)
    assert S.sauvegarder(jour) is not None
    assert S.sauvegarder(jour) is None            # déjà faite aujourd'hui
    assert S.sauvegarder(jour, forcer=True) is not None
    assert sorted(os.listdir(os.path.join(S.DOSSIER, "2026-11-20"))) == ["jarvis_memoire.json", "macros.json"]


def test_rien_a_sauvegarder_sans_fichier(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "_DATA", str(tmp_path))
    monkeypatch.setattr(S, "DOSSIER", str(tmp_path / "sauvegardes"))
    assert S.sauvegarder(datetime.date(2026, 11, 20)) is None
    assert not (tmp_path / "sauvegardes").exists()


def test_seules_les_14_plus_recentes_sont_gardees(donnees):
    for i in range(20):
        S.sauvegarder(datetime.date(2026, 11, 1) + datetime.timedelta(days=i), forcer=True)
    jours = S.lister()
    assert len(jours) == S.GARDER and jours[0] == datetime.date(2026, 11, 20)


def test_choisir_hier_date_precise_ou_derniere(donnees):
    for j in (10, 12, 15):
        S.sauvegarder(datetime.date(2026, 11, j), forcer=True)
    assert S.choisir() == datetime.date(2026, 11, 15)
    assert S.choisir(avant=datetime.date(2026, 11, 15)) == datetime.date(2026, 11, 12)
    assert S.choisir(jour=datetime.date(2026, 11, 10)) == datetime.date(2026, 11, 10)
    assert S.choisir(jour=datetime.date(2026, 11, 11)) is None


def test_restauration_garde_l_etat_actuel_a_part(donnees):
    S.sauvegarder(datetime.date(2026, 11, 12))
    (donnees / "jarvis_memoire.json").write_text('{"a": 2}', encoding="utf-8")
    assert "jarvis_memoire.json" in S.restaurer(datetime.date(2026, 11, 12))
    assert (donnees / "jarvis_memoire.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert (donnees / "sauvegardes" / S.AVANT / "jarvis_memoire.json").read_text(encoding="utf-8") == '{"a": 2}'
    assert S.restaurer(datetime.date(2026, 1, 1)) == []


def test_resolver_demande_confirmation_avant_de_restaurer(donnees, monkeypatch):
    from core import confirmation
    from plugins import sauvegarde_resolver as R
    S.sauvegarder(datetime.date.today() - datetime.timedelta(days=1))
    (donnees / "jarvis_memoire.json").write_text('{"a": 9}', encoding="utf-8")
    reponses = [False, True]
    questions = []

    async def faux(websocket, message, **kw):
        questions.append(message)
        return reponses.pop(0)

    monkeypatch.setattr(confirmation, "demander_confirmation", faux)
    assert "ne touche à rien" in asyncio.run(R.resoudre_sauvegarde("restaure la sauvegarde d'hier"))
    assert (donnees / "jarvis_memoire.json").read_text(encoding="utf-8") == '{"a": 9}'   # refusé : intact
    assert "restaurée" in asyncio.run(R.resoudre_sauvegarde("restaure la sauvegarde d'hier"))
    assert (donnees / "jarvis_memoire.json").read_text(encoding="utf-8") == '{"a": 1}'
    assert len(questions) == 2 and "Restaurer" in questions[0]


def test_resolver_ignore_les_autres_phrases(donnees):
    from plugins import sauvegarde_resolver as R
    assert asyncio.run(R.resoudre_sauvegarde("quelle heure est-il")) is None
    assert asyncio.run(R.resoudre_sauvegarde("fais une sauvegarde")).startswith("Rien à sauvegarder") is False   # fichiers présents : sauvegarde faite
