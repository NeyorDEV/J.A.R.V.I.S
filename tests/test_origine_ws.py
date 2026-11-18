"""Filtre d'origine du WebSocket (core/ws_handler.py) : seul le HUD (localhost:5173), l'extension et les clients natifs passent."""
from types import SimpleNamespace

import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré (il tourne dans le venv de JARVIS)
    from core.ws_handler import _origine_autorisee
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


def ws(origine):
    return SimpleNamespace(request=SimpleNamespace(headers={"Origin": origine} if origine else {}))


@pytest.mark.parametrize("origine", [None, "http://localhost:5173", "http://127.0.0.1:5173", "chrome-extension://abcdef"])
def test_acceptees(origine):
    assert _origine_autorisee(ws(origine))


@pytest.mark.parametrize("origine", ["null", "file://", "http://localhost:4173", "http://localhost", "https://evil.com", "http://localhost:5173.evil.com"])
def test_refusees(origine):
    assert not _origine_autorisee(ws(origine))
