"""Compression de session : coupe entre paires, résumé injecté, échec du modèle sans perte."""
import asyncio
from types import SimpleNamespace

import pytest

try:
    from core import compression as c
except (ModuleNotFoundError, AttributeError) as e:
    pytest.skip(f"dépendance absente : {e}", allow_module_level=True)


def _hist(n):
    return [SimpleNamespace(role="user" if i % 2 == 0 else "model", parts=[SimpleNamespace(text=f"m{i}")]) for i in range(n)]


def test_sous_la_marge_rien_a_resumer():
    anciens, gardes = c.a_resumer(_hist(c.FENETRE + c.MARGE))
    assert anciens == [] and len(gardes) == c.FENETRE + c.MARGE


def test_coupe_entre_deux_paires():
    anciens, gardes = c.a_resumer(_hist(c.FENETRE + c.MARGE + 1))
    assert len(anciens) % 2 == 0 and gardes[0].role == "user" and len(anciens) + len(gardes) == c.FENETRE + c.MARGE + 1


def test_compresse_et_roge():
    vus = []

    async def llm(consigne):
        vus.append(consigne)
        return "Résumé neuf"
    resume, h = asyncio.run(c.compresser(_hist(80), "ancien", llm))
    assert resume == "Résumé neuf" and len(h) <= c.FENETRE + 1 and "ancien" in vus[0] and "m0" in vus[0]


def test_echec_du_modele_garde_tout():
    async def llm(consigne):
        raise RuntimeError("quota")
    h0 = _hist(80)
    resume, h = asyncio.run(c.compresser(h0, "ancien", llm))
    assert resume == "ancien" and h is h0


def test_resume_vide_ignore():
    async def llm(consigne):
        return "  "
    h0 = _hist(80)
    assert asyncio.run(c.compresser(h0, "a", llm)) == ("a", h0)
