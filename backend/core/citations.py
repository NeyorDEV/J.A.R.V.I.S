"""Recherche approfondie avec sources numérotées : le modèle cite [1], [2]… ; la voix ne lit pas les numéros, le HUD affiche la liste des sources utilisées.

Pur (testé : tests/test_citations.py).
"""
import re
from urllib.parse import urlparse

_CITATION = re.compile(r"\s*\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]")


def sources_numerotees(donnees: list, entourer) -> tuple:
    """(contexte, urls) : `donnees` = [{'url','content'}] ; `entourer(texte, url)` isole le contenu externe."""
    urls = [d["url"] for d in donnees]
    contexte = "\n\n".join(f"[{i}] Source : {d['url']}\n{entourer(d['content'], d['url'])}" for i, d in enumerate(donnees, 1))
    return contexte, urls


def consigne_citation(n: int) -> str:
    return (f"Cite tes sources par leur numéro entre crochets, par exemple [1] ou [2], après chaque information (sources 1 à {n} seulement). "
            "N'invente aucune source ni aucun numéro.")


def numeros_utilises(texte: str, n: int) -> list:
    """Numéros réellement cités et valides (1..n), dans l'ordre croissant."""
    vus = set()
    for m in _CITATION.finditer(texte or ""):
        for x in m.group(1).split(","):
            if 1 <= int(x) <= n:
                vus.add(int(x))
    return sorted(vus)


def pour_la_voix(texte: str) -> str:
    """Texte sans les marques de citation, à lire à voix haute."""
    return _CITATION.sub("", texte or "").strip()


def liste_sources(urls: list, numeros: list) -> str:
    """Lignes « [1] domaine.tld » pour l'affichage ; si le modèle n'a rien cité, toutes les sources."""
    lignes = []
    for i in (numeros or range(1, len(urls) + 1)):
        u = urls[i - 1]
        lignes.append(f"[{i}] {urlparse(u).hostname or u}")
    return "\n".join(lignes)
