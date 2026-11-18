"""Routines vocales (module/routines.py) : compréhension de la phrase, refus des commandes dangereuses, déclenchement. Sans JARVIS lancé, sans effet sur le PC."""
from datetime import datetime

import pytest

from module import routines as R


def ok(phrase):
    statut, valeur = R.analyser(phrase)
    assert statut == "ok", (phrase, statut)
    return valeur


def test_tous_les_jours_a_8_heures():
    r = ok("Tous les jours à 8 heures, donne-moi la météo")
    assert r == {"commande": "donne-moi la meteo", "heure": "08:00", "jours": list(range(7))}


def test_commande_avant_la_recurrence_et_amorce_programme():
    assert ok("programme une routine : lance la musique tous les soirs à 20h30")["heure"] == "20:30"
    assert ok("dis-moi mes rendez-vous chaque matin à 7 h")["commande"] == "dis-moi mes rendez-vous"


@pytest.mark.parametrize("phrase,jours", [
    ("en semaine à 7h30 donne-moi la météo", [0, 1, 2, 3, 4]),
    ("le week-end à 10h joue de la musique", [5, 6]),
    ("tous les lundis à 9 heures montre mon agenda", [0]),
    ("chaque vendredi à midi annonce le menu", [4]),
])
def test_jours(phrase, jours):
    assert ok(phrase)["jours"] == jours


@pytest.mark.parametrize("phrase,heure", [("tous les jours à midi dis la météo", "12:00"), ("tous les jours à 8 heures et demie dis la météo", "08:30"),
                                          ("tous les jours à 9 heures du soir dis la météo", "21:00"), ("tous les jours à minuit dis la météo", "00:00")])
def test_heures(phrase, heure):
    assert ok(phrase)["heure"] == heure


def test_phrase_de_conversation_ou_sans_recurrence_n_est_pas_une_routine():
    assert R.analyser("je me lève tous les jours à 8 heures") is None
    assert R.analyser("donne-moi la météo") is None
    assert R.analyser("mets une alarme à 7 heures") is None


def test_heure_ou_commande_manquante_on_redemande():
    assert R.analyser("tous les jours donne-moi la météo")[0] == "heure"
    assert R.analyser("tous les jours à 8 heures routine")[0] == "commande"


@pytest.mark.parametrize("commande", ["éteins le pc", "redémarre l'ordinateur", "supprime mes fichiers", "envoie un mail à Paul", "désinstalle Discord", "mets l'ordinateur en veille", "vide la corbeille"])
def test_commandes_a_effet_refusees(commande):
    assert R.analyser(f"tous les jours à 8 heures, {commande}")[0] == "interdit"


def test_une_routine_part_une_fois_par_jour_dans_la_fenetre():
    r = {"commande": "x y", "heure": "08:00", "jours": [0]}                  # lundi
    lundi = datetime(2026, 11, 16, 8, 0, 30)
    assert R.a_lancer(r, lundi)
    assert R.a_lancer(r, datetime(2026, 11, 16, 8, 9))
    assert not R.a_lancer(r, datetime(2026, 11, 16, 7, 59))                   # trop tôt
    assert not R.a_lancer(r, datetime(2026, 11, 16, 8, 10))                   # trop tard (JARVIS démarré en retard)
    assert not R.a_lancer(r, datetime(2026, 11, 17, 8, 0, 30))                # mardi
    assert not R.a_lancer({**r, "derniere": "2026-11-16"}, lundi)             # déjà lancée aujourd'hui


def test_description_parlee():
    assert R.decrire({"commande": "donne-moi la meteo", "heure": "08:30", "jours": list(range(7))}) == "tous les jours à 8 heures 30 : donne-moi la meteo"
    assert R.decrire({"commande": "a b", "heure": "07:00", "jours": [0, 1, 2, 3, 4]}).startswith("en semaine à 7 heures")


def test_supprimer_utilise_le_numero_de_routine_pas_l_heure(tmp_path, monkeypatch):
    import asyncio
    monkeypatch.setattr(R, "FICHIER", str(tmp_path / "routines.json"))
    R.sauver({"actif": True, "routines": [{"commande": f"donne la meteo {i}", "heure": "07:00", "jours": list(range(7))} for i in range(9)]})
    asyncio.run(R.resoudre_routines("supprime la routine de 8 heures"))
    assert len(R.charger()["routines"]) == 9   # « 8 heures » n'est pas un numéro
    asyncio.run(R.resoudre_routines("supprime la routine 2"))
    assert len(R.charger()["routines"]) == 8


def test_creation_et_demon_ne_se_perdent_pas(tmp_path, monkeypatch):
    """Le démon écrit « derniere » pendant que des routines sont créées : aucune création ne doit disparaître."""
    import asyncio
    import threading
    monkeypatch.setattr(R, "FICHIER", str(tmp_path / "routines.json"))
    R.sauver({"actif": True, "routines": [{"commande": "donne la meteo", "heure": "00:00", "jours": list(range(7))}]})
    stop = threading.Event()

    def demon():
        while not stop.is_set():
            with R._VERROU:
                d = R.charger()
                d["routines"][0]["derniere"] = "2026-11-17"
                R.sauver(d)
    t = threading.Thread(target=demon, daemon=True)
    t.start()
    for i in range(1, 9):
        asyncio.run(R.resoudre_routines(f"tous les jours à {i} heures, donne-moi la météo {i}"))
    stop.set()
    t.join()
    assert len(R.charger()["routines"]) == 9
