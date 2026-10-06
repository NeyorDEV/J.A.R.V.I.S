import builtins
import core.config as config
import re
from core.interlocuteur import nom_espace, nom_virgule

async def resoudre_francais_localement(texte):
    """Gère les questions de base sur le français et les paramètres de JARVIS."""
    t = texte.lower().strip()
    
    # 1. CHANGEMENT DE VOIX / GENRE
    if any(kw in t for kw in ["voix d'homme", "voix masculine", "mode homme", "parle en homme"]):
        if config.VOIX_ACTUELLE == "homme": return "Ma voix est déjà configurée sur le mode masculin, Monsieur."
        config.VOIX_ACTUELLE = "homme"; return "Très bien Monsieur, je reprends ma voix habituelle."
    if any(kw in t for kw in ["voix de femme", "voix feminine", "mode femme", "parle en femme"]):
        if config.VOIX_ACTUELLE == "femme": return f"Ma voix est déjà configurée sur le mode féminin{nom_virgule()}."
        config.VOIX_ACTUELLE = "femme"; return f"C'est entendu{nom_espace()}, je passe sur une fréquence vocale féminine."

    # 2. CALCULS MATHÉMATIQUES
    t_math = re.sub(r'([a-zA-Z])\-([a-zA-Z])', r'\1 \2', t)
    
    # Vérifier la présence de mots déclencheurs ou d'un opérateur réel
    has_math_word = any(w in t_math for w in ["combien font", "calcule", "puissance", "racine"])
    # Détecter + - * / ou un "x" isolé (ex: 2 x 5 ou 2x5)
    has_operator = any(op in t_math for op in ["+", "-", "*", "/"]) or re.search(r'\b[x×]\b|\d\s*[x×]\s*\d', t_math)
    
    if has_math_word or has_operator:
        # Remplacer les "x" de multiplication isolés par "*"
        expr = re.sub(r'\b[x×]\b', '*', t_math)
        t_clean = "".join([c for c in expr if c in "0123456789+-*/()., "])
        t_clean = t_clean.replace(",", ".")
        t_stripped = t_clean.strip()
        
        # S'assurer qu'il y a au moins un chiffre et qu'il y a un vrai opérateur pour faire un calcul (exclure les nombres isolés comme "180")
        if len(t_stripped) > 1 and any(c.isdigit() for c in t_stripped) and any(op in t_stripped for op in ["+", "-", "*", "/"]):
            try:
                resultat = eval(t_stripped)
                return f"Le résultat de {t_stripped} est {resultat}, Monsieur."
            except: pass
    return None

async def resoudre_conversion_localement(texte):
    """Gère les conversions d'unités localement."""
    t = texte.lower().replace("?", "").strip()
    # km <-> miles
    if any(m in t for m in [" km ", " kilometres ", " milles ", " miles "]):
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:km|kilometres)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            return f"{val} kilomètres font environ {round(val * 0.621, 2)} miles, Monsieur."
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:miles|milles)', t)
        if match:
            val = float(match.group(1).replace(",", "."))
            return f"{val} miles font environ {round(val / 0.621, 2)} kilomètres, Monsieur."
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
