"""Dictionnaire français → anglais du HUD (interfaces/frontend/src/i18n/en.json) : cohérence des marqueurs et des clés."""
import json
import os
import re

CHEMIN = os.path.join(os.path.dirname(__file__), "..", "interfaces", "frontend", "src", "i18n", "en.json")
DICO = json.load(open(CHEMIN, encoding="utf-8"))
MARQUEUR = re.compile(r"\{\d+\}")


def test_dictionnaire_non_vide():
    assert len(DICO) > 1000


def test_marqueurs_identiques_et_valeurs_remplies():
    for fr, en in DICO.items():
        assert en.strip(), fr
        assert sorted(MARQUEUR.findall(fr)) == sorted(MARQUEUR.findall(en)), (fr, en)


def test_cles_normalisees():
    for fr in DICO:
        assert fr == re.sub(r"\s+", " ", fr).strip(), repr(fr)   # même normalisation que chercher() dans i18n.ts
