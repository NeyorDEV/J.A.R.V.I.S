"""Extrait les textes français affichés par le HUD (index.html + src/**/*.ts|js) : texte, title, placeholder, aria-label, chaînes de code.

Usage : venv\\Scripts\\python.exe tools\\i18n_extraire.py [sortie.json]   (défaut : scratch/i18n_textes.json)
Les nombres deviennent {0}, {1}… (même normalisation que src/i18n/i18n.ts) ; chaque texte n'apparaît qu'une fois.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONT = os.path.join(RACINE, "interfaces", "frontend")
ACCENT = re.compile(r"[àâçéèêëîïôùûüœÀÂÇÉÈÊËÎÏÔÙÛÜŒ]")
MOTS = frozenset("le la les un une des du de au aux et ou je vous votre vos ce cette est sont pour avec dans sur pas plus très mon ma mes aucun aucune afficher ouvrir fermer lancer activer désactiver "
                 "musique météo agenda mail courrier réglages paramètres annuler valider enregistrer fermer quitter charger recherche rechercher "
                 "en sur par aucune aucun active actif inactif analyse lecture cours tout tous toute toutes oui non erreur disponible indisponible attente protection".split())
NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")


def normaliser(texte: str) -> str:
    i = iter(range(1000))
    return NOMBRE.sub(lambda m: "{%d}" % next(i), re.sub(r"\s+", " ", texte).strip())


def candidat(texte: str, html: bool = False) -> bool:
    t = texte.strip()
    if not t or len(t) > 400 or not re.search(r"[A-Za-zÀ-ÿ]{2}", t):
        return False
    if re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9\s.,{}+-]+", t):   # tracé SVG (« M 0 0 h 4 v 2 »)
        return False
    if "|" in t or "_" in t or t.lower() in ("active", "attente", "recherche"):   # expressions régulières, identifiants, mots ambigus avec l'anglais
        return False
    if re.match(r"^(https?:|\./|\.\./|/|#|data:|[\w-]+\.(png|jpg|svg|js|ts|css|json))", t) or "://" in t or re.search(r"\$\{", t):
        return False
    if not html and re.search(r"[{}<>;=]", t.replace("{0}", "").replace("{1}", "")):   # du code, pas du texte (le HTML, lui, peut contenir « = »)
        return False
    if html or ACCENT.search(t):
        return True
    if re.match(r"^[A-ZÀ-Ý]", t) and len(t) >= 3 and "_" not in t and not (" " not in t and re.search(r"[a-z][A-Z]", t)) and not re.search(r"\.[a-z]{2,4}$", t) and not re.fullmatch(r"[A-Z0-9 ]{1,3}", t):
        return True   # libellé (majuscule initiale) : « Aide », « Mode local », « MUSIQUE »
    if " " in t and re.search(r"\d", t) and re.search(r"[a-zà-ÿ]{3,}", t) and not re.search(r"\d(px|em|rem|vh|vw|ms|deg)", t) and not re.search(r"[#:]\s*[0-9a-f]{3,}", t):
        return True   # phrase avec un nombre (« 6 rendez-vous ») : le nombre devient {0}, le reste se traduit
    mots = re.findall(r"[a-zà-ÿ']+", t.lower())
    return sum(1 for m in mots if m in MOTS) >= 2 or (len(mots) == 1 and len(t) >= 4 and t.lower() in MOTS)


class _Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.textes = []
        self._ignorer = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._ignorer += 1
        for nom, val in attrs:
            if nom in ("title", "placeholder", "aria-label", "alt") and val:
                self.textes.append(val)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._ignorer:
            self._ignorer -= 1

    def handle_data(self, data):
        if not self._ignorer:
            self.textes.append(data)


def chaines(code: str):
    """Toutes les chaînes de caractères du code TypeScript / JavaScript, y compris celles écrites DANS les ${ ... } des gabarits (`...${cond ? "a" : "b"}...`).
    Un gabarit est rendu avec ses ${ ... } remplacés par « 0 » (les nombres deviennent {n} ensuite). Commentaires ignorés ; les littéraux d'expressions régulières ne sont pas analysés."""
    sortie = []

    def lire(i: int, fin_gabarit: bool):
        """Lit du code à partir de i ; s'arrête sur « } » fermant un ${ si fin_gabarit. Renvoie la position suivante."""
        profondeur = 0
        while i < len(code):
            c = code[i]
            if code.startswith("//", i):
                i = code.find("\n", i)
                i = len(code) if i < 0 else i
            elif code.startswith("/*", i):
                i = code.find("*/", i)
                i = len(code) if i < 0 else i + 2
            elif c in "'\"":
                j = i + 1
                while j < len(code) and code[j] != c and code[j] != "\n":
                    j += 2 if code[j] == "\\" else 1
                sortie.append(code[i + 1:j])
                i = j + 1
            elif c == "`":
                i = gabarit(i + 1)
            elif c == "{":
                profondeur += 1
                i += 1
            elif c == "}":
                if fin_gabarit and profondeur == 0:
                    return i + 1
                profondeur -= 1
                i += 1
            else:
                i += 1
        return i

    def gabarit(i: int) -> int:
        morceaux = []
        while i < len(code) and code[i] != "`":
            if code[i] == "\\":
                morceaux.append(code[i:i + 2])
                i += 2
            elif code.startswith("${", i):
                morceaux.append("\uE000")   # remplacé par « 0 » plus loin ; reconnaissable pour retirer les expressions en bord de texte
                i = lire(i + 2, True)
            else:
                morceaux.append(code[i])
                i += 1
        sortie.append("".join(morceaux))
        return i + 1

    lire(0, False)
    return sortie


def extraire() -> list:
    vus = {}
    html = _Html()
    html.feed(open(os.path.join(FRONT, "index.html"), encoding="utf-8").read())
    sources = list(html.textes)
    nb_html = len(sources)
    fragments = []
    for dossier, _, fichiers in os.walk(os.path.join(FRONT, "src")):
        for f in fichiers:
            if f.endswith((".ts", ".js")) and not f.endswith(".d.ts"):
                code = open(os.path.join(dossier, f), encoding="utf-8").read()
                for s in chaines(code):
                    s = s.replace("\\'", "'").replace('\\"', '"').replace("\\n", " ")
                    if "<" not in s:
                        s = s.replace("\uE000", "0")
                    if "<" in s and ">" in s:   # fragment HTML dans une chaîne du code : on en extrait le texte et les attributs comme pour index.html
                        h = _Html()
                        try:
                            h.feed(s)
                        except Exception:
                            continue
                        for texte in h.textes:
                            fragments.append(texte.replace("\uE000", "0"))
                            nu = re.sub(r"^[\s\uE000]+|[\s\uE000]+$", "", texte)   # « <icône> Écouter » : le texte réel est « Écouter »
                            if nu != texte.strip() and "\uE000" not in nu:
                                fragments.append(nu)
                        continue
                    sources.append(s)
    sources[nb_html:nb_html] = []
    html_total = sources[:nb_html] + fragments
    for s in html_total:   # le HTML (de index.html et des fragments du code) est du texte affiché : tout est retenu (hors code évident)
        if candidat(s, html=True):
            vus.setdefault(normaliser(s), 0)
    for s in sources[nb_html:]:
        if candidat(s):
            vus.setdefault(normaliser(s), 0)
    return sorted(vus)


if __name__ == "__main__":
    sortie = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "scratch", "i18n_textes.json")
    textes = extraire()
    json.dump(textes, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(textes), "textes ->", sortie)
