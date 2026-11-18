"""_ecrire_env (core/ai_clients.py) : seules les clés API du panneau s'écrivent, sur une seule ligne."""
import os

import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    import core.shared as shared
    from core import ai_clients
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "RACINE_PROJET", str(tmp_path))
    for k in ("GROQ_API_KEY", "PYTHONPATH", "PATH_TEST"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path / ".env"


def test_cle_autorisee_ecrite(env):
    ai_clients._ecrire_env({"GROQ_API_KEY": "gsk_abc"})
    assert env.read_text(encoding="utf-8") == "GROQ_API_KEY=gsk_abc\n" and os.environ["GROQ_API_KEY"] == "gsk_abc"


def test_nom_hors_liste_refuse(env):
    ai_clients._ecrire_env({"PYTHONPATH": r"C:\evil"})
    assert not env.exists() and "PYTHONPATH" not in os.environ


def test_valeur_a_plusieurs_lignes_refusee(env):
    ai_clients._ecrire_env({"GROQ_API_KEY": "a\nGEMINI_API_KEY=pirate"})
    assert not env.exists() and "GROQ_API_KEY" not in os.environ
