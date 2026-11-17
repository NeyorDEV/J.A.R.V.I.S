"""Compteur de consommation de la reconnaissance vocale (limites de Groq)."""
import re

from core.usage_stt import CompteurQuota

T0 = 1_800_000_000.0   # heure de départ arbitraire (le compteur reçoit l'heure : aucun sleep dans les tests)


def test_compte_requetes_et_secondes_par_fenetre():
    c = CompteurQuota()
    for i in range(5):
        c.noter("groq", 2.0, True, maintenant=T0 + i)
    e = c.etat(T0 + 10)
    assert e["minute"] == 5 and e["heure_requetes"] == 5 and e["heure_secondes"] == 10 and e["jour_requetes"] == 5
    e = c.etat(T0 + 120)   # deux minutes plus tard : plus rien dans la fenêtre d'une minute, toujours dans l'heure
    assert e["minute"] == 0 and e["heure_requetes"] == 5


def test_alerte_a_80_pour_cent_une_fois_par_heure():
    c = CompteurQuota(limites={"rpm": 10, "rpj": 10_000, "sh": 100_000, "sj": 1_000_000})
    alertes = []
    for i in range(10):
        alertes += c.noter("groq", 1.0, True, maintenant=T0 + i)
    assert len(alertes) == 1 and "requêtes par minute" in alertes[0]   # une seule alerte malgré 3 appels au-dessus du seuil (8, 9, 10)
    assert c.noter("groq", 1.0, True, maintenant=T0 + 20) == []
    nouvelles = []
    for i in range(10):
        nouvelles += c.noter("groq", 1.0, True, maintenant=T0 + 4000 + i)   # plus d'une heure après : une nouvelle alerte est permise
    assert len(nouvelles) == 1


def test_refus_429_et_repli_google_comptes_a_part():
    c = CompteurQuota()
    c.noter("groq", 3.0, False, code=429, maintenant=T0)
    c.noter("groq", 3.0, False, code=500, maintenant=T0 + 1)
    c.noter("google", 3.0, True, maintenant=T0 + 2)
    e = c.etat(T0 + 3)
    assert e["refus_jour"] == 1 and e["erreurs_jour"] == 1 and e["repli_google_jour"] == 1 and e["jour_requetes"] == 2


def test_pic_de_requetes_par_minute():
    c = CompteurQuota()
    for i in range(7):
        c.noter("groq", 1.0, True, maintenant=T0 + i * 5)      # 7 requêtes en 30 s
    c.noter("groq", 1.0, True, maintenant=T0 + 1000)
    assert c.etat(T0 + 1001)["pic_requetes_minute_24h"] == 7


def test_evenements_de_plus_de_24h_sont_oublies_mais_pas_les_totaux_du_jour():
    c = CompteurQuota()
    c.noter("groq", 5.0, True, maintenant=T0)
    e = c.etat(T0 + 90_000)
    assert e["dernieres_24h_requetes"] == 0


def test_persistance(tmp_path):
    f = str(tmp_path / "usage.json")
    c = CompteurQuota(f)
    c.noter("groq", 4.0, True, maintenant=T0)
    c.enregistrer()
    c2 = CompteurQuota(f)
    assert c2.etat(T0 + 1)["heure_requetes"] == 1 and c2.etat(T0 + 1)["jour_secondes"] == 4


def test_resume_parle_contient_les_chiffres_utiles():
    c = CompteurQuota()
    for i in range(3):
        c.noter("groq", 10.0, True, maintenant=T0 + i)
    c.noter("groq", 10.0, False, code=429, maintenant=T0 + 5)
    c.noter("google", 10.0, True, maintenant=T0 + 6)
    texte = c.resume_parle(T0 + 10)
    assert "4 requêtes" in texte and "40 secondes" in texte and "1 refus" in texte and "1 reconnaissances faites par Google" in texte
    assert re.search(r"\d+ %", texte)


def test_limites_personnalisees_pour_une_offre_payante():
    c = CompteurQuota(limites={"rpm": 100})
    assert c.limites["rpm"] == 100 and c.limites["rpj"] == 2000   # seules les clés données sont remplacées
