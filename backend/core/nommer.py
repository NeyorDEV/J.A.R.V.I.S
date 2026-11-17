"""Dire le prénom de l'interlocuteur dans la RÉPONSE quand la personne change ou au premier échange de la journée, à la place de l'ancienne annonce « Voix de X détectée ».

Pourquoi : l'annonce était une phrase à part, répétée à chaque changement de voix ; à trois dans une pièce, JARVIS ne faisait plus que la redire. Maintenant :
  - plus d'annonce (ni pour une voix connue, ni pour une voix inconnue) ;
  - quand la personne qui parle n'est pas la même que la fois d'avant (invités compris : A, invité, A = un changement), ou que c'est son premier échange de la journée, JARVIS ARME son prénom ;
  - la PREMIÈRE phrase que JARVIS prononce ensuite (speech.parler) le contient, sans exception : s'il y est déjà (« … Clara. »), rien n'est ajouté, sinon il est placé à la FIN, avant la ponctuation (« Il est 14 h, Clara. ») ;
  - le prénom armé expire au bout d'une minute (une réponse silencieuse ne doit pas faire nommer quelqu'un plus tard, hors contexte) ; une voix inconnue n'est jamais nommée.
Pur et testé : tests/test_nommer.py.
"""
import re
import time
import unicodedata
from datetime import date

EXPIRE_S = 60.0


def _norm(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower()) if unicodedata.category(c) != "Mn")


def doit_nommer(locuteur, precedent, nomme_le: dict, aujourdhui: str) -> bool:
    """Vrai si `locuteur` doit être nommé dans la prochaine réponse : personne connue, et (différente de la précédente voix OU pas encore nommée aujourd'hui)."""
    if not locuteur or locuteur == "guest":
        return False
    return precedent != locuteur or nomme_le.get(locuteur) != aujourdhui


def contient_le_nom(texte, nom) -> bool:
    n = _norm(nom).strip()
    return bool(n) and re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", _norm(texte)) is not None


_PONCTUATION_FINALE = re.compile(r"(\s*[.!?…]+)\s*$")


def inserer_nom(texte, nom):
    """Le prénom à la FIN de la phrase, avant sa ponctuation finale : « Il est 14 h. » -> « Il est 14 h, Clara. », « Que puis-je pour vous ? » -> « Que puis-je pour vous, Clara ? ».
    Inchangé si le prénom y est déjà. Une phrase qui annonce une suite (« Voici la liste : ») ne peut pas finir sur un prénom : il passe alors DEVANT (« Clara, voici la liste : »)."""
    if not str(texte or "").strip() or not nom or contient_le_nom(texte, nom):
        return texte
    t = str(texte).rstrip()
    if t.endswith((":", ";", ",")):
        t = t.lstrip()
        if len(t) > 1 and t[0].isalpha() and t[0].isupper() and not (t[1].isupper() or t[1].isdigit()):
            t = t[0].lower() + t[1:]   # « Voici » -> « voici » (pas les sigles : « IA », ni les nombres)
        return f"{nom}, {t}"
    m = _PONCTUATION_FINALE.search(t)
    if m:
        return f"{t[:m.start()]}, {nom}{m.group(1)}"
    return f"{t}, {nom}"


def armer(shared, locuteur, nom_fn=None, maintenant=None) -> bool:
    """À appeler quand une voix vient d'être identifiée. Renvoie True si un prénom est armé pour la prochaine phrase de JARVIS."""
    precedent = getattr(shared, "LOCUTEUR_PRECEDENT", None)
    shared.LOCUTEUR_PRECEDENT = locuteur
    nomme_le = getattr(shared, "NOMME_LE", None)
    if nomme_le is None:
        nomme_le = shared.NOMME_LE = {}
    if not doit_nommer(locuteur, precedent, nomme_le, date.today().isoformat()):
        return False
    if nom_fn is None:
        from core.interlocuteur import nom_interlocuteur as nom_fn
    nom = nom_fn()
    if not nom:
        return False
    shared.NOM_A_DIRE = (nom, locuteur, time.time() if maintenant is None else maintenant)
    return True


def appliquer(shared, texte, maintenant=None):
    """À appeler sur chaque phrase avant de la dire : y place le prénom armé (une seule fois), sinon la renvoie telle quelle."""
    armee = getattr(shared, "NOM_A_DIRE", None)
    if not armee:
        return texte
    nom, locuteur, t0 = armee
    shared.NOM_A_DIRE = None
    if (time.time() if maintenant is None else maintenant) - t0 > EXPIRE_S:
        return texte
    if getattr(shared, "NOMME_LE", None) is None:
        shared.NOMME_LE = {}
    shared.NOMME_LE[locuteur] = date.today().isoformat()
    return inserer_nom(texte, nom)
