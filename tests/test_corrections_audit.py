"""Corrections de l'audit du 17/11 : tri de dossiers, relais HUD, prompt invité, historique vide."""
import asyncio
import os

import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from core import actions_ia as A
    from core import prompt_builder as P
    from core import llm_providers as L
    from module import file_manager as fm
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


# ── tri de dossiers : jamais un dossier système ─────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("variable", ["SystemRoot", "ProgramFiles", "ProgramData", "USERPROFILE"])
def test_tri_refuse_les_dossiers_systeme(variable):
    dossier = os.environ.get(variable)
    if not dossier:
        pytest.skip(f"{variable} absent")
    assert fm._tri_interdit(dossier)
    assert fm.classer_par_type(dossier)[0] is False
    assert fm.classer_par_date(dossier)[0] is False


def test_tri_refuse_la_racine_d_un_disque():
    assert fm._tri_interdit(os.path.abspath(os.sep))


def test_tri_accepte_un_dossier_ordinaire(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)   # le dossier temporaire de pytest est sous AppData, interdit par construction
    monkeypatch.delenv("APPDATA", raising=False)
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "b.jpg").write_bytes(b"x")
    assert fm._tri_interdit(str(tmp_path)) is None
    assert fm.apercu_tri(str(tmp_path)) == (str(tmp_path), 2)
    ok, _ = fm.classer_par_type(str(tmp_path))
    assert ok and not (tmp_path / "a.txt").exists()


def test_chemin_ia():
    assert A._chemin_ia({"chemin": "downloads"}) == "downloads"
    for vide in ({}, {"chemin": None}, {"chemin": "null"}, {"chemin": "  "}, {"chemin": "None"}):
        assert A._chemin_ia(vide) is None


# ── relais HUD : jamais de clic ni de saisie venus de l'IA ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("data", [{"type": "dom_action", "action": "click", "selector": "#x"}, {"action": "click", "selector": "#x"},
                                  {"action": "type", "selector": "#x", "text": "a"}])
def test_relais_refuse_le_pilotage_du_hud(monkeypatch, data):
    envoyes = []
    monkeypatch.setattr(A, "_safe_ws_send", lambda b: envoyes.append(b))
    asyncio.run(A.executer_action(data.get("action", ""), data, "{}", "", ""))
    assert envoyes == []


def test_relais_laisse_passer_une_action_d_affichage(monkeypatch):
    envoyes = []
    monkeypatch.setattr(A, "_safe_ws_send", lambda b: envoyes.append(b))
    asyncio.run(A.executer_action("action_inconnue_du_hud", {"action": "action_inconnue_du_hud"}, "{}", "", ""))
    assert envoyes == ["{}"]


# ── prompt : un invité n'a ni la mémoire, ni les souvenirs, ni les infos privées ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("profil,present", [("guest", False), ("neyor", True)])
def test_prompt_invite_sans_donnees_privees(monkeypatch, profil, present):
    monkeypatch.setattr(P, "composer_contexte_memoire", lambda: "MEMOIRE_SECRETE")
    monkeypatch.setattr(P, "infos_createur", lambda: ["NE_LE_01_01_1990"])
    monkeypatch.setattr(P, "profil_actif", lambda: profil)
    prompt = P.composer_prompt_systeme(souvenirs="SOUVENIR_PRIVE")
    for marque in ("MEMOIRE_SECRETE", "SOUVENIR_PRIVE", "NE_LE_01_01_1990"):
        assert (marque in prompt) is present


# ── historique : jamais une réponse vide ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_reponse_vide_pas_dans_l_historique(monkeypatch):
    historique = []
    monkeypatch.setattr(L.shared, "historique", historique)
    monkeypatch.setattr(L, "_archiver_echange", lambda *a: None)
    monkeypatch.setattr(L, "ajouter_souvenir", lambda *a: None)
    L._memoriser_echange("bonjour", "   ")
    assert historique == []
    L._memoriser_echange("bonjour", "salut")
    assert len(historique) == 2


# ── lanceur : un joker dans les chemins connus est résolu (Discord : app-*\Discord.exe) ─────────────────────────────────────────────────────
def test_localiser_exe_resout_un_joker(tmp_path, monkeypatch):
    from controller import app_launcher as AL
    for v in ("1.0.9", "1.0.10"):
        (tmp_path / f"app-{v}").mkdir()
        (tmp_path / f"app-{v}" / "Discord.exe").write_text("x")
    monkeypatch.setenv("FAUX_LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(AL.shutil, "which", lambda n: None)
    trouve = AL._localiser_exe(["NomIntrouvable123.exe"], [r"%FAUX_LOCALAPPDATA%\app-*\Discord.exe"])
    assert trouve.endswith("Discord.exe") and "app-" in trouve
