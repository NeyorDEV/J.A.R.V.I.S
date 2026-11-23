"""Fabrique backend/core/console_fr_en.json : les messages de la console (print(...) du backend) avec leur traduction anglaise.

Extrait par analyse du code (ast) le premier argument de chaque print(...) : texte ou f-string ; les parties variables deviennent {0}, {1}… ; l'étiquette « [STT] » du début est retirée
(la console la sépare du message). Traduit par Gemini les messages nouveaux, par lots, avec la même vérification des marqueurs que tools/i18n_traduire.py.
Usage : venv\\Scripts\\python.exe tools\\i18n_console.py   (à relancer quand on ajoute des messages ; ne retraduit pas l'existant)
"""
import ast
import json
import os
import re

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SORTIE = os.path.join(RACINE, "backend", "core", "console_fr_en.json")
MARQUEUR = re.compile(r"\{\d+\}")
TAG = re.compile(r"^\s*(?:[✔⚠❌⚡]️?\s*)*\[[^\]]{1,40}\]\s*")
CONSIGNE = ("You translate console log messages of JARVIS (a voice assistant) from French to concise, natural English. Input: a JSON array of French strings. Output: a JSON array of the same length, "
            "same order. Keep {0}, {1}... placeholders exactly and in a position that keeps the sentence natural; keep technical names, file names, numbers, units, emoji and punctuation; "
            "if a string is not French (already English, code, a name), return it unchanged. Output JSON only.")


def modeles() -> list:
    trouves = {}
    sources = [(RACINE, ["main.py"])] + [(d, fs) for d, _, fs in os.walk(os.path.join(RACINE, "backend"))]   # main.py est hors du dossier backend
    for dossier, fichiers in sources:
        if any(x in dossier for x in ("sandbox", "__pycache__", "voiceprints")):
            continue
        for f in fichiers:
            if not f.endswith(".py"):
                continue
            try:
                arbre = ast.parse(open(os.path.join(dossier, f), encoding="utf-8").read())
            except Exception:
                continue
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.Call) and getattr(noeud.func, "id", None) == "print" and noeud.args):
                    continue
                a = noeud.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    s = a.value
                elif isinstance(a, ast.JoinedStr):
                    n, morceaux = 0, []
                    for v in a.values:
                        if isinstance(v, ast.Constant):
                            morceaux.append(str(v.value))
                        else:
                            morceaux.append("{%d}" % n)
                            n += 1
                    s = "".join(morceaux)
                else:
                    continue
                s = re.sub(r"\s+", " ", TAG.sub("", s)).strip()
                if len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", s)) >= 2 and re.search(r"[A-Za-zÀ-ÿ]{3}", re.sub(r"\{\d+\}", "", s)):
                    trouves[s] = 1
    return sorted(trouves)


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RACINE, ".env"))
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        dico = json.load(open(SORTIE, encoding="utf-8"))
    except Exception:
        dico = {}
    tous = modeles()
    manquants = [t for t in tous if t not in dico]
    print(len(tous), "messages,", len(manquants), "à traduire")

    def traduire(lot):
        r = client.models.generate_content(model="gemini-3.8-flash", contents=json.dumps(lot, ensure_ascii=False),
                                           config=types.GenerateContentConfig(system_instruction=CONSIGNE, temperature=0.2, response_mime_type="application/json"))
        sortie = json.loads(r.text)
        if not isinstance(sortie, list) or len(sortie) != len(lot):
            raise ValueError(f"{len(sortie)} réponses pour {len(lot)} messages")
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
        json.dump(dico, open(SORTIE, "w", encoding="utf-8"), ensure_ascii=False, indent=0, sort_keys=True)
        print(i + len(lot), "/", len(manquants))


if __name__ == "__main__":
    main()
