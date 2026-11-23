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


def test_salutation_anglaise_suit_l_heure(monkeypatch):
    from core import i18n
    monkeypatch.setattr(i18n, "_langue", "en")
    assert b.composer(datetime(2026, 11, 16, 9, 0)).startswith("Good morning.")
    assert b.composer(datetime(2026, 11, 16, 15, 0)).startswith("Good afternoon.")
    assert b.composer(datetime(2026, 11, 16, 19, 0)).startswith("Good evening.")
    monkeypatch.setattr(i18n, "_langue", "fr")
    assert b.composer(datetime(2026, 11, 16, 15, 0)).startswith("Bonjour.") and b.composer(datetime(2026, 11, 16, 19, 0)).startswith("Bonsoir.")


class _Chaine:
    """Faux service Google : service.xxx().yyy(...).execute() renvoie la réponse préparée, sans réseau."""
    def __init__(self, reponse):
        self.reponse = reponse

    def __getattr__(self, _):
        return lambda *a, **k: self

    def execute(self):
        return self.reponse


def test_sources_google_avec_de_faux_services(monkeypatch):
    """Agenda, tâches et mails lus et mis en forme comme avec le vrai Google (jeton simulé valide) ; une panne de service donne None, jamais une erreur dite."""
    pytest.importorskip("google_auth_oauthlib")   # absent de l'environnement minimal de la CI
    import module.google_services as gs
    monkeypatch.setattr(b, "_google_pret", lambda: True)
    monkeypatch.setattr(gs, "service_agenda", lambda: _Chaine({"items": [{"start": {"dateTime": "2026-11-23T18:30:00+01:00"}, "summary": "Dentiste"}, {"start": {"date": "2026-11-23"}, "summary": "Anniversaire de Clara"}]}))
    monkeypatch.setattr(gs, "get_tasks_service", lambda: _Chaine({"items": [{"title": "Payer le loyer"}, {"title": "Appeler Léo"}]}))
    monkeypatch.setattr(gs, "service_gmail", lambda: _Chaine({"messages": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}))
    ev = b._agenda()
    assert [(d.hour if d else None, t) for d, t in ev] == [(18, "Dentiste"), (None, "Anniversaire de Clara")]
    assert b._taches() == ["Payer le loyer", "Appeler Léo"] and b._mails() == 3
    phrase = b.composer(datetime(2026, 11, 23, 9, 0), evenements=ev, taches=b._taches(), mails=b._mails())
    assert "Dentiste à 18 h 30" in phrase and "Anniversaire de Clara, toute la journée" in phrase and "2 tâches à faire" in phrase and "3 mails non lus" in phrase
    monkeypatch.setattr(gs, "service_agenda", lambda: (_ for _ in ()).throw(RuntimeError("panne")))
    assert b._agenda() is None   # panne : source passée sous silence
    monkeypatch.setattr(b, "_google_pret", lambda: False)
    assert b._taches() is None and b._mails() is None   # pas de jeton utilisable : aucune fenêtre de connexion ouverte, source ignorée
