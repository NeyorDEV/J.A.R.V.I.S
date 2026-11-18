"""Mode local : « désactive le mode local » ne doit pas l'activer (« active le mode local » est contenu dans « desactive… »)."""
import asyncio
import builtins

import pytest

try:
    from plugins import local_mode_resolver as r
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


@pytest.fixture(autouse=True)
def neutre(monkeypatch):
    p = pytest.importorskip("core.llm_providers")   # google-genai absent de la CI minimale : test ignoré
    monkeypatch.setattr(p, "prechauffer_ollama", lambda: None)   # jamais de chargement réel du modèle dans un test
    monkeypatch.setattr(builtins, "FORCE_LOCAL_MODE", False, raising=False)


@pytest.mark.parametrize("phrase,attendu", [("active le mode local", True), ("passe en mode hors ligne", True), ("mode local", True),
                                            ("désactive le mode local", False), ("desactive le mode hors ligne", False), ("passe en mode hybride", False)])
def test_activation_et_desactivation(phrase, attendu):
    builtins.FORCE_LOCAL_MODE = not attendu
    assert asyncio.run(r.resoudre_local_mode(phrase))
    assert builtins.FORCE_LOCAL_MODE is attendu
