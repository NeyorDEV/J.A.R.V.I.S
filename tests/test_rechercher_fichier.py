"""rechercher_fichier (module/file_manager.py) : trouve, et s'arrête à la limite de temps au lieu de parcourir un disque entier."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from module import file_manager as fm
except (ModuleNotFoundError, AttributeError) as e:   # AttributeError : ctypes.windll absent hors Windows (CI Linux)
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    (tmp_path / "Windows Games").mkdir()
    (tmp_path / "Windows Games" / "partie.sav").write_text("x")
    monkeypatch.setattr(fm, "dossier_courant", str(tmp_path))
    return tmp_path


def test_trouve_un_fichier(dossier):
    resultats, err = fm.rechercher_fichier("partie.sav", scan_global=False)
    assert err is None and resultats and resultats[0].endswith("partie.sav")


def test_limite_de_temps_sans_resultat(dossier):
    resultats, err = fm.rechercher_fichier("absent.xyz", scan_global=False, delai=-1)   # délai déjà dépassé
    assert resultats == [] and "secondes" in err


def test_les_dossiers_nommes_windows_ne_sont_ignores_que_par_leur_nom():
    assert "windows" in fm._DOSSIERS_IGNORES and "windows games" not in fm._DOSSIERS_IGNORES
