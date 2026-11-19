"""Briefing du matin (module/briefing.py) : reconnaissance de la demande et phrase composée, sans réseau."""
import asyncio
import builtins
from datetime import datetime

import pytest

from module import briefing as b

LUNDI_9H = datetime(2026, 11, 16, 9, 0)


@pytest.mark.parametrize("phrase", ["ma journee", "jarvis mon briefing du matin", "resume de ma journee", "qu est ce que j ai aujourd hui", "quoi de prevu aujourd hui", "le programme du jour"])
def test_demandes_reconnues(phrase):
    assert b.demande(phrase)


@pytest.mark.parametrize("phrase", ["quelle heure est il", "mets de la musique", "ouvre la vue de dieu"])
def test_phrases_ignorees(phrase):
    assert not b.demande(phrase)


def test_briefing_complet():
    p = b.composer(LUNDI_9H, meteo="À Lyon, il fait 8 degrés et le ciel est dégagé",
                   evenements=[(datetime(2026, 11, 16, 14, 30), "Dentiste"), (None, "Anniversaire de Clara")], taches=["Payer le loyer"],
                   alarmes=[(datetime(2026, 11, 16, 18, 0), "Sport")], mails=3, nom="Neyor")
    assert p.startswith("Bonjour Neyor. Nous sommes lundi 16 novembre. À Lyon, il fait 8 degrés")
    assert "Dentiste à 14 h 30 et Anniversaire de Clara, toute la journée" in p
    assert "1 tâche à faire : Payer le loyer." in p and "Sport à 18 h" in p and "3 mails non lus" in p


def test_sources_en_panne_passees_sous_silence_et_agenda_vide():
    p = b.composer(datetime(2026, 11, 16, 19, 0))
    assert p == "Bonsoir. Nous sommes lundi 16 novembre."
    assert "Rien à l'agenda" in b.composer(LUNDI_9H, evenements=[]) and "Aucun mail non lu" in b.composer(LUNDI_9H, mails=0)
    assert "1 mail non lu." in b.composer(LUNDI_9H, mails=1)


def test_longues_listes_resumees():
    ev = [(datetime(2026, 11, 16, h, 0), f"R{h}") for h in range(8, 15)]
    p = b.composer(LUNDI_9H, evenements=ev, taches=["a", "b", "c", "d", "e"])
    assert "et 2 autres." in p and "5 tâches à faire : a, b et c, et 2 de plus." in p


def test_resolver_de_bout_en_bout(monkeypatch):
    from plugins import briefing_resolver as r
    monkeypatch.setattr(b, "SOURCES", {"meteo": lambda: None, "evenements": lambda: [], "taches": lambda: None, "mails": lambda: 2, "alarmes": lambda: []})
    monkeypatch.setattr(r, "nom_interlocuteur", lambda: "Clara")
    rep = asyncio.run(r.resoudre_briefing("Jarvis, ma journée"))
    assert rep.startswith(("Bonjour Clara.", "Bonsoir Clara.")) and "Rien à l'agenda" in rep and "2 mails non lus" in rep
    assert asyncio.run(r.resoudre_briefing("mets de la musique")) is None
    assert builtins.resoudre_briefing is r.resoudre_briefing
