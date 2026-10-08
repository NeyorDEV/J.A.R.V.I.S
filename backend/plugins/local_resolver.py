import ast
import builtins
import math
import operator
import core.config as config
import core.shared as shared
import re
from core.interlocuteur import nom_espace, nom_virgule

_OPERATEURS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
               ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
               ast.Pow: operator.pow}


def _evaluer(noeud):
    """Évalue une expression arithmétique (nombres, + - * / // % ** et parenthèses)."""
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        v = _evaluer(noeud.operand)
        return -v if isinstance(noeud.op, ast.USub) else v
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATEURS:
        gauche, droite = _evaluer(noeud.left), _evaluer(noeud.right)
        # Bornes : « 9**9**9**9 » tapé au clavier figeait JARVIS (eval sans limite)
        if isinstance(noeud.op, ast.Pow) and (abs(droite) > 1000 or abs(gauche) > 1e6):
            raise ValueError("puissance trop grande")
        return _OPERATEURS[type(noeud.op)](gauche, droite)
    raise ValueError("expression non arithmétique")


def _formater(valeur):
    if isinstance(valeur, float):
        if valeur.is_integer() and abs(valeur) < 1e15:
            valeur = int(valeur)
        else:
            return f"{round(valeur, 6):g}".replace(".", ",")
    return f"{valeur:,}".replace(",", " ")


def _calcul(t):
    """Résultat d'un calcul demandé dans la phrase, ou None.

    Le calcul n'a lieu que sur une vraie demande (« combien font », « calcule »…) ou si
    la phrase n'est qu'une opération : avant, tout tiret entre deux chiffres était une
    soustraction (« le PSG a gagné 3-0 » → « 3 », « thermostat sur 19-20 » → « -1 »).
    """
    t = t.replace("?", " ").replace("=", " ").strip()
    demande = re.search(r"\b(combien (font|fait|ca fait|ça fait|egale?|égale?)|calcule[sz]?|resultat de|résultat de|racine)\b", t)
    m_racine = re.search(r"racine(?: carr[ée]e)? de (\d+(?:[.,]\d+)?)", t)
    if m_racine:
        n = float(m_racine.group(1).replace(",", "."))
        return f"La racine carrée de {_formater(n)} est {_formater(math.sqrt(n))}{nom_virgule()}."
    expr = t
    for motif, op in [(r"\bpuissance\b", "**"), (r"\bau carr[ée]\b", "**2"), (r"\bau cube\b", "**3"),
                      (r"\bmultipli[ée] par\b", "*"), (r"\bfois\b", "*"), (r"\bdivis[ée] par\b", "/"),
                      (r"\bplus\b", "+"), (r"\bmoins\b", "-"), (r"(?<=\d)\s*[x×]\s*(?=\d)", "*"),
                      (r"\b[x×]\b", "*"), (r"\^", "**")]:
        expr = re.sub(motif, f" {op} ", expr)
    if not demande:
        # Sans mot de calcul, la phrase entière doit être une opération (« 12 x 3 », « 3+4 »)
        if re.search(r"[^\d\s.,+\-*/()]", expr) or not re.search(r"\d\s*[+\-*/]", expr):
            return None
    garde = "".join(c for c in expr if c in "0123456789+-*/()., ").replace(",", ".")
    garde = re.sub(r"\s+", " ", garde).strip()
    if not re.search(r"\d", garde) or not re.search(r"[+\-*/]", garde.lstrip("-")):
        return None
    try:
        resultat = _evaluer(ast.parse(garde, mode="eval"))
    except ZeroDivisionError:
        return f"Division par zéro impossible{nom_virgule()}."
    except Exception:
        return None
    expression_dite = (garde.replace("**", " puissance ").replace("*", " fois ").replace("/", " divisé par ")
                       .replace("+", " plus ").replace(".", ","))
    expression_dite = re.sub(r"(?<=\d)\s*-\s*(?=\d)", " moins ", expression_dite)
    expression_dite = re.sub(r"\s+", " ", expression_dite).strip()
    return f"{expression_dite} font {_formater(resultat)}{nom_virgule()}."


async def resoudre_francais_localement(texte):
    """Gère les questions de base sur le français et les paramètres de JARVIS."""
    t = texte.lower().strip()

    # 1. CHANGEMENT DE VOIX / GENRE
    if any(kw in t for kw in ["voix d'homme", "voix masculine", "mode homme", "parle en homme"]):
        if config.VOIX_ACTUELLE == "homme": return f"Ma voix est déjà configurée sur le mode masculin{nom_virgule()}."
        config.VOIX_ACTUELLE = shared.VOIX_ACTUELLE = "homme"; return f"Très bien{nom_espace()}, je reprends ma voix habituelle."
    if any(kw in t for kw in ["voix de femme", "voix feminine", "mode femme", "parle en femme"]):
        if config.VOIX_ACTUELLE == "femme": return f"Ma voix est déjà configurée sur le mode féminin{nom_virgule()}."
        config.VOIX_ACTUELLE = shared.VOIX_ACTUELLE = "femme"; return f"C'est entendu{nom_espace()}, je passe sur une fréquence vocale féminine."

    # 2. CALCULS MATHÉMATIQUES
    return _calcul(t)

async def resoudre_conversion_localement(texte):
    """Gère les conversions d'unités localement."""
    t = texte.lower().replace("?", "").strip()
    # km <-> miles
    if any(m in t for m in [" km ", " kilometres ", " milles ", " miles "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilometres)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            return f"{val} kilomètres font environ {round(val * 0.621, 2)} miles{nom_virgule()}."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:miles|milles)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            return f"{val} miles font environ {round(val / 0.621, 2)} kilomètres{nom_virgule()}."
    # Celsius <-> Fahrenheit
    if any(m in t for m in [" degres ", " celsius ", " fahrenheit "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:degres|celsius)', t)
        if match and "fahrenheit" in t:
            val = float(match.group(1).replace(",", "."))
            return f"{val} degrés Celsius font {round((val * 9/5) + 32, 1)} degrés Fahrenheit."
    return None

async def resoudre_traduction_localement(texte):
    """Traduction ultra-rapide de mots courants."""
    t = texte.lower().strip()
    dict_trad = {
        "bonjour": {"en": "hello", "es": "hola"}, "merci": {"en": "thank you", "es": "gracias"},
        "maison": {"en": "house", "es": "casa"}, "ordinateur": {"en": "computer", "es": "ordenador"}
    }
    if any(p in t for p in ["comment dit-on", "traduis", "en anglais", "en espagnol"]):
        cible = "es" if "espagnol" in t else "en"
        mot = t
        for p in ["comment dit-on", "traduis", "en anglais", "en espagnol", "?"]: mot = mot.replace(p, "")
        mot = mot.strip()
        if mot in dict_trad:
            res = dict_trad[mot][cible]
            lang = "anglais" if cible == "en" else "espagnol"
            return f"En {lang}, '{mot}' se dit '{res}'."
    return None

# Injection builtins
builtins.resoudre_francais_localement = resoudre_francais_localement
builtins.resoudre_conversion_localement = resoudre_conversion_localement
builtins.resoudre_traduction_localement = resoudre_traduction_localement
