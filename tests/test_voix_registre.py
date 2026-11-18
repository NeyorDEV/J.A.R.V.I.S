"""Registre de moteurs de voix : ordre, repli, pause après échec, réglage « tts_ordre »."""
import asyncio

import pytest

try:
    from core import voix_registre as vr
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


@pytest.fixture(autouse=True)
def _propre(monkeypatch):
    vr.vider()
    monkeypatch.setattr(vr, "_ordre_configure", lambda: [])
    yield
    vr.vider()


def _ok(nom):
    async def f(texte, base):
        return f"{base}.{nom}"
    return f


async def _casse(texte, base):
    raise RuntimeError("panne")


def test_premier_moteur_par_priorite():
    vr.enregistrer("b", 20, lambda: True, _ok("b"))
    vr.enregistrer("a", 10, lambda: True, _ok("a"))
    assert asyncio.run(vr.generer("x", "/t/p", 0)) == "/t/p.a"


def test_repli_et_pause_apres_echec():
    appels = []

    async def casse_compte(texte, base):
        appels.append(1)
        raise RuntimeError("x")
    vr.enregistrer("a", 10, lambda: True, casse_compte)
    vr.enregistrer("b", 20, lambda: True, _ok("b"))
    assert asyncio.run(vr.generer("x", "/t/p", 100.0)) == "/t/p.b"
    assert asyncio.run(vr.generer("x", "/t/p", 110.0)) == "/t/p.b"   # « a » est en pause : pas réessayé
    assert len(appels) == 1
    assert asyncio.run(vr.generer("x", "/t/p", 100.0 + vr.PAUSE_APRES_ECHEC + 1)) == "/t/p.b"
    assert len(appels) == 2


def test_indisponible_ecarte_et_tous_en_echec():
    vr.enregistrer("a", 10, lambda: False, _ok("a"))
    vr.enregistrer("b", 20, lambda: True, _casse)
    assert asyncio.run(vr.generer("x", "/t/p", 0)) is None


def test_reglage_ordre(monkeypatch):
    vr.enregistrer("a", 10, lambda: True, _ok("a"))
    vr.enregistrer("b", 20, lambda: True, _ok("b"))
    monkeypatch.setattr(vr, "_ordre_configure", lambda: ["b"])
    assert asyncio.run(vr.generer("x", "/t/p", 0)) == "/t/p.b"


def test_elevenlabs_desactive_par_defaut(monkeypatch):
    from core import voix_elevenlabs as el
    monkeypatch.setattr(el, "_config", lambda: {})
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    assert not el.disponible()
    monkeypatch.setattr(el, "_config", lambda: {"actif": True, "voice_id": "v"})
    assert el.disponible()
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert not el.disponible()
