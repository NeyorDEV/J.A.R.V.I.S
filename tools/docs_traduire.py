"""Traduit les documents de docs/fr/ en anglais -> docs/en/ (même nom de fichier).

Usage : venv\\Scripts\\python.exe tools\\docs_traduire.py [fichier ...]      (sans argument : tous les fichiers de docs/fr/)
Le français (docs/fr/) est la référence : après l'avoir modifié, relancer cet outil sur le fichier concerné.
Méthode : le fichier est traduit ligne à ligne (lots de ~40 lignes, réponse JSON de même longueur). Chaque ligne traduite est contrôlée : mêmes cibles de liens, mêmes extraits entre
accents graves, même puce ou même niveau de titre, même retrait. Une ligne qui échoue est retentée, puis traduite seule, puis (en dernier recours) laissée en français avec un avertissement.
"""
import json
import os
import re
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FR = os.path.join(RACINE, "docs", "fr")
EN = os.path.join(RACINE, "docs", "en")
MODELE = "gemini-3.8-flash"
CONSIGNE = (
    "You translate technical documentation of JARVIS (a French/English voice assistant project) from French to natural, concise English. "
    "Input: a JSON array of lines of a document. Output: a JSON array with EXACTLY the same number of lines, in the same order, each the translation of the matching input line. "
    "Rules: keep the structure of every line identical: same leading spaces, same bullet or numbering marker (-, *, 1.), same markdown heading marks (#), same table bars, same decoration characters (box-drawing, = and - rulers); "
    "an empty line stays empty; never merge or split lines. Keep unchanged: text inside backticks, link targets (the part in parentheses after a markdown link), file names and paths, URLs, "
    "code, identifiers, numbers, product and library names, placeholders in [square brackets] only when they are names of things (translate them when they are words, e.g. [Nom] -> [Name], [Ville] -> [City]). "
    "Voice commands (phrases the user says to JARVIS, usually before '->' or in quotes) become natural English voice commands, because JARVIS in English mode understands English. "
    "Translate markdown link texts but never their targets. Use the same register as the source. Output JSON only."
)
LIEN = re.compile(r"\]\(([^)]*)\)")
CODE = re.compile(r"`([^`]*)`")
# Phrases qui parlent de LA langue du document lui-même : une traduction littérale serait fausse, on impose le texte anglais (clé : début de la ligne française).
SURCHARGES = {
    "JARVIS_Commandes.txt": [
        ("Les commandes ci-dessous sont écrites en français.",
         "The commands below are given in English (translated from the French reference, docs/fr/JARVIS_Commandes.txt). JARVIS understands them in English mode: see the \"LANGUAGE\" section at the end of the document"),
        ("(« passe en anglais »", "(\"switch to English\" / \"passe en français\" to go back). Square brackets [ ] indicate a variable part of the phrase."),
    ],
}
DEBUT = re.compile(r"^(\s*)((?:[-*•]|\d+\.|#{1,6}|\|)?)")


def invariants(ligne: str):
    m = DEBUT.match(ligne)
    return (LIEN.findall(ligne), CODE.findall(ligne), len(m.group(1)), m.group(2), bool(ligne.strip()))


def valide(fr: str, en) -> bool:
    return isinstance(en, str) and invariants(fr) == invariants(en)


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RACINE, ".env"))
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    cibles = sys.argv[1:] or sorted(f for f in os.listdir(FR) if os.path.isfile(os.path.join(FR, f)) and f != "README.md")
    os.makedirs(EN, exist_ok=True)

    def appel(lignes, temperature=0.2):
        r = client.models.generate_content(model=MODELE, contents=json.dumps(lignes, ensure_ascii=False),
                                           config=types.GenerateContentConfig(system_instruction=CONSIGNE, temperature=temperature, response_mime_type="application/json"))
        sortie = json.loads(r.text)
        if not isinstance(sortie, list) or len(sortie) != len(lignes):
            raise ValueError(f"{len(sortie)} lignes pour {len(lignes)}")
        return sortie

    for nom in cibles:
        brut = open(os.path.join(FR, nom), "rb").read().decode("utf-8")
        eol = "\r\n" if "\r\n" in brut else "\n"
        lignes = brut.replace("\r\n", "\n").split("\n")
        sortie = [""] * len(lignes)
        a_faire = [i for i, l in enumerate(lignes) if l.strip()]
        for debut in range(0, len(a_faire), 40):
            idx = a_faire[debut:debut + 40]
            lot = [lignes[i] for i in idx]
            resultat = None
            for essai in range(3):
                try:
                    resultat = appel(lot, 0.2 if essai < 2 else 0.0)
                    break
                except Exception as e:
                    print("   lot retenté :", e)
            if resultat is None:
                resultat = list(lot)
            for i, fr, en in zip(idx, lot, resultat):
                if not valide(fr, en):
                    ok = None
                    for essai in range(2):
                        try:
                            cand = appel([fr], 0.0)[0]
                            if valide(fr, cand):
                                ok = cand
                                break
                        except Exception:
                            pass
                    if ok is None:
                        print(f"   AVERTISSEMENT {nom} ligne {i + 1} laissée en français : {fr[:70]}")
                        ok = fr
                    en = ok
                sortie[i] = en
            print(f"{nom} : {min(debut + 40, len(a_faire))}/{len(a_faire)} lignes", flush=True)
        for prefixe, texte in SURCHARGES.get(nom, []):
            for i, l in enumerate(lignes):
                if l.startswith(prefixe):
                    sortie[i] = texte
        with open(os.path.join(EN, nom), "wb") as f:
            f.write(eol.join(sortie).encode("utf-8"))
        print("->", os.path.join("docs", "en", nom), flush=True)


if __name__ == "__main__":
    main()
