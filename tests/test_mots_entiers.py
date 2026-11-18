"""Resolvers : mots entiers, pas sous-chaînes (« ar » dans « arrosage », « excel » dans « excellent »)."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from plugins import dom_controller_resolver as DOM
    from plugins import document_generator_resolver as DOC
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


@pytest.mark.parametrize("phrase,attendu", [("active le mode ar", True), ("ferme l ar", True), ("active l arrosage", False), ("ferme l arrosage", False)])
def test_commandes_ar(phrase, attendu):
    assert DOM._mots(phrase, ["active le mode ar", "active l ar", "ferme l ar"]) is attendu


def test_marqueurs_de_documents():
    assert DOC._mots("fais moi un tableau excel", ["excel"])
    assert not DOC._mots("fais moi un excellent resume", ["excel"])   # « excel » dans « excellent » générait un .xlsx
    assert not DOC._mots("cree un password", ["word"])                # « word » dans « password » générait un .docx
    assert DOC._mots("cree un document word", ["word"])
