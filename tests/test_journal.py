"""Journal consultable (core/audit_log.evenements_entre + plugins/journal_resolver) : lecture d'un journal temporaire, résumé parlé."""
import asyncio
import datetime
import json

import pytest

from core import audit_log
from plugins import journal_resolver as J

MAINTENANT = datetime.datetime(2026, 11, 25, 15, 0, 0)


@pytest.fixture
def journal(monkeypatch, tmp_path):
    chemin = tmp_path / "audit.log"
    monkeypatch.setattr(audit_log, "_LOG_PATH", str(chemin))
    lignes = [
        {"ts": "2026-11-24 09:00:00", "event": "commande", "texte": "mets de la musique", "resolveur": "resoudre_musique"},
        {"ts": "2026-11-24 09:05:00", "event": "commande", "texte": "mets une alarme", "resolveur": "alarmes"},
        {"ts": "2026-11-24 22:00:00", "event": "confirmation_resolue", "message": "Désinstaller X ?", "confirme": False},
        {"ts": "2026-11-25 08:00:00", "event": "commande", "texte": "ma journée", "resolveur": "resoudre_briefing"},
        {"ts": "2026-11-25 08:01:00", "event": "competence_creee", "nom": "x"},
    ]
    chemin.write_text("\n".join(json.dumps(e) for e in lignes) + "\nligne cassée\n", encoding="utf-8")
    return chemin


def test_periodes():
    assert J.periode("hier", MAINTENANT)[2] == "Hier"
    debut, fin, _ = J.periode("hier", MAINTENANT)
    assert (debut, fin) == (datetime.datetime(2026, 11, 24), datetime.datetime(2026, 11, 25))
    assert J.periode("aujourd'hui", MAINTENANT)[2] == "Aujourd'hui"
    assert J.periode("cette semaine", MAINTENANT)[0] == datetime.datetime(2026, 11, 19)


def test_evenements_entre_ignore_les_lignes_cassees(journal):
    debut, fin, _ = J.periode("hier", MAINTENANT)
    assert len(audit_log.evenements_entre(debut, fin)) == 3
    assert audit_log.evenements_entre(datetime.datetime(2025, 1, 1), datetime.datetime(2025, 1, 2)) == []


def test_resume_hier(journal, monkeypatch):
    monkeypatch.setattr(J.datetime, "datetime", type("D", (datetime.datetime,), {"now": staticmethod(lambda: MAINTENANT)}))
    rep = asyncio.run(J.resoudre_journal("Qu'est-ce que tu as fait hier ?"))
    assert rep.startswith("Hier : 2 commandes (") and "1 musique" in rep and "1 alarmes" in rep
    assert "1 confirmation, dont 1 refusée" in rep and "La dernière : « mets une alarme »" in rep


def test_resume_vide_et_phrase_etrangere(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "_LOG_PATH", str(tmp_path / "absent.log"))
    assert "rien consigné" in asyncio.run(J.resoudre_journal("qu'est-ce que tu as fait aujourd'hui"))
    assert asyncio.run(J.resoudre_journal("quelle heure est-il")) is None


def test_consigner_commande_ecrit_une_ligne(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_log, "_LOG_PATH", str(tmp_path / "audit.log"))
    from core import traitement
    traitement._consigner_commande("mets de la musique " + "x" * 200, "resoudre_musique")
    e = json.loads((tmp_path / "audit.log").read_text(encoding="utf-8"))
    assert e["event"] == "commande" and e["resolveur"] == "resoudre_musique" and len(e["texte"]) == 80
