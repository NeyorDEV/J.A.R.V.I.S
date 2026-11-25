"""Mémoire sémantique (module/vector_memory.py) : un simple accusé de réception (« Très bien... ») n'est jamais rejoué à la place d'une vraie réponse ou d'une action."""
import pytest

from module import vector_memory as VM


class _Coll:
    def __init__(self, reponse, dist=0.1):
        self.doc, self.dist = f"Date: 2026-11-25\nUser: x\nAssistant: {reponse}", dist

    def count(self):
        return 1

    def query(self, **kw):
        return {"documents": [[self.doc]], "distances": [[self.dist]]}


@pytest.mark.parametrize("reponse", ["Très bien...", "Très bien Neyor...", "Entendu…", "D'accord, j'y vais"])
def test_accuse_de_reception_non_rejoue(monkeypatch, reponse):
    monkeypatch.setattr(VM, "_get_collection", lambda: _Coll(reponse))
    assert VM.rechercher_souvenir_semantique("fais ce truc") is None


def test_vraie_reponse_courte_rejouee(monkeypatch):
    monkeypatch.setattr(VM, "_get_collection", lambda: _Coll("Paris."))
    assert VM.rechercher_souvenir_semantique("capitale de la france") == "Paris."


def test_mails_jamais_depuis_la_memoire(monkeypatch):
    monkeypatch.setattr(VM, "_get_collection", lambda: _Coll("Vous avez trois mails de Clara."))
    assert VM.rechercher_souvenir_semantique("lis moi mes mails non lus") is None


class _CollEcriture:
    def __init__(self, docs=(), dist=0.3):
        self.ajouts, self.docs, self.dist = [], list(docs), dist

    def count(self):
        return max(1, len(self.docs))

    def add(self, **kw):
        self.ajouts.append(kw)

    def query(self, **kw):
        return {"documents": [self.docs], "distances": [[self.dist] * len(self.docs)]}


def test_accuse_de_reception_non_memorise(monkeypatch):
    import core.shared as shared
    monkeypatch.setattr(shared, "ACTIVE_SPEAKER", "neyor", raising=False)
    coll = _CollEcriture()
    monkeypatch.setattr(VM, "_get_collection", lambda: coll)
    VM.ajouter_souvenir("lis moi mes courriers", "Très bien...")
    assert coll.ajouts == []
    VM.ajouter_souvenir("capitale de l'italie", "Rome.")
    assert len(coll.ajouts) == 1


def test_ancien_accuse_non_injecte_au_prompt(monkeypatch):
    docs = ["Date: x\nUser: lis moi mes mails\nAssistant: Très bien...", "Date: x\nUser: capitale\nAssistant: Rome est la capitale de l'Italie."]
    monkeypatch.setattr(VM, "_get_collection", lambda: _CollEcriture(docs))
    sortie = VM.rechercher_souvenirs("question")
    assert "Rome" in sortie and "Très bien" not in sortie


def test_historique_ni_archive_ni_recharge_pour_un_accuse(monkeypatch, tmp_path):
    import json

    from module import memory_manager as MM
    monkeypatch.setattr(MM, "HISTORIQUE_CONV_FILE", str(tmp_path / "conv.json"))
    MM._archiver_echange("lis moi mes mails", "Très bien...")
    MM._archiver_echange("lis moi mes mails", 'Très bien...\n{"action": "read_emails"}')   # avec son action : gardé
    MM._archiver_echange("capitale de l'italie", "Rome.")
    assert [e["model"] for e in json.load(open(MM.HISTORIQUE_CONV_FILE, encoding="utf-8"))] == ['Très bien...\n{"action": "read_emails"}', "Rome."]
    # un ancien fichier déjà pollué : les accusés ne sont pas rechargés dans le contexte de Gemini
    anciens = [{"date": "d", "heure": "h", "user": "u", "model": "Très bien..."}, {"date": "d", "heure": "h", "user": "u2", "model": "Rome."}]
    json.dump(anciens, open(MM.HISTORIQUE_CONV_FILE, "w", encoding="utf-8"))
    assert [c.parts[0].text for c in MM._relire_historique_recent() if c.role == "model"] == ["Rome."]
