"""Import de skills GitHub : jamais approuvé, jamais écrasé, fichiers bornés."""
import pytest

try:
    from module import skills_import as si
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)

RAW = "https://raw.githubusercontent.com/o/r/main/s/"


def _api(fichiers):
    """Faux GitHub : fichiers = {'SKILL.md': '…', 'scripts/a.py': '…'}."""
    def get_json(url):
        base = url.split("/contents/", 1)[1].split("?")[0]            # s  ou  s/scripts
        rel = base[2:] if len(base) > 1 else ""
        sorties, vus = [], set()
        for chemin, texte in fichiers.items():
            if rel and not chemin.startswith(rel + "/"):
                continue
            reste = chemin[len(rel) + 1:] if rel else chemin
            nom = reste.split("/")[0]
            if nom in vus:
                continue
            vus.add(nom)
            if "/" in reste:
                sorties.append({"name": nom, "type": "dir"})
            else:
                sorties.append({"name": nom, "type": "file", "size": len(texte), "download_url": RAW + chemin})
        return sorties
    return get_json, lambda u: fichiers[u[len(RAW):]]


SKILL = "---\nname: Mon Skill\ndescription: test\n---\n# x\n"


def test_decouper_url():
    assert si.decouper_url("https://github.com/o/r/tree/main/skills/x") == ("o", "r", "main", "skills/x")
    for mauvais in ("http://github.com/o/r/tree/main/x", "https://evil.com/o/r/tree/main/x", "https://github.com/o/r", "https://github.com/o/r/tree/main/../x"):
        with pytest.raises(ValueError):
            si.decouper_url(mauvais)


def test_import_ecrit_sans_approuver_et_ajoute_script(tmp_path):
    gj, gt = _api({"SKILL.md": SKILL, "scripts/a.py": "print(1)"})
    nom, fichiers, _, a_script = si.importer("https://github.com/o/r/tree/main/s", str(tmp_path), gj, gt)
    assert nom == "mon-skill" and a_script and "scripts/a.py" in fichiers
    assert "script: scripts/a.py" in (tmp_path / "mon-skill" / "SKILL.md").read_text(encoding="utf-8")
    assert not (tmp_path / "_approbations.json").exists()
    assert '"niveau": "importe"' in (tmp_path / "_origine.json").read_text(encoding="utf-8")


def test_n_ecrase_pas(tmp_path):
    (tmp_path / "mon-skill").mkdir()
    gj, gt = _api({"SKILL.md": SKILL})
    with pytest.raises(ValueError, match="existe déjà"):
        si.importer("https://github.com/o/r/tree/main/s", str(tmp_path), gj, gt)


def test_sans_skill_md_et_fichiers_dangereux_ignores(tmp_path):
    gj, gt = _api({"x.py": "1"})
    with pytest.raises(ValueError, match="SKILL.md"):
        si.importer("https://github.com/o/r/tree/main/s", str(tmp_path), gj, gt)
    gj, gt = _api({"SKILL.md": SKILL, "run.exe": "MZ", "scripts/a.py": "1", "scripts/b.py": "2"})
    nom, fichiers, ignores, a_script = si.importer("https://github.com/o/r/tree/main/s", str(tmp_path), gj, gt)
    assert "run.exe" in ignores and not a_script and "run.exe" not in fichiers   # deux scripts : pas de choix à la place de l'utilisateur


def test_nom_nettoye_ou_refuse():
    assert si.nom_sur("../../x ") == "x"   # pas de séparateur de chemin possible dans le nom
    with pytest.raises(ValueError):
        si.nom_sur("")
