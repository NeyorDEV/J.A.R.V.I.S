"""Routines : une commande vocale qui se rejoue toute seule (« tous les jours à 8 heures, donne-moi la météo »).

Stockage data/routines.json ; un démon vérifie chaque minute et soumet la phrase au traitement normal de JARVIS, comme si elle était dite
(core/traitement.gerer_reponse_ia). Les commandes à effet sur le PC (arrêt, suppression, envoi de mail…) sont refusées : une routine tourne sans personne pour la confirmer.
La partie « comprendre la phrase » est pure (testée : tests/test_routines.py) ; seuls demarrer_daemon_routines / resoudre_routines touchent au reste de JARVIS.
"""
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta

FICHIER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "routines.json")
_VERROU = threading.RLock()
RATTRAPAGE_MIN = 10   # JARVIS démarré en retard : une routine manquée de moins de 10 minutes part quand même, sinon elle attend demain

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_TOUS = list(range(7))
_SEMAINE, _WEEKEND = [0, 1, 2, 3, 4], [5, 6]

# commandes qu'on refuse de programmer : effet sur le PC ou envoi vers l'extérieur
_INTERDIT = re.compile(r"\b(eteins?|eteindre|arrete(?:r)? (?:le )?(?:pc|ordinateur)|redemarre\w*|veille|hiberne\w*|verrouille\w*|supprime\w*|efface\w*|vide\w*|desinstalle\w*|"
                       r"corbeille|formate\w*|installe\w*|met(?:s)? a jour|mise a jour|envoie\w*|mail|e-mail|courriel|ferme\w*|kill|tue\w*|payer|achete\w*)\b")
_IMPERATIFS = ("dis", "donne", "lance", "ouvre", "joue", "mets", "met", "montre", "affiche", "fais", "annonce", "lis", "resume", "ecoute", "active", "demande", "surveille")
_RECURRENCE = re.compile(r"\b(?:tous les jours|chaque jour|tous les matins|chaque matin|tous les soirs|chaque soir|en semaine|les jours de semaine|tous les week ?-?ends?|le week ?-?end|"
                         r"(?:tous les|chaque|les) (?:lundis?|mardis?|mercredis?|jeudis?|vendredis?|samedis?|dimanches?))\b")
_HEURE = re.compile(r"\b(?:a|vers)?\s*(?:(\d{1,2})\s*(?:h|heures?|:)\s*(\d{2})?|(midi)|(minuit))(?:\s*et\s*(demie|quart))?(?:\s*du\s*(matin|soir))?\b")


def norm(texte: str) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t.replace("’", "'")).strip()


def jours_de(t: str):
    """Jours (0 = lundi) visés par la phrase normalisée ; None si aucune récurrence."""
    m = _RECURRENCE.search(t)
    if not m:
        return None
    s = m.group(0)
    for i, j in enumerate(JOURS):
        if j in s:
            return [i]
    if "week" in s:
        return list(_WEEKEND)
    if "semaine" in s:
        return list(_SEMAINE)
    return list(_TOUS)


def heure_de(t: str, jours_phrase: str = ""):
    """(heure, minute) dans la phrase normalisée, ou None. « chaque matin » sans heure : None (on demande)."""
    m = _HEURE.search(t)
    if not m:
        return None
    h, mn, midi, minuit, suite, moment = m.groups()
    if midi:
        h, mn = 12, 0
    elif minuit:
        h, mn = 0, 0
    else:
        h, mn = int(h), int(mn or 0)
        if suite == "demie":
            mn = 30
        elif suite == "quart":
            mn = 15
        if moment == "soir" and h < 12:
            h += 12
    if not (0 <= h < 24 and 0 <= mn < 60):
        return None
    return h, mn


def commande_de(t: str) -> str:
    """Retire de la phrase la récurrence, l'heure et les mots d'amorce : il reste la commande à rejouer."""
    t = _RECURRENCE.sub(" ", t)
    t = _HEURE.sub(" ", t, count=1)
    t = re.sub(r"\b(?:jarvis|s'il te plait|stp)\b", " ", t)
    t = re.sub(r"^\W*(?:(?:programme|planifie|automatise|ajoute|cree)\s+)?(?:(?:une|ma|la)\s+)?(?:nouvelle\s+)?(?:routine\s*(?:ou|:)?\s*)?", "", t.strip())
    return re.sub(r"\s+", " ", t).strip(" ,.;:!?-")


def interdite(commande: str) -> bool:
    return bool(_INTERDIT.search(norm(commande)))


_INTERVALLE = re.compile(r"\b(?:toutes les|chaque)\s+(\d{1,3}|une|deux|trois|quatre|cinq|six|huit|dix|douze)?\s*(minutes?|heures?)\b")
_NOMBRES = {"une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "huit": 8, "dix": 10, "douze": 12}
INTERVALLE_MIN = 5   # minutes : en dessous, une routine saturerait JARVIS


def intervalle_de(t: str):
    """Minutes entre deux lancements (« toutes les 2 heures », « toutes les 30 minutes », « chaque heure »), ou None."""
    m = _INTERVALLE.search(t)
    if not m:
        return None
    n = m.group(1)
    n = 1 if not n else (int(n) if n.isdigit() else _NOMBRES[n])
    return n * (60 if m.group(2).startswith("heure") else 1)


_MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"]
_UNE_FOIS = re.compile(r"\b(?:dans\s+(\d{1,3}|une|deux|trois|quatre|cinq|six|huit|dix|douze)\s*(minutes?|heures?)|(apres-demain|apres demain|demain)|le\s+(\d{1,2})(?:er)?\s+(" + "|".join(_MOIS) + r"))\b")
_AUTRE_OUTIL = re.compile(r"\b(?:rappel\w*|minuteur|timer|alarme|reveil|chrono\w*)\b")   # déjà gérés par module/alarmes_local.py


def une_fois_de(t: str, maintenant: datetime):
    """(datetime, texte_sans_la_date) pour « dans 2 heures », « demain à 8 h », « le 3 décembre à 9 h » ; None sinon. Une date sans heure : None (on demande)."""
    m = _UNE_FOIS.search(t)
    if not m or _AUTRE_OUTIL.search(t):
        return None
    reste = _UNE_FOIS.sub(" ", t, count=1)
    if m.group(1):
        n = m.group(1)
        n = int(n) if n.isdigit() else _NOMBRES[n]
        return maintenant + timedelta(minutes=n * (60 if m.group(2).startswith("heure") else 1)), reste
    hm = heure_de(t)
    if hm is None:
        return "heure", reste
    reste = _HEURE.sub(" ", reste, count=1)
    if m.group(3):
        jour = maintenant.date() + timedelta(days=1 if m.group(3) == "demain" else 2)
    else:
        mois = _MOIS.index(m.group(5)) + 1
        try:
            jour = maintenant.date().replace(month=mois, day=int(m.group(4)))
            if datetime.combine(jour, datetime.min.time()).replace(hour=hm[0], minute=hm[1]) < maintenant:
                jour = jour.replace(year=jour.year + 1)
        except ValueError:
            return "heure", reste   # 31 février
    return datetime.combine(jour, datetime.min.time()).replace(hour=hm[0], minute=hm[1]), reste


def analyser(texte: str, maintenant=None):
    """Phrase de création -> ('ok', routine) | ('heure', None) | ('interdit', commande) | ('commande', None) | None si ce n'est pas une création de routine."""
    t = norm(texte)
    pas = intervalle_de(t)
    if pas is not None:
        commande = re.sub(r"\s+", " ", re.sub(r"\b(?:jarvis|s'il te plait|stp)\b", " ", _INTERVALLE.sub(" ", t))).strip(" ,.;:!?-")
        commande = re.sub(r"^(?:(?:programme|planifie|automatise|ajoute|cree)\s+)?(?:(?:une|ma|la)\s+)?(?:nouvelle\s+)?(?:routine\s*(?:ou|:)?\s*)?", "", commande).strip(" ,.;:!?-")
        premier = re.split(r"[ \-]", commande)[0] if commande else ""
        if interdite(commande):
            return ("interdit", commande)   # comme pour les routines horaires : refusé, jamais exécuté à la place
        if not ("routine" in t or premier in _IMPERATIFS):
            return None
        if len(commande.split()) < 2:
            return ("commande", None)
        if pas < INTERVALLE_MIN:
            return ("trop_court", None)
        if premier == "surveille":   # veille : une recherche sur le sujet à chaque échéance (pas de comparaison avec la fois précédente)
            commande = "recherche les dernieres nouvelles sur " + commande.split(" ", 1)[1].removeprefix("les ").removeprefix("la ").removeprefix("le ")
        return ("ok", {"commande": commande, "chaque_min": pas})
    jours = jours_de(t)
    if jours is None:
        quand = une_fois_de(t, maintenant or datetime.now())
        if quand is None:
            return None
        date, reste = quand
        commande = re.sub(r"\s+", " ", re.sub(r"\b(?:jarvis|s'il te plait|stp|a|vers)\b", " ", reste)).strip(" ,.;:!?-")
        commande = re.sub(r"^(?:(?:programme|planifie|ajoute|cree)\s+)?(?:(?:une|ma|la)\s+)?(?:nouvelle\s+)?(?:routine\s*(?:ou|:)?\s*)?", "", commande).strip(" ,.;:!?-")
        premier = re.split(r"[ \-]", commande)[0] if commande else ""
        if interdite(commande):
            return ("interdit", commande)
        if not ("routine" in t or premier in _IMPERATIFS):
            return None
        if date == "heure":
            return ("heure", None)
        if len(commande.split()) < 2:
            return ("commande", None)
        if date < (maintenant or datetime.now()):
            return ("passe", None)
        return ("ok", {"commande": commande, "une_fois": date.timestamp()})
    commande = commande_de(t)
    premier = re.split(r"[ \-]", commande)[0] if commande else ""   # « donne-moi » -> « donne »
    hm = heure_de(t)
    if hm is not None and interdite(commande):
        return ("interdit", commande)   # « tous les jours à 8 h éteins le PC » : refusé, jamais exécuté à la place
    if not ("routine" in t or premier in _IMPERATIFS):
        return None   # « je me lève tous les jours à 8 h » : simple conversation
    if hm is None:
        return ("heure", None)
    if len(commande.split()) < 2:
        return ("commande", None)
    if interdite(commande):
        return ("interdit", commande)
    return ("ok", {"commande": commande, "heure": f"{hm[0]:02d}:{hm[1]:02d}", "jours": jours})


def decrire(r: dict) -> str:
    if r.get("une_fois"):
        return f"le {datetime.fromtimestamp(r['une_fois']).strftime('%d/%m à %H h %M')}, une seule fois : {r['commande']}"
    if r.get("chaque_min"):
        n = r["chaque_min"]
        return f"toutes les {n // 60} heures : {r['commande']}" if n % 60 == 0 and n > 60 else (f"toutes les heures : {r['commande']}" if n == 60 else f"toutes les {n} minutes : {r['commande']}")
    jours = r.get("jours") or _TOUS
    if jours == _TOUS:
        quand = "tous les jours"
    elif jours == _SEMAINE:
        quand = "en semaine"
    elif jours == _WEEKEND:
        quand = "le week-end"
    else:
        quand = "le " + " et le ".join(JOURS[j] for j in jours)
    h, m = r["heure"].split(":")
    return f"{quand} à {int(h)} heures{'' if m == '00' else ' ' + m} : {r['commande']}"


def a_lancer(r: dict, maintenant: datetime) -> bool:
    """La routine doit-elle partir maintenant ? Jour voulu, heure passée (de moins de RATTRAPAGE_MIN minutes), pas déjà lancée aujourd'hui."""
    if r.get("une_fois"):   # une seule fois : échue ; « en retard » est jugé par le démon (voir _surveiller)
        return maintenant.timestamp() >= r["une_fois"]
    if r.get("chaque_min"):   # à intervalle : depuis le dernier lancement (ou la création), sans rattrapage en rafale
        return maintenant.timestamp() - r.get("derniere_ts", 0) >= r["chaque_min"] * 60
    if maintenant.weekday() not in (r.get("jours") or _TOUS) or r.get("derniere") == maintenant.date().isoformat():
        return False
    h, m = (int(x) for x in r["heure"].split(":"))
    ecart = (maintenant.hour * 60 + maintenant.minute) - (h * 60 + m)
    return 0 <= ecart < RATTRAPAGE_MIN


# ── stockage ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def charger() -> dict:
    with _VERROU:
        try:
            with open(FICHIER, encoding="utf-8") as f:
                d = json.load(f)
            return {"actif": bool(d.get("actif", True)), "routines": list(d.get("routines", []))}
        except Exception:
            return {"actif": True, "routines": []}


def sauver(d: dict) -> None:
    with _VERROU:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        tmp = FICHIER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FICHIER)


# ── commandes vocales ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def resoudre_routines(texte: str):
    """Crée, liste, supprime, met en pause / reprend les routines. None si la phrase n'en parle pas."""
    with _VERROU:   # lire-modifier-écrire d'un seul tenant : le démon (autre thread) écrit « derniere » dans le même fichier
        return _resoudre(texte)


def _resoudre(texte: str):
    from core.interlocuteur import nom_virgule
    t = norm(texte)
    if re.search(r"\b(mes routines|les routines|liste des routines|quelles routines)\b", t) and not re.search(r"\b(supprime|annule|efface|enleve|desactive|active|reactive|reprends?|pause)\b", t):
        d = charger()
        if not d["routines"]:
            return f"Aucune routine programmée{nom_virgule()}."
        lignes = [f"{i}. {decrire(r)}" for i, r in enumerate(d["routines"], 1)]
        return ("Routines en pause. " if not d["actif"] else "") + f"Vous avez {len(lignes)} routine{'s' if len(lignes) > 1 else ''} : " + " ; ".join(lignes) + "."
    if "routine" in t and re.search(r"\b(supprime|annule|efface|enleve)\b", t):
        d = charger()
        if re.search(r"\b(toutes|tout)\b", t):
            n = len(d["routines"])
            d["routines"] = []
            sauver(d)
            return f"{n} routine{'s' if n > 1 else ''} supprimée{'s' if n > 1 else ''}{nom_virgule()}."
        m = re.search(r"\b(?:routine|numero|n°)\s*(\d+)\b", t)
        if m and 1 <= int(m.group(1)) <= len(d["routines"]):
            r = d["routines"].pop(int(m.group(1)) - 1)
            sauver(d)
            return f"Routine supprimée : {r['commande']}."
        return f"Quelle routine{nom_virgule()} ? Dites par exemple : supprime la routine 1, ou : supprime toutes les routines."
    if re.search(r"\b(desactive|suspends?|mets? en pause|stoppe)\b.*\broutines?\b", t) or re.search(r"\broutines?\b.*\b(en pause|desactivees?)\b", t):
        d = charger()
        d["actif"] = False
        sauver(d)
        return f"Routines en pause{nom_virgule()}. Dites « réactive les routines » pour les reprendre."
    if re.search(r"\b(active|reactive|reprends?|relance)\b.*\broutines?\b", t):
        d = charger()
        d["actif"] = True
        sauver(d)
        return f"Routines réactivées{nom_virgule()}."
    res = analyser(texte)
    if res is None:
        return None
    statut, valeur = res
    if statut == "heure":
        return f"À quelle heure{nom_virgule()} ? Dites par exemple : tous les jours à 8 heures, donne-moi la météo."
    if statut == "commande":
        return f"Que dois-je faire{nom_virgule()} ? Dites par exemple : tous les jours à 8 heures, donne-moi la météo."
    if statut == "passe":
        return f"Cette date est déjà passée{nom_virgule()}."
    if statut == "trop_court":
        return f"Pas moins de {INTERVALLE_MIN} minutes entre deux lancements{nom_virgule()}."
    if statut == "interdit":
        return f"Je ne programme pas « {valeur} » : une routine tourne sans personne pour la confirmer{nom_virgule()}."
    d = charger()
    if any(r["commande"] == valeur["commande"] and r.get("heure") == valeur.get("heure") and r.get("jours") == valeur.get("jours") and r.get("chaque_min") == valeur.get("chaque_min") for r in d["routines"]):
        return f"Cette routine existe déjà{nom_virgule()}."
    if valeur.get("chaque_min"):
        valeur["derniere_ts"] = time.time()   # premier lancement après un intervalle complet
    if len(d["routines"]) >= 30:
        return f"Vous avez déjà 30 routines{nom_virgule()}, supprimez-en une d'abord."
    d["routines"].append(valeur)
    sauver(d)
    return f"C'est noté{nom_virgule()} : {decrire(valeur)}."


# ── démon ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _lancer(commande: str) -> None:
    import asyncio

    import core.shared as shared
    from core.traitement import gerer_reponse_ia
    if shared.WS_LOOP is None:
        return
    asyncio.run_coroutine_threadsafe(gerer_reponse_ia(commande, de_confiance=True), shared.WS_LOOP)


def _surveiller():
    while True:
        time.sleep(30)
        try:
            with _VERROU:   # même verrou que resoudre_routines : une routine créée à cet instant ne se perd plus
                d = charger()
                if not d["actif"]:
                    continue
                maintenant, change = datetime.now(), False
                for r in list(d["routines"]):
                    if a_lancer(r, maintenant) and r.get("une_fois"):
                        d["routines"].remove(r)   # une seule fois : retirée avant le lancement, jamais deux fois
                        change = True
                        if maintenant.timestamp() - r["une_fois"] > RATTRAPAGE_MIN * 60 or interdite(r["commande"]):
                            print(f"[ROUTINE] Échéance manquée ou refusée, abandonnée : {r['commande']}")   # JARVIS éteint à l'heure dite : pas de lancement tardif
                            continue
                        print(f"[ROUTINE] {r['commande']} (une fois)")
                        _lancer(r["commande"])
                    elif a_lancer(r, maintenant):
                        r["derniere_ts"] = maintenant.timestamp()
                        r["derniere"] = maintenant.date().isoformat()   # marqué avant : une routine ne part jamais deux fois le même jour
                        change = True
                        if interdite(r["commande"]):
                            continue   # fichier modifié à la main : même règle qu'à la création
                        print(f"[ROUTINE] {r['commande']}")
                        _lancer(r["commande"])
                if change:
                    sauver(d)
        except Exception as e:
            print(f"[ROUTINE] Erreur : {e}")


def demarrer_daemon_routines():
    t = threading.Thread(target=_surveiller, daemon=True, name="RoutinesDaemon")
    t.start()
    return t
