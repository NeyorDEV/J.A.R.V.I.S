"""Auto-modification du code (plugins/developer_resolver.py) : périmètre limité au code, restauration à l'identique, un lot appliqué à moitié ne reste jamais."""
import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from plugins import developer_resolver as D
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


@pytest.fixture
def projet(tmp_path, monkeypatch):
    (tmp_path / "backend").mkdir()
    (tmp_path / "interfaces" / "frontend").mkdir(parents=True)
    monkeypatch.setattr(D, "ROOT_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("chemin", [".env", "start.bat", ".git/hooks/pre-commit", "config/token.pickle", "data/jarvis_memoire.json", "main.py",
                                    "backend/core/voiceprints/neyor/x.py", "interfaces/frontend/node_modules/x.js", "../dehors.py", "backend/.env"])
def test_hors_perimetre(projet, chemin):
    assert D._chemin_projet(chemin) is None


@pytest.mark.parametrize("chemin", ["backend/plugins/nouveau_resolver.py", "interfaces/frontend/src/main.ts", "interfaces/frontend/index.html"])
def test_dans_le_perimetre(projet, chemin):
    assert D._chemin_projet(chemin) is not None


def test_restauration_a_l_identique_y_compris_le_travail_non_commite(projet):
    f = projet / "backend" / "a.py"
    f.write_bytes(b"ligne1\r\nTRAVAIL_NON_COMMITE\r\nligne3\r\n")
    avant = f.read_bytes()
    D.appliquer_edits([{"file_path": "backend/a.py", "target_code": "ligne1", "replacement_code": "MODIF_IA"}])
    assert f.read_bytes() != avant
    D._annuler_modifications(["backend/a.py"])
    assert f.read_bytes() == avant   # octet pour octet : ni git, ni perte du travail non commité


def test_fichier_cree_est_supprime_au_retour_arriere(projet):
    D.appliquer_edits([{"file_path": "backend/plugins/neuf.py", "target_code": "", "replacement_code": "x = 1\n"}])
    assert (projet / "backend" / "plugins" / "neuf.py").exists()
    D._annuler_modifications(["backend/plugins/neuf.py"])
    assert not (projet / "backend" / "plugins" / "neuf.py").exists()


def test_lot_a_moitie_applique_est_restaure(projet):
    f = projet / "backend" / "b.py"
    f.write_text("alpha\n", encoding="utf-8")
    with pytest.raises(ValueError):
        D.appliquer_edits([
            {"file_path": "backend/b.py", "target_code": "alpha", "replacement_code": "beta"},
            {"file_path": ".env", "target_code": "", "replacement_code": "PIRATE=1"},   # hors périmètre : tout le lot s'annule
        ])
    assert f.read_text(encoding="utf-8") == "alpha\n" and not (projet / ".env").exists()
