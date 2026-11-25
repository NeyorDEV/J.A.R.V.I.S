"""Suivi des colis et factures (module/suivi_mails.py, plugins/suivi_resolver.py) : classement par règles, fusion, alertes, résolveur. Faux service Gmail, fichiers temporaires."""
import asyncio
from datetime import date, datetime

import pytest

from module import suivi_mails as S

MAINT = datetime(2026, 11, 25, 10, 0)


def cl(sujet, de="Chronopost <noreply@chronopost.fr>", extrait="", recu=MAINT):
    return S.classer(sujet, de, extrait, recu)


def test_colis_en_route_avec_date_et_suivi():
    r = cl("Votre colis sera livré demain", extrait="Numéro de suivi XW123456789FR")
    assert r["type"] == "colis" and r["statut"] == "en_route" and r["transporteur"] == "Chronopost"
    assert r["date"] == "2026-11-26" and r["suivi"] == "XW123456789FR"


def test_colis_livre_relais_et_date_en_lettres():
    assert cl("Votre colis a été livré")["statut"] == "livre"
    assert cl("Votre colis est disponible en point relais", de="Mondial Relay <a@mondialrelay.fr>")["statut"] == "relais"
    assert cl("Livraison prévue le 28 novembre", extrait="votre colis")["date"] == "2026-11-28"


@pytest.mark.parametrize("sujet,de", [
    ("Livraison offerte dès 25 euros", "Fnac <promo@fnac.com>"),
    ("Soldes : -50 % sur tout", "Cdiscount <a@cdiscount.com>"),
    ("Réunion demain à 10h", "Clara <clara@mail.fr>"),
    ("Facture offerte pour tout achat, code PROMO", "Boutique <a@b.fr>"),
])
def test_promotions_et_autres_ignorees(sujet, de):
    assert S.classer(sujet, de, "", MAINT) is None


def test_facture_avec_montant_et_echeance():
    r = cl("Votre facture EDF", de='"EDF" <noreply@edf.fr>', extrait="Montant à payer 82,50 € avant le 30 novembre")
    assert r["type"] == "facture" and r["statut"] == "a_payer" and r["emetteur"] == "EDF" and r["montant"] == "82,50" and r["date"] == "2026-11-30"
    assert cl("Prélèvement effectué", de="EDF <a@edf.fr>", extrait="facture payée")["statut"] == "payee"


def test_emetteur():
    assert S.emetteur('"Orange" <a@orange.fr>') == "Orange" and S.emetteur("noreply@free.fr") == "Free"


def _item(i, **kw):
    base = dict(id=i, type="colis", statut="en_route", emetteur="Chronopost", transporteur="Chronopost", suivi="", date="", objet="", recu="2026-11-20T10:00")
    return dict(base, **kw)


def test_fusion_cloture_colis_livre_facture_payee_et_oubli():
    d = {"items": [_item("a", suivi="XW1"), _item("b", transporteur="UPS", emetteur="UPS"),
                   _item("f", type="facture", statut="a_payer", emetteur="EDF", montant="82", recu="2026-11-20T10:00"),
                   _item("vieux", recu="2026-09-01T10:00")], "maj": ""}
    nouveaux = [_item("c", statut="livre", suivi="XW1", recu="2026-11-24T10:00"), _item("p", type="facture", statut="payee", emetteur="EDF", recu="2026-11-24T10:00")]
    assert S.fusionner(d, nouveaux, MAINT) == 2 and S.fusionner(d, nouveaux, MAINT) == 0
    statuts = {i["id"]: i["statut"] for i in d["items"]}
    assert statuts["a"] == "livre" and statuts["b"] == "en_route" and statuts["f"] == "payee" and "vieux" not in statuts


def test_alertes_une_par_jour_et_seulement_pertinentes():
    d = {"items": [_item("a", date="2026-11-25"), _item("b", date="2026-11-30"), _item("c", statut="relais"),
                   _item("f", type="facture", statut="a_payer", emetteur="EDF", montant="82", date="2026-11-27"),
                   _item("g", type="facture", statut="a_payer", emetteur="Free", date="2026-12-20")], "maj": ""}
    p = S.alertes(d, MAINT)
    assert len(p) == 3 and any("Chronopost" in x and "aujourd'hui" in x for x in p) and any("relais" in x for x in p) and any("EDF" in x and "dans 2 jours" in x for x in p)
    assert S.alertes(d, MAINT) == []   # déjà annoncées aujourd'hui


class _Req:
    def __init__(self, v): self.v = v
    def execute(self): return self.v


class FauxGmail:
    def __init__(self, mails): self.mails = mails
    def users(self): return self
    def messages(self): return self
    def list(self, **kw): return _Req({"messages": [{"id": m["id"]} for m in self.mails]})
    def get(self, id, **kw): return _Req(next(m for m in self.mails if m["id"] == id))


def _mail(i, sujet, de, snippet):
    return {"id": i, "snippet": snippet, "internalDate": str(int(MAINT.timestamp() * 1000)),
            "payload": {"headers": [{"name": "Subject", "value": sujet}, {"name": "From", "value": de}]}}


@pytest.fixture
def stock(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "FICHIER", str(tmp_path / "suivi.json"))


def test_rafraichir_avec_faux_gmail(stock):
    gmail = FauxGmail([_mail("1", "Votre colis arrive aujourd'hui", "Colissimo <a@colissimo.fr>", ""), _mail("2", "Newsletter", "Pub <a@pub.fr>", "soldes"),
                       _mail("3", "Facture Orange", "Orange <a@orange.fr>", "à régler avant le 1 décembre 39,99 €")])
    assert S.rafraichir(gmail, MAINT) == 2
    assert S.rafraichir(gmail, MAINT) == 0
    d = S.charger()
    assert [i["type"] for i in S.actifs(d, "colis")] == ["colis"] and S.actifs(d, "facture")[0]["montant"] == "39,99"
    assert "colis Colissimo, en route, prévu aujourd'hui" in S.decrire(S.actifs(d, "colis")[0], date(2026, 11, 25))


def test_resolver_liste_marque_et_active(stock, monkeypatch):
    from plugins import suivi_resolver as R
    S.sauver({"items": [_item("a", date="2026-11-25")], "maj": datetime.now().isoformat()})   # suivi récent : Gmail non relu
    monkeypatch.setattr(R, "_service", lambda: None)
    rep = asyncio.run(R.resoudre_suivi("où en sont mes colis"))
    assert rep.startswith("1 colis à suivre : 1. colis Chronopost")
    assert "C'est noté" in asyncio.run(R.resoudre_suivi("le colis 1 est arrivé"))
    assert "Aucun colis" in asyncio.run(R.resoudre_suivi("mes colis"))
    assert "numéro 5" in asyncio.run(R.resoudre_suivi("j'ai payé la facture 5"))
    assert "Suivi activé" in asyncio.run(R.resoudre_suivi("active le suivi des colis et factures")) and R._config() is True
    assert "Suivi désactivé" in asyncio.run(R.resoudre_suivi("désactive le suivi des colis")) and R._config() is False
    assert asyncio.run(R.resoudre_suivi("quelle heure est-il")) is None


def test_resolver_sans_acces_google(stock, monkeypatch):
    from plugins import suivi_resolver as R
    monkeypatch.setattr(R, "_service", lambda: None)
    assert "pas accès à votre messagerie" in asyncio.run(R.resoudre_suivi("mes factures à payer"))


def test_vrais_cas_micromania_et_facture_de_commande():
    assert cl("Votre colis a bien été récupéré", de="Micromania <a@micromania.fr>")["statut"] == "livre"
    assert cl("Votre colis est disponible en magasin", de="Micromania <a@micromania.fr>")["statut"] == "relais"
    assert cl("Votre colis Micromania est en route vers notre magasin", de="Micromania <a@micromania.fr>")["statut"] == "en_route"
    assert cl("Facture de la commande: 272846452", de="Micromania - Zing <a@micromania.fr>")["statut"] == "payee"


def test_colis_recupere_cloture_les_precedents_et_pluriel_invariable(stock, monkeypatch):
    from plugins import suivi_resolver as R
    d = {"items": [_item("a", emetteur="Micromania", transporteur="", recu="2026-11-20T14:24"), _item("b", emetteur="Micromania", transporteur="", statut="relais", recu="2026-11-21T13:28")], "maj": ""}
    S.fusionner(d, [_item("z", emetteur="Micromania", transporteur="", statut="livre", recu="2026-11-21T15:34")], MAINT)
    assert {i["id"]: i["statut"] for i in d["items"]} == {"a": "livre", "b": "livre", "z": "livre"}
    S.sauver({"items": [_item("x", date="2026-11-25"), _item("y", date="2026-11-26")], "maj": datetime.now().isoformat()})
    monkeypatch.setattr(R, "_service", lambda: None)
    assert asyncio.run(R.resoudre_suivi("mes colis")).startswith("2 colis à suivre")
