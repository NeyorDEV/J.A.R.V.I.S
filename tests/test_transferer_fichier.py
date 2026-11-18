"""transferer_fichier (module/file_manager.py) : jamais d'écrasement, jamais hors du dossier ouvert."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from module import file_manager as fm
except (ModuleNotFoundError, AttributeError) as e:   # AttributeError : ctypes.windll absent hors Windows (CI Linux)
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


def test_deplace_dans_un_sous_dossier(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    ok, _ = fm.transferer_fichier("a.txt", "Archive", str(tmp_path))
    assert ok and (tmp_path / "Archive" / "a.txt").read_text() == "A" and not (tmp_path / "a.txt").exists()


def test_n_ecrase_pas(tmp_path):
    (tmp_path / "Archive").mkdir()
    (tmp_path / "a.txt").write_text("NOUVEAU")
    (tmp_path / "Archive" / "a.txt").write_text("ANCIEN")
    ok, _ = fm.transferer_fichier("a.txt", "Archive", str(tmp_path))
    assert not ok and (tmp_path / "Archive" / "a.txt").read_text() == "ANCIEN" and (tmp_path / "a.txt").exists()


@pytest.mark.parametrize("destination", ["ABSOLU", "../dehors"])
def test_ne_sort_pas_du_dossier(tmp_path, destination):
    ouvert = tmp_path / "ouvert"
    ouvert.mkdir()
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (ouvert / "b.txt").write_text("B")
    ok, _ = fm.transferer_fichier("b.txt", str(dehors) if destination == "ABSOLU" else destination, str(ouvert))
    assert not ok and (ouvert / "b.txt").exists() and not (dehors / "b.txt").exists()


def test_autre_lecteur_refuse_sans_planter(tmp_path):
    (tmp_path / "c.txt").write_text("C")
    ok, _ = fm.transferer_fichier("c.txt", r"Z:\autre", str(tmp_path))   # lecteur différent : commonpath lèverait ValueError
    assert not ok and (tmp_path / "c.txt").exists()


def test_ouvrir_refuse_un_programme(tmp_path):
    exe = tmp_path / "install.bat"
    exe.write_text("echo x")
    ok, msg = fm.ouvrir_fichier_ou_dossier(str(exe))
    assert not ok and "programmes" in msg


def test_lire_refuse_les_secrets(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=secret")
    contenu, msg = fm.lire_fichier(str(env))
    assert contenu is None and "secrets" in msg


def test_renommer_reste_dans_le_dossier(tmp_path):
    (tmp_path / "a.txt").write_text("A")
    ok, _ = fm.changer_nom_fichier("a.txt", "../sorti.txt", str(tmp_path))
    assert not ok and (tmp_path / "a.txt").exists() and not (tmp_path.parent / "sorti.txt").exists()
    (tmp_path / "b.txt").write_text("B")
    ok, _ = fm.changer_nom_fichier("a.txt", "b.txt", str(tmp_path))   # n'écrase pas
    assert not ok and (tmp_path / "b.txt").read_text() == "B"
    ok, _ = fm.changer_nom_fichier("a.txt", "c.txt", str(tmp_path))
    assert ok and (tmp_path / "c.txt").exists()
