"""Transcription locale (core/stt_local.py) : repli silencieux, texte normalisé, rééchantillonnage. Modèle remplacé par un leurre (pas de GPU requis)."""
from types import SimpleNamespace

import pytest

try:   # la CI n'installe que pytest et requests : sans numpy, ce fichier est ignoré (il tourne dans le venv de JARVIS)
    import numpy as np
    from core import stt_local
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


class Leurre:
    def __init__(self):
        self.vu = None

    def transcribe(self, audio, **kw):
        self.vu = (audio, kw)
        return [SimpleNamespace(text=" Bonjour "), SimpleNamespace(text="Jarvis. ")], None


def pcm(n=16000):
    return (np.zeros(n, dtype=np.int16)).tobytes()


def test_pas_charge_rend_none(monkeypatch):
    monkeypatch.setattr(stt_local, "_modele", None)
    assert stt_local.transcrire(pcm()) is None   # jamais d'attente du chargement : Groq prend le relais


def test_hors_service_ou_desactive_rend_none(monkeypatch):
    monkeypatch.setattr(stt_local, "_modele", Leurre())
    monkeypatch.setattr(stt_local, "active", lambda: False)
    assert stt_local.transcrire(pcm()) is None
    monkeypatch.setattr(stt_local, "active", lambda: True)
    monkeypatch.setattr(stt_local, "_hors_service", True)
    assert stt_local.transcrire(pcm()) is None


def test_texte_minuscule_et_amorce(monkeypatch):
    m = Leurre()
    monkeypatch.setattr(stt_local, "_modele", m)
    monkeypatch.setattr(stt_local, "_hors_service", False)
    monkeypatch.setattr(stt_local, "active", lambda: True)
    assert stt_local.transcrire(pcm(), 16000, "stop") == "bonjour jarvis."
    assert m.vu[1]["initial_prompt"] == "stop" and m.vu[1]["language"] == "fr"


def test_reechantillonne_a_16k(monkeypatch):
    m = Leurre()
    monkeypatch.setattr(stt_local, "_modele", m)
    monkeypatch.setattr(stt_local, "_hors_service", False)
    monkeypatch.setattr(stt_local, "active", lambda: True)
    stt_local.transcrire(pcm(48000), 48000)
    assert len(m.vu[0]) == 16000


def test_erreur_du_modele_rend_none(monkeypatch):
    class Casse:
        def transcribe(self, *a, **k):
            raise RuntimeError("CUDA out of memory")
    monkeypatch.setattr(stt_local, "_modele", Casse())
    monkeypatch.setattr(stt_local, "_hors_service", False)
    monkeypatch.setattr(stt_local, "active", lambda: True)
    assert stt_local.transcrire(pcm()) is None


def test_silence_rend_chaine_vide_et_non_none(monkeypatch):
    class Muet:
        def transcribe(self, audio, **kw):
            return [], None
    monkeypatch.setattr(stt_local, "_modele", Muet())
    monkeypatch.setattr(stt_local, "_hors_service", False)
    monkeypatch.setattr(stt_local, "active", lambda: True)
    assert stt_local.transcrire(pcm()) == ""   # « entendu du silence » ≠ None (« indisponible ») : pas de repli vers Groq pour chaque faux déclenchement
