"""Traduit en anglais les textes extraits par tools/i18n_extraire.py -> interfaces/frontend/src/i18n/en.json (ajoute les textes manquants, ne retraduit pas l'existant).

Usage : venv\\Scripts\\python.exe tools\\i18n_traduire.py [textes.json]   (défaut : scratch/i18n_textes.json ; relancer l'extraction avant)
Utilise la clé Gemini du .env. Vérifie que chaque marqueur {n} du français est repris dans l'anglais, sinon la ligne est retentée seule.
"""
import json
import os
import re
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(RACINE, "backend"))
SORTIE = os.path.join(RACINE, "interfaces", "frontend", "src", "i18n", "en.json")
MARQUEUR = re.compile(r"\{\d+\}")
CONSIGNE = ("You translate the user interface texts of JARVIS (a futuristic Iron-Man style voice assistant HUD) from French to natural, concise English. "
            "Input: a JSON array of French strings. Output: a JSON array of the same length, same order, with the English translation of each. "
            "Rules: keep {0}, {1}... placeholders exactly; keep ALL-CAPS strings in ALL CAPS and the same punctuation/emoji; keep brand and product names, file names, "
            "commands in code style and keyboard keys unchanged; voice-command examples (imperative sentences the user would say to JARVIS) become natural English voice commands; "
            "if a string is not really French text (a code fragment, a CSS name), return it unchanged. Output JSON only.")


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RACINE, ".env"))
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    source = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "scratch", "i18n_textes.json")
    textes = json.load(open(source, encoding="utf-8"))
    try:
        dico = json.load(open(SORTIE, encoding="utf-8"))
    except Exception:
        dico = {}
    manquants = [t for t in textes if t not in dico]
    print(len(manquants), "textes à traduire")

    def traduire(lot):
        r = client.models.generate_content(model="gemini-3.8-flash", contents=json.dumps(lot, ensure_ascii=False),
                                           config=types.GenerateContentConfig(system_instruction=CONSIGNE, temperature=0.2, response_mime_type="application/json"))
        sortie = json.loads(r.text)
        if not isinstance(sortie, list) or len(sortie) != len(lot):
            raise ValueError(f"{len(sortie)} réponses pour {len(lot)} textes")
        return sortie

    for i in range(0, len(manquants), 60):
        lot = manquants[i:i + 60]
        try:
            sortie = traduire(lot)
        except Exception as e:
            print("lot en échec, ligne par ligne :", e)
            sortie = []
            for t in lot:
                try:
                    sortie.append(traduire([t])[0])
                except Exception:
                    sortie.append(t)
        for fr, en in zip(lot, sortie):
            if sorted(MARQUEUR.findall(fr)) != sorted(MARQUEUR.findall(en)):
                print("marqueurs perdus, ligne ignorée :", fr, "->", en)
                continue
            dico[fr] = en
        os.makedirs(os.path.dirname(SORTIE), exist_ok=True)
        json.dump(dico, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print(i + len(lot), "/", len(manquants))


if __name__ == "__main__":
    main()
