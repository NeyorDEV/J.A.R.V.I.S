"""Assistant de premier lancement, étape « Hors ligne » : détection d'Ollama, du modèle de secours et du GPU NVIDIA (core/ws_assistant.verifier_local)."""
import io
import json
import subprocess

import pytest

try:   # ai_clients tire google-genai : absent de la CI minimale, fichier ignoré
    from core import ws_assistant as w
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


def _ollama(monkeypatch, noms=None):
    """noms=None : serveur injoignable ; sinon liste de modèles présents."""
    def faux(url, timeout=0):
        if noms is None:
            raise OSError("refusé")
        assert url.startswith("http://127.0.0.1")   # jamais autre chose que la machine locale
        return io.BytesIO(json.dumps({"models": [{"name": n} for n in noms]}).encode())
    monkeypatch.setattr("urllib.request.urlopen", faux)


def _gpu(monkeypatch, sortie=None):
    monkeypatch.setattr("shutil.which", lambda n: "smi" if (n == "nvidia-smi" and sortie is not None) else None)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=sortie or "", stderr=""))


def test_tout_present(monkeypatch):
    _ollama(monkeypatch, [w.shared.OLLAMA_MODELS[0]])
    _gpu(monkeypatch, "NVIDIA GeForce RTX 4070 SUPER, 12282\n")
    r = w.verifier_local()
    assert r["ollama_actif"] and r["modele_present"] and r["gpu"] == "NVIDIA GeForce RTX 4070 SUPER" and r["vram_go"] == 12


def test_modele_absent_les_modeles_perso_ne_comptent_pas(monkeypatch):
    _ollama(monkeypatch, ["huihui_ai/gemma-4-abliterated:12b"])
    _gpu(monkeypatch, None)
    r = w.verifier_local()
    assert r["ollama_actif"] and not r["modele_present"] and r["gpu"] is None


def test_ollama_absent_ou_arrete(monkeypatch):
    _ollama(monkeypatch, None)
    _gpu(monkeypatch, None)
    monkeypatch.setenv("LOCALAPPDATA", "")
    r = w.verifier_local()
    assert not r["ollama_actif"] and not r["ollama_installe"] and not r["modele_present"]


def test_sortie_gpu_illisible_ne_plante_pas(monkeypatch):
    _ollama(monkeypatch, None)
    _gpu(monkeypatch, "n'importe quoi")
    assert w.verifier_local()["gpu"] is None
