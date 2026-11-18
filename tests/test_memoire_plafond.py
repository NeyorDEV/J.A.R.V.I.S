"""composer_contexte_memoire (module/memory_manager.py) : le prompt n'embarque que les derniers faits."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from module import memory_manager as M
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


def test_garde_les_derniers_faits(monkeypatch):
    faits = {f"cle{i}": {"valeur": f"v{i}", "timestamp": "t"} for i in range(100)}
    monkeypatch.setattr(M, "relire_memoire", lambda: faits)
    texte = M.composer_contexte_memoire()
    assert texte.count("\n") == M.MAX_FAITS_PROMPT and "cle99" in texte and "cle59 " not in texte and "cle60 " in texte


def test_memoire_courte_inchangee(monkeypatch):
    monkeypatch.setattr(M, "relire_memoire", lambda: {"a": {"valeur": "1", "timestamp": "t"}})
    assert M.composer_contexte_memoire().count("\n") == 1
