"""Reconnaissance de musique : phrases reconnues, collecte et WAV de l'extrait, lecture des réponses d'AudD."""
import builtins
import io
import queue
import struct
import wave

import pytest

builtins.CONNECTED_CLIENTS = []
from core import musique_id as mid  # noqa: E402
from plugins import musique_resolver as r  # noqa: E402

DEMANDES = ["c'est quoi cette musique", "C'est quoi cette musique ?", "quelle est cette chanson", "quel est ce morceau", "qui chante ça", "reconnais cette musique", "identifie cette chanson",
            "shazam", "jarvis c'est quoi cette musique", "quelle musique est-ce", "c'est quoi cette musique dans la pièce", "qu'est-ce que c'est comme musique", "quelle est cette musique qui passe"]
PAS_DES_DEMANDES = ["mets de la musique", "joue une chanson de Daft Punk", "coupe la musique", "quelle heure est-il", "c'est quoi la météo", "monte le son", "trouve la musique de Daft Punk", "ouvre la vue de dieu"]


@pytest.mark.parametrize("phrase", DEMANDES)
def test_demande_reconnue(phrase):
    assert r.est_demande(phrase) is True


@pytest.mark.parametrize("phrase", PAS_DES_DEMANDES)
def test_autres_phrases_ignorees(phrase):
    assert r.est_demande(phrase) is False


def test_collecte_jusqu_a_la_duree_voulue_et_pas_plus():
    q = queue.Queue()
    for _ in range(40):
        q.put(b"\x01\x00" * 1000)   # 40 morceaux de 1 000 échantillons = 2,5 s à 16 kHz
    pcm = mid.collecter(q, secondes=2.0)
    assert len(pcm) == 2 * mid.OCTETS_PAR_SECONDE   # exactement 2 s, le reste est ignoré


def test_collecte_s_arrete_au_delai_si_le_flux_est_muet():
    q = queue.Queue()
    q.put(b"\x00\x00" * 100)
    pcm = mid.collecter(q, secondes=5.0, delai_max=0.6)
    assert len(pcm) == 200   # ce qui est arrivé seulement ; l'appelant juge que c'est insuffisant


def test_wav_valide():
    pcm = struct.pack("<4h", 1, -1, 2, -2)
    with wave.open(io.BytesIO(mid.en_wav(pcm))) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 16000, 4)


def test_niveau_sonore_distingue_silence_et_son():
    assert mid.niveau_sonore(b"\x00\x00" * 1000) == 0.0
    assert mid.niveau_sonore(struct.pack("<2h", 12000, -12000) * 500) == 1.0
    assert mid.niveau_sonore(b"") == 0.0


def test_reponse_reconnue():
    m = mid.lire_reponse({"status": "success", "result": {"artist": "Daft Punk", "title": "One More Time", "album": "Discovery", "release_date": "2001-03-13", "song_link": "https://lis.tn/x"}})
    assert m == {"titre": "One More Time", "artiste": "Daft Punk", "album": "Discovery", "annee": "2001", "lien": "https://lis.tn/x"}
    assert mid.phrase_resultat(m) == "C'est « One More Time » de Daft Punk, sur l'album Discovery (2001)."


def test_reponse_sans_resultat():
    assert mid.lire_reponse({"status": "success", "result": None}) is None
    assert mid.lire_reponse({"status": "success", "result": {"artist": "x"}}) is None   # pas de titre


@pytest.mark.parametrize("code", [900, 901])
def test_cle_refusee_ou_quota_epuise(code):
    with pytest.raises(mid.MusiqueErreur, match="clé AudD"):
        mid.lire_reponse({"status": "error", "error": {"error_code": code, "error_message": "x"}})


def test_autre_erreur_et_reponse_inattendue():
    with pytest.raises(mid.MusiqueErreur, match="erreur"):
        mid.lire_reponse({"status": "error", "error": {"error_code": 300, "error_message": "bad audio"}})
    with pytest.raises(mid.MusiqueErreur):
        mid.lire_reponse("pas du json")


def test_phrase_sans_artiste_ni_annee():
    assert mid.phrase_resultat({"titre": "Titre", "artiste": "", "album": "Titre", "annee": "", "lien": ""}) == "C'est « Titre »."


def test_sans_cle_reconnaitre_refuse_sans_reseau(monkeypatch):
    monkeypatch.delenv("AUDD_API_TOKEN", raising=False)
    with pytest.raises(mid.MusiqueErreur, match="clé"):
        mid.reconnaitre(b"x")


# --- Shazam et choix du fournisseur ---------------------------------------------------------------------------------------------------------------------------------------------------------
REPONSE_SHAZAM = {"matches": [{"id": "1"}], "track": {"title": "One More Time", "subtitle": "Daft Punk", "url": "https://www.shazam.com/track/1", "sections": [
    {"type": "SONG", "metadata": [{"title": "Album", "text": "Discovery"}, {"title": "Label", "text": "Virgin"}, {"title": "Sortie", "text": "2001"}]}, {"type": "VIDEO"}]}}


def test_shazam_reponse_reconnue():
    m = mid.lire_reponse_shazam(REPONSE_SHAZAM)
    assert m == {"titre": "One More Time", "artiste": "Daft Punk", "album": "Discovery", "annee": "2001", "lien": "https://www.shazam.com/track/1"}


def test_shazam_annee_en_anglais():
    d = {"track": {"title": "T", "subtitle": "A", "sections": [{"metadata": [{"title": "Released", "text": "2001"}]}]}}
    assert mid.lire_reponse_shazam(d)["annee"] == "2001"


def test_shazam_sans_resultat_ou_reponse_inattendue():
    assert mid.lire_reponse_shazam({"matches": [], "tagid": "x"}) is None
    assert mid.lire_reponse_shazam({"track": {"subtitle": "sans titre"}}) is None
    with pytest.raises(mid.MusiqueErreur):
        mid.lire_reponse_shazam("pas un dict")


def _faux(monkeypatch, shazam=None, audd=None, cle_audd=True):
    """Remplace les deux fournisseurs : une fonction qui renvoie un morceau / None, ou une exception, et trace les appels."""
    appels = []

    def f(nom, comportement):
        def appel(wav, *a, **k):
            appels.append(nom)
            if isinstance(comportement, Exception):
                raise comportement
            return comportement
        return appel
    monkeypatch.setattr(mid, "shazam_disponible", lambda: True)
    monkeypatch.setattr(mid, "cle", lambda: "jeton" if cle_audd else "")
    monkeypatch.setattr(mid, "reconnaitre_shazam", f("shazamio", shazam))
    monkeypatch.setattr(mid, "reconnaitre", f("audd", audd))
    return appels


MORCEAU = {"titre": "T", "artiste": "A", "album": "", "annee": "", "lien": ""}


def test_identifier_shazam_d_abord(monkeypatch):
    appels = _faux(monkeypatch, shazam=MORCEAU, audd=MORCEAU)
    assert mid.identifier(b"x", ["shazamio", "audd"]) == (MORCEAU, "shazamio") and appels == ["shazamio"]


def test_inconnu_est_definitif_et_ne_consomme_pas_le_quota_audd(monkeypatch):
    appels = _faux(monkeypatch, shazam=None, audd=MORCEAU)
    assert mid.identifier(b"x", ["shazamio", "audd"]) == (None, "shazamio") and appels == ["shazamio"]


def test_panne_de_shazam_passe_a_audd(monkeypatch):
    appels = _faux(monkeypatch, shazam=mid.MusiqueErreur("panne"), audd=MORCEAU)
    assert mid.identifier(b"x", ["shazamio", "audd"]) == (MORCEAU, "audd") and appels == ["shazamio", "audd"]


def test_toutes_les_pannes_remontent_la_derniere_erreur(monkeypatch):
    _faux(monkeypatch, shazam=mid.MusiqueErreur("panne shazam"), audd=mid.MusiqueErreur("panne audd"))
    with pytest.raises(mid.MusiqueErreur, match="panne audd"):
        mid.identifier(b"x", ["shazamio", "audd"])


def test_audd_sans_cle_est_ignore(monkeypatch):
    appels = _faux(monkeypatch, shazam=mid.MusiqueErreur("panne"), audd=MORCEAU, cle_audd=False)
    with pytest.raises(mid.MusiqueErreur):
        mid.identifier(b"x", ["shazamio", "audd"])
    assert appels == ["shazamio"] and mid.fournisseurs_disponibles(["shazamio", "audd"]) == ["shazamio"]


def test_ordre_audd_d_abord_et_aucun_fournisseur(monkeypatch):
    appels = _faux(monkeypatch, shazam=MORCEAU, audd=MORCEAU)
    assert mid.identifier(b"x", ["audd", "shazamio"]) == (MORCEAU, "audd") and appels == ["audd"]
    monkeypatch.setattr(mid, "shazam_disponible", lambda: False)
    monkeypatch.setattr(mid, "cle", lambda: "")
    with pytest.raises(mid.MusiqueErreur, match="Aucun service"):
        mid.identifier(b"x", ["shazamio", "audd"])
