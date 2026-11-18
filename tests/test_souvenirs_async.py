"""souvenirs_async / precharger_souvenirs (module/vector_memory.py) : la recherche part en fil séparé, la préchargée n'est utilisée que pour la même phrase."""
import asyncio

import pytest

try:   # chromadb absent de la CI minimale : fichier ignoré
    from module import vector_memory as vm
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


@pytest.fixture
def appels(monkeypatch):
    liste = []
    monkeypatch.setattr(vm, "rechercher_souvenirs", lambda t: liste.append(t) or f"s:{t}")
    monkeypatch.setattr(vm, "_prechargee", None)
    return liste


def test_sans_prechargement(appels):
    assert asyncio.run(vm.souvenirs_async("a")) == "s:a" and appels == ["a"]


def test_prechargee_reutilisee_une_seule_fois(appels):
    async def scenario():
        vm.precharger_souvenirs("a")
        return await vm.souvenirs_async("a"), await vm.souvenirs_async("a")
    assert asyncio.run(scenario()) == ("s:a", "s:a") and appels == ["a", "a"]   # 1re : préchargée ; 2e : nouvelle recherche, jamais de résultat périmé


def test_autre_phrase_ignore_la_prechargee(appels):
    async def scenario():
        vm.precharger_souvenirs("a")
        return await vm.souvenirs_async("b")
    assert asyncio.run(scenario()) == "s:b"


def test_precharger_sans_boucle_ne_plante_pas(appels):
    vm.precharger_souvenirs("a")   # aucune boucle active
    assert vm._prechargee is None
