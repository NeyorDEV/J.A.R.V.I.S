"""Fabrique backend/core/commandes_fr_en.json : les commandes vocales d'exemple de l'aide du HUD (hud/aide_commandes.ts) avec leur traduction anglaise (src/i18n/en.json).

Ce sont les phrases que comprennent vraiment les resolvers : core/i18n.py les donne en exemples à Gemini pour ramener une commande anglaise à la bonne phrase française.
Usage : venv\\Scripts\\python.exe tools\\i18n_exemples.py   (à relancer après tools/i18n_traduire.py)
"""
import json
import os
import re

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AIDE = os.path.join(RACINE, "interfaces", "frontend", "src", "hud", "aide_commandes.ts")
DICO = os.path.join(RACINE, "interfaces", "frontend", "src", "i18n", "en.json")
SORTIE = os.path.join(RACINE, "backend", "core", "commandes_fr_en.json")


def main():
    dico = json.load(open(DICO, encoding="utf-8"))
    code = open(AIDE, encoding="utf-8").read()
    paires = []
    for m in re.finditer(r'"([^"\n]{8,80})"', code):
        fr = re.sub(r"\s+", " ", m.group(1)).strip()
        en = dico.get(fr)
        if en and fr != fr.upper() and re.match(r"^[A-ZÀ-Ý]", fr) and [fr, en] not in paires:
            paires.append([fr, en])
    json.dump(paires, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(paires), "commandes ->", SORTIE)


if __name__ == "__main__":
    main()
