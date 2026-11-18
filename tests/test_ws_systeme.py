"""Handlers WebSocket système (core/ws_systeme.py) : le HUD n'est pas une source sûre. Secrets illisibles, suppression limitée aux traces trouvées, commande de désinstallation relue côté serveur."""
import asyncio
import json
import os

import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from core import ws_systeme as W
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


class FauxWs:
    def __init__(self):
        self.messages = []

    async def send(self, texte):
        self.messages.append(json.loads(texte))


@pytest.mark.parametrize("chemin", [".env", ".env.local", "config/token.pickle", "data/jarvis_memoire.json", ".git/hooks/pre-commit", "start.bat", "jarvis_config.json",
                                    "backend/core/voiceprints/neyor/sample_1.wav", "../hors_projet.txt"])
def test_chemins_interdits(chemin):
    assert W._chemin_projet_valide(chemin) is None


@pytest.mark.parametrize("chemin", ["main.py", "backend/core/speech.py", "interfaces/frontend/src/main.ts", "README.md"])
def test_chemins_du_code_autorises(chemin):
    assert W._chemin_projet_valide(chemin) == os.path.abspath(os.path.join(W._RACINE_PROJET, chemin))


def test_clean_leftovers_refuse_un_chemin_absent_de_l_analyse(monkeypatch, tmp_path):
    cible = tmp_path / "Documents_importants"
    cible.mkdir()
    (cible / "a.txt").write_text("precieux")
    demandes = []

    async def faux_confirm(ws, message, **kw):
        demandes.append((message, kw.get("details")))
        return True
    monkeypatch.setattr(W, "demander_confirmation", faux_confirm)
    W._TRACES_TROUVEES.clear()
    ws = FauxWs()
    asyncio.run(W.ws_clean_leftovers(ws, {"items": [{"type": "folder", "path": str(cible)}]}))
    assert (cible / "a.txt").exists()          # jamais supprimé : le chemin ne vient pas de l'analyse
    assert not demandes                        # rien à confirmer : la liste est vide


def test_clean_leftovers_efface_une_trace_trouvee_et_montre_la_liste(monkeypatch, tmp_path):
    residu = tmp_path / "AppliDesinstallee"
    residu.mkdir()
    demandes = []

    async def faux_confirm(ws, message, **kw):
        demandes.append(kw.get("details"))
        return True
    monkeypatch.setattr(W, "demander_confirmation", faux_confirm)
    W._TRACES_TROUVEES.clear()
    W._memoriser_traces([{"type": "folder", "path": str(residu)}])
    asyncio.run(W.ws_clean_leftovers(FauxWs(), {"items": [{"type": "folder", "path": str(residu)}]}))
    assert not residu.exists()
    assert demandes and demandes[0][0]["d"] == str(residu)   # le chemin exact est montré dans la confirmation


def test_desinstallation_ignore_la_commande_du_message(monkeypatch):
    import module.uninstaller_helper as U
    lancees = []
    monkeypatch.setattr(U, "inventaire_logiciels", lambda: [{"name": "Discord", "publisher": "x", "install_location": "", "uninstall_string": "C:/vrai/uninstall.exe"}])
    monkeypatch.setattr(U, "executer_desinstallation", lambda cmd, nom="": (lancees.append(cmd), (False, "stop"))[1])
    monkeypatch.setattr(U, "chercher_traces_fichiers", lambda *a: [])

    async def oui(*a, **k):
        return True
    monkeypatch.setattr(W, "demander_confirmation", oui)
    asyncio.run(W.ws_uninstall_program(FauxWs(), {"name": "Discord", "uninstall_string": "calc.exe & del /s C:/"}))
    assert lancees == ["C:/vrai/uninstall.exe"]


def test_desinstallation_d_un_programme_inconnu_ne_lance_rien(monkeypatch):
    import module.uninstaller_helper as U
    lancees = []
    monkeypatch.setattr(U, "inventaire_logiciels", lambda: [])
    monkeypatch.setattr(U, "executer_desinstallation", lambda cmd, nom="": (lancees.append(cmd), (True, ""))[1])
    ws = FauxWs()
    asyncio.run(W.ws_uninstall_program(ws, {"name": "Fantome", "uninstall_string": "calc.exe"}))
    assert not lancees and ws.messages[-1]["success"] is False


# ── block_ip : jamais la box, le DNS ni la machine ───────────────────────────────────────────────────────────────────────────────────────
def test_ip_blocable():
    from core.ws_securite import ip_blocable
    assert ip_blocable("8.8.8.8") == (True, "")
    for refusee in ("192.168.1.1", "10.0.0.5", "172.16.0.1", "127.0.0.1", "169.254.1.1", "224.0.0.1", "0.0.0.0", "999.999.999.999", "abc", ""):
        assert ip_blocable(refusee)[0] is False, refusee


def test_block_ip_refuse_une_adresse_locale_sans_netsh(monkeypatch):
    import subprocess
    from core import ws_securite as S
    appels = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: appels.append(a))
    ws = FauxWs()
    asyncio.run(S.ws_block_ip(ws, {"ip": "192.168.1.1"}))
    assert appels == [] and ws.messages and ws.messages[0]["title"] == "Blocage refusé"


def test_block_ip_demande_confirmation(monkeypatch):
    import subprocess
    from core import ws_securite as S
    from core import confirmation as C
    appels = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: appels.append(a))

    async def non(*a, **k):
        return False
    monkeypatch.setattr(C, "demander_confirmation", non)
    asyncio.run(S.ws_block_ip(FauxWs(), {"ip": "8.8.8.8"}))
    assert appels == []   # refusé à la confirmation : aucune règle de pare-feu
