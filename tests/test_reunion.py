"""Réunions (module/reunion.py, plugins/reunion_resolver.py) : prise de notes, fermeture automatique, compte rendu. Doublures : aucun micro, aucun Gemini, dossier temporaire."""
import asyncio
import json
import time

import pytest

from module import reunion as M
from plugins import reunion_resolver as R


@pytest.fixture(autouse=True)
def _isole(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "DOSSIER", str(tmp_path / "reunions"))
    monkeypatch.setitem(M._etat, "actif", False)
    M._etat.update(notes=[], id=None, titre="")


def dire(phrase):
    return asyncio.run(R.resoudre_reunion(phrase))


def test_notes_filtrees_et_fichier_jsonl():
    rid = M.demarrer("point projet")
    assert rid.endswith("_point-projet") and M.en_cours()
    assert M.noter("on décide de livrer vendredi", "neyor")
    assert not M.noter("Jarvis arrête la réunion", "neyor")   # commande : pas notée
    assert not M.noter("ok", "clara")                          # fragment d'un mot
    assert M.demarrer() is None                                # déjà en cours
    lignes = (open(M._chemin(rid, ".jsonl"), encoding="utf-8").read().splitlines())
    assert len(lignes) == 2 and json.loads(lignes[1])["qui"] == "neyor"


def test_terminer_enregistre_et_ferme():
    M.demarrer("x")
    M.noter("bonjour tout le monde", "clara")
    r = M.terminer()
    assert r["notes"][0]["texte"] == "bonjour tout le monde" and not M.en_cours()
    assert M.derniere()["id"] == r["id"] and M.nombre_enregistrees() == 1
    assert M.terminer() is None


def test_fermeture_automatique_apres_inactivite(monkeypatch):
    M.demarrer("x")
    M.noter("une phrase de test", "")
    M._etat["dernier"] = time.time() - M.INACTIVITE_S - 5
    assert M.en_cours() is False and M.derniere()["auto"] is True


def test_lire_compte_rendu_robuste():
    ok = '```json\n{"resume": "Livraison vendredi.", "decisions": ["Livrer vendredi"], "actions": [{"qui": "Clara", "quoi": "envoyer le devis", "echeance": "jeudi"}, {"quoi": ""}]}\n```'
    cr = M.lire_compte_rendu(ok)
    assert cr["resume"] == "Livraison vendredi." and cr["actions"] == [{"qui": "Clara", "quoi": "envoyer le devis", "echeance": "jeudi"}]
    assert M.lire_compte_rendu("Voici : " + '{"resume": "a"}')["decisions"] == []
    assert M.lire_compte_rendu("pas du json") is None and M.lire_compte_rendu("") is None and M.lire_compte_rendu('{"x": 1}') is None


def test_transcription_tronquee_et_markdown():
    r = {"notes": [{"t": "10:00:00", "qui": "neyor", "texte": "a" * 100}] * 50}
    assert "[… passage omis …]" in M.transcription(r, 1000)
    md = M.markdown({"titre": "T", "debut": "2026-11-25T10:00:00", "duree_s": 600, "notes": r["notes"][:1],
                     "compte_rendu": {"resume": "R", "decisions": ["D"], "actions": [{"qui": "Clara", "quoi": "Q", "echeance": "jeudi"}]}})
    assert "# T" in md and "- D" in md and "- Clara : Q (jeudi)" in md


def test_commandes_demarrer_statut_arreter(monkeypatch):
    dits = []
    monkeypatch.setattr(R.builtins, "parler", lambda t, **k: dits.append(t), raising=False)

    async def faux_rediger(r):
        return {"resume": "On livre vendredi.", "decisions": [], "actions": [{"qui": "Clara", "quoi": "envoyer le devis", "echeance": ""}]}

    monkeypatch.setattr(M, "rediger", faux_rediger)
    assert dire("quelle heure est-il") is None
    assert "Aucune réunion n'est en cours" in dire("arrête la réunion")
    rep = dire("démarre la réunion avec Clara")
    assert "Prise de notes lancée" in rep and "prévenez les participants" in rep
    assert "déjà en cours" in dire("démarre la réunion")
    M.noter("on livre vendredi sans faute", "neyor")
    assert "1 phrases notées" in dire("où en est la réunion")
    rep = dire("arrête la réunion")
    assert "On livre vendredi." in rep and "Clara doit envoyer le devis" in rep and dits and "compte rendu" in dits[0]
    assert "On livre vendredi." in dire("résume la dernière réunion")
    assert "envoyer le devis" in dire("quelles sont les actions de la réunion")


def test_reunion_vide(monkeypatch):
    dire("démarre la réunion")
    assert "rien noté" in dire("arrête la réunion")


def test_qui_parle_sans_biometrie(monkeypatch):
    import core.shared as shared
    monkeypatch.setattr(shared, "VOICE_BIOMETRICS", None)
    assert M.qui_parle(b"", 16000) == ""

    class Bio:
        def identify_speaker(self, audio, rate, threshold=0.0):
            return "clara", 0.7
    monkeypatch.setattr(shared, "VOICE_BIOMETRICS", Bio())
    assert M.qui_parle(b"", 16000) == "clara" and M.qui_parle(b"", 16000, seuil=0.9) == "invité"
