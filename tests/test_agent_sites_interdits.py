"""Agent navigateur visuel (module/visual_web_agent.py) : il agit dans le vrai profil Opera GX ; jamais sur un site de banque ou de paiement."""
import asyncio

import pytest

try:   # la CI n'installe que pytest et requests : sans les dépendances de l'appli, ce fichier est ignoré
    from module.visual_web_agent import VisualWebAgent
except ModuleNotFoundError as e:
    pytest.skip(f"dépendance absente : {e.name}", allow_module_level=True)


def agent(url_page):
    a = object.__new__(VisualWebAgent)   # sans __init__ : pas de navigateur
    a.page = type("P", (), {"url": url_page})()
    appels = []

    async def brut(step):
        appels.append(step)
        return True
    a._execute_step_brut = brut
    return a, appels


@pytest.mark.parametrize("url", ["https://www.paypal.com/signin", "https://mabanque.bnpparibas/", "https://www.impots.gouv.fr/accueil", "https://checkout.shop.example/pay"])
def test_page_sensible_refusee(url):
    a, appels = agent(url)
    assert asyncio.run(a._execute_step({"action": "click"})) is False and not appels


def test_navigation_vers_un_site_sensible_refusee():
    a, appels = agent("https://www.google.com/")
    assert asyncio.run(a._execute_step({"action": "goto", "url": "https://paypal.com/"})) is False and not appels


def test_site_ordinaire_passe():
    a, appels = agent("https://www.amazon.fr/")
    assert asyncio.run(a._execute_step({"action": "click"})) is True and appels
