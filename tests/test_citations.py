"""Citations de la recherche approfondie."""
from core import citations as c


def test_numeros_valides_seulement():
    assert c.numeros_utilises("A [1] et B [3, 2] mais C [9] et [0]", 3) == [1, 2, 3]
    assert c.numeros_utilises("rien", 3) == []


def test_voix_sans_marques():
    assert c.pour_la_voix("Il pleut [1]. Il fait froid [1, 2].") == "Il pleut. Il fait froid."


def test_sources_numerotees_et_liste():
    ctx, urls = c.sources_numerotees([{"url": "https://a.fr/x", "content": "t1"}, {"url": "https://b.com", "content": "t2"}], lambda t, u: f"<{t}>")
    assert "[1] Source : https://a.fr/x" in ctx and "[2] Source : https://b.com" in ctx and "<t2>" in ctx
    assert c.liste_sources(urls, [2]) == "[2] b.com"
    assert c.liste_sources(urls, []).count("\n") == 1
