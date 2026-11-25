"""Habitudes (module/habitudes.py, plugins/habitudes_resolver.py) : détection sur un journal fabriqué, refus des commandes dangereuses, création de routine dans un fichier temporaire."""
import asyncio
import datetime
import json

import pytest

from core import audit_log
from module import habitudes as H
from module import routines


def ev(jour, heure, texte="lance spotify", resolveur="resoudre_musique", event="commande"):
    return {"ts": f"2026-11-{jour:02d} {heure}:00", "event": event, "texte": texte, "resolveur": resolveur}


def test_habitude_reguliere():
    evts = [ev(10, "22:05"), ev(11, "22:20"), ev(12, "21:55"), ev(13, "22:10"), ev(14, "09:00")]   # une exception le matin : 4 jours sur 5
    [h] = H.analyser(evts)
    assert h["commande"] == "lance spotify" and h["heure"] == "22:10" and h["vus"] == 4 and h["total"] == 5   # médiane de 22:05, 22:20, 21:55, 22:10 arrondie à 5 minutes
    assert h["jours"] == [0, 1, 2, 3, 4]   # 10 au 13 novembre 2026 = mardi au vendredi
    assert "vers 22 h 10" in H.decrire(h) and "4 jours sur 5" in H.decrire(h)


def test_pas_assez_de_jours_ou_heures_dispersees():
    assert H.analyser([ev(10, "22:00"), ev(11, "22:00")]) == []                                  # 2 jours seulement
    assert H.analyser([ev(10, "07:00"), ev(11, "13:00"), ev(12, "19:00"), ev(13, "23:00")]) == []   # pas d'heure habituelle


def test_une_seule_fois_par_jour():
    evts = [ev(10, "22:00")] * 5 + [ev(11, "22:00")] * 5   # 10 commandes mais 2 jours
    assert H.analyser(evts) == []


def test_jamais_les_commandes_dangereuses_horaires_ou_tronquees():
    dangereux = [ev(j, "22:00", "eteins le pc", "commandes_locales") for j in (10, 11, 12)]
    horaires = [ev(j, "22:00", "mets une alarme a sept heures", "alarmes") for j in (10, 11, 12)]
    macros = [ev(j, "22:00", "mode cinema", "resoudre_macros") for j in (10, 11, 12)]
    tronque = [ev(j, "22:00", "a" * 80, "resoudre_musique") for j in (10, 11, 12)]
    un_mot = [ev(j, "22:00", "musique", "resoudre_musique") for j in (10, 11, 12)]
    assert H.analyser(dangereux + horaires + macros + tronque + un_mot) == []


def test_deja_en_routine_et_autres_evenements():
    evts = [ev(j, "22:00") for j in (10, 11, 12)] + [ev(j, "22:00", event="confirmation_resolue") for j in (10, 11, 12)]
    assert len(H.analyser(evts)) == 1
    assert H.analyser(evts, deja={"lance spotify"}) == []


def test_week_end():
    evts = [ev(j, "10:00") for j in (7, 8, 14, 15)]   # samedi 7, dimanche 8, 14, 15 novembre 2026
    [h] = H.analyser(evts)
    assert h["jours"] == [5, 6]


@pytest.fixture
def journal(monkeypatch, tmp_path):
    monkeypatch.setattr(audit_log, "_LOG_PATH", str(tmp_path / "audit.log"))
    monkeypatch.setattr(routines, "FICHIER", str(tmp_path / "routines.json"))
    lignes = [ev(j, "22:00") for j in (20, 21, 22, 23)] + [ev(j, "08:00", "donne la meteo", "resoudre_musique") for j in (20, 21, 22)]
    (tmp_path / "audit.log").write_text("\n".join(json.dumps(e) for e in lignes), encoding="utf-8")


def test_resolver_liste_puis_cree_la_routine(journal, monkeypatch):
    from plugins import habitudes_resolver as R
    monkeypatch.setattr(H, "datetime", type("D", (datetime.datetime,), {"now": staticmethod(lambda: datetime.datetime(2026, 11, 25, 12, 0))}))
    R._derniere_liste = []
    rep = asyncio.run(R.resoudre_habitudes("quelles sont mes habitudes"))
    assert rep.startswith("J'ai remarqué 2 habitudes") and "lance spotify" in rep and "transforme l'habitude 1" in rep
    assert "Routine créée" in asyncio.run(R.resoudre_habitudes("transforme l'habitude 1 en routine"))
    [r] = routines.charger()["routines"]
    assert r["commande"] == "lance spotify" and r["heure"] == "22:00"
    assert "existe déjà" in asyncio.run(R.resoudre_habitudes("transforme l'habitude 1 en routine"))
    assert "pas d'habitude numéro 9" in asyncio.run(R.resoudre_habitudes("transforme l'habitude 9 en routine"))


def test_resolver_sans_recul_et_phrase_etrangere(tmp_path, monkeypatch):
    from plugins import habitudes_resolver as R
    monkeypatch.setattr(audit_log, "_LOG_PATH", str(tmp_path / "absent.log"))
    monkeypatch.setattr(routines, "FICHIER", str(tmp_path / "routines.json"))
    assert "pas encore assez de recul" in asyncio.run(R.resoudre_habitudes("qu'as-tu remarqué"))
    assert asyncio.run(R.resoudre_habitudes("quelle heure est-il")) is None
