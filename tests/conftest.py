"""Les tests importent le code du backend tel quel (sans lancer JARVIS) : core.*, module.*, plugins.*."""
import os
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "backend"))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _langue_francaise_isolee(monkeypatch, tmp_path):
    """La langue vient de jarvis_config.json (celle de l'utilisateur) : chaque test repart en français, avec une config temporaire que « definir() » peut écrire sans toucher à la vraie."""
    from core import i18n
    monkeypatch.setattr(i18n, "_langue", "fr")
    monkeypatch.setattr(i18n, "_CONFIG", str(tmp_path / "jarvis_config.json"))
    monkeypatch.setattr(i18n, "_console_memo", {})
