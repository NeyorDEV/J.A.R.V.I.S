"""Macros vocales : une phrase qui enchaîne plusieurs commandes (« mode cinéma » = lumières, volume, télé).

Création à la voix : « quand je dis mode cinéma, baisse la lumière, mets le volume à 30 puis lance la télé ».
Stockage data/macros.json. Chaque étape est rejouée comme une phrase dite (core/traitement.gerer_reponse_ia), l'une après l'autre.
Même garde-fou que les routines : les commandes à effet sur le PC (arrêt, suppression, envoi de mail, fermeture…) sont refusées à la création.
« Test à blanc » : « teste à blanc mode cinéma » énumère les étapes sans rien exécuter.
La partie « comprendre la phrase » est pure (testée : tests/test_macros.py) ; seule lancer() touche au reste de JARVIS.
"""
import asyncio
import json
import os
import re
import threading

from module.routines import interdite, norm

FICHIER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "macros.json")
_VERROU = threading.RLock()
MAX_MACROS = 30
MAX_ETAPES = 10

_VERBES = ("dis", "donne", "lance", "ouvre", "joue", "mets", "met", "montre", "affiche", "fais", "annonce", "lis", "resume", "ecoute", "active", "desactive",
           "demande", "baisse", "monte", "augmente", "diminue", "coupe", "allume", "regle", "passe", "reprends", "pause", "cherche", "recherche", "dit", "mute")
_SEP = re.compile(r"\s*(?:,|;|\bpuis\b|\bensuite\b|\bet ensuite\b|\bapres\b)\s*|\s+et\s+(?=(?:" + "|".join(_VERBES) + r")\b)")
_CREER_QUAND = re.compile(r"^(?:jarvis\s+)?(?:quand|des que|lorsque|chaque fois que)\s+je\s+(?:te\s+)?(?:dis|dirai)\s+(?:que\s+)?[\"'«]?(.+?)[\"'»]?\s*[,:]\s*(?:tu\s+|il faut\s+)?(?:(?:fais|fait|lance|execute|enchaine)\s+)?(.+)$")
_CREER_MACRO = re.compile(r"^(?:jarvis\s+)?(?:cree|ajoute|enregistre|definis|fais)(?:\s+moi)?\s+(?:une\s+|ma\s+)?(?:nouvelle\s+)?macro\s+(?:appelee\s+|nommee\s+)?[\"'«]?(.*?)[\"'»]?\s*[:,]\s*(.+)$")
_A_BLANC = re.compile(r"\ba blanc\b|\b(?:simule|simuler)\b|\bque\s+(?:fait|ferait|contient)\b")


def separer_etapes(t: str) -> list:
    """Découpe « baisse la lumière, mets le volume à 30 puis lance la télé » en étapes (un « et » ne coupe que devant un verbe de commande)."""
    morceaux = [re.sub(r"^(?:et|puis|ensuite)\s+", "", p.strip(" .!?")) for p in _SEP.split(t) if p and p.strip(" .!?")]
    return [m for m in morceaux if m]


def analyser_creation(texte: str):
    """None si la phrase ne crée pas de macro ; sinon (statut, valeur) : « ok » avec la macro, ou « vide » / « interdit » / « trop » / « nom »."""
    t = norm(texte)
    m = _CREER_QUAND.match(t) or _CREER_MACRO.match(t)
    if not m:
        return None
    nom, reste = norm(m.group(1)).strip(" .,:;!?"), m.group(2)
    etapes = separer_etapes(reste)
    if not nom or len(nom.split()) > 6 or "jarvis" in nom:
        return "nom", nom
    if not etapes:
        return "vide", nom
    if len(etapes) > MAX_ETAPES:
        return "trop", len(etapes)
    for e in etapes:
        if interdite(e):
            return "interdit", e
    return "ok", {"nom": nom, "etapes": etapes}


def declencheur_de(texte: str) -> str:
    t = re.sub(r"\b(?:jarvis|s'il te plait|stp)\b", " ", norm(texte))
    return re.sub(r"\s+", " ", re.sub(r"[^\w' ]", " ", t)).strip()


def _contient(t: str, nom: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(nom) + r"(?!\w)", t))


def trouver(texte: str, macros: list, exact: bool = False):
    """La macro visée : phrase égale au nom (exact) ou phrase qui le contient (la plus longue d'abord, « mode cinéma » avant « cinéma »)."""
    t = declencheur_de(texte)
    for mac in sorted(macros, key=lambda x: -len(x["nom"])):
        if t == mac["nom"] or (not exact and _contient(t, mac["nom"])):
            return mac
    return None


def decrire(mac: dict) -> str:
    return f"{mac['nom']} : " + ", puis ".join(mac["etapes"])


def charger() -> list:
    with _VERROU:
        try:
            with open(FICHIER, encoding="utf-8") as f:
                return [m for m in json.load(f).get("macros", []) if m.get("nom") and m.get("etapes")]
        except Exception:
            return []


def sauver(macros: list) -> None:
    with _VERROU:
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        tmp = FICHIER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"macros": macros}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, FICHIER)


async def _derouler(mac: dict, executer) -> None:
    for etape in mac["etapes"]:
        if interdite(etape):   # fichier modifié à la main : même règle qu'à la création
            print(f"[MACRO] Étape refusée : {etape}")
            continue
        print(f"[MACRO] {mac['nom']} : {etape}")
        try:
            await executer(etape)
        except Exception as e:
            print(f"[MACRO] Erreur à l'étape « {etape} » : {type(e).__name__} : {e}")
        await asyncio.sleep(0.4)


_en_cours: set = set()   # garde une référence : une tâche sans référence peut être ramassée avant la fin


def lancer(mac: dict, executer=None):
    """Déroule les étapes en tâche de fond : la phrase qui l'a déclenchée garde le verrou de traitement, chaque étape passe après elle."""
    if executer is None:
        from core.traitement import gerer_reponse_ia
        executer = gerer_reponse_ia
    tache = asyncio.get_running_loop().create_task(_derouler(mac, executer))
    _en_cours.add(tache)
    tache.add_done_callback(_en_cours.discard)
    return tache


async def resoudre_macros(texte: str):
    """Crée, liste, supprime, simule à blanc et lance les macros. None si la phrase n'en parle pas."""
    from core.interlocuteur import nom_virgule
    with _VERROU:
        return _resoudre(texte, nom_virgule)


def _resoudre(texte: str, nom_virgule):
    t = norm(texte)
    macros = charger()
    creation = analyser_creation(texte)
    if creation:
        statut, valeur = creation
        if statut == "nom":
            return f"Quel nom pour cette macro{nom_virgule()} ? Dites par exemple : quand je dis mode cinéma, baisse la lumière puis lance la télé."
        if statut == "vide":
            return f"Que doit faire « {valeur} »{nom_virgule()} ? Listez les actions, séparées par « puis »."
        if statut == "trop":
            return f"Pas plus de {MAX_ETAPES} étapes par macro{nom_virgule()}."
        if statut == "interdit":
            return f"Je n'enregistre pas « {valeur} » : une macro s'enchaîne sans confirmation{nom_virgule()}."
        reste = [m for m in macros if m["nom"] != valeur["nom"]]
        if len(reste) >= MAX_MACROS:
            return f"Vous avez déjà {MAX_MACROS} macros{nom_virgule()}, supprimez-en une d'abord."
        remplace = len(reste) != len(macros)
        sauver(reste + [valeur])
        return f"Macro « {valeur['nom']} » {'remplacée' if remplace else 'enregistrée'}{nom_virgule()} : {len(valeur['etapes'])} étape{'s' if len(valeur['etapes']) > 1 else ''}. Dites-la pour la lancer, ou « teste à blanc {valeur['nom']} »."
    if re.search(r"\b(mes macros|les macros|liste des macros|quelles macros|liste mes macros)\b", t):
        if not macros:
            return f"Aucune macro enregistrée{nom_virgule()}. Dites par exemple : quand je dis mode cinéma, baisse la lumière puis lance la télé."
        return f"Vous avez {len(macros)} macro{'s' if len(macros) > 1 else ''} : " + " ; ".join(decrire(m) for m in macros) + "."
    if re.search(r"\b(supprime|efface|enleve|oublie)\b", t) and re.search(r"\bmacros?\b", t):
        if re.search(r"\b(toutes|tout)\b", t):
            sauver([])
            return f"{len(macros)} macro{'s' if len(macros) > 1 else ''} supprimée{'s' if len(macros) > 1 else ''}{nom_virgule()}."
        mac = trouver(texte, macros)
        if not mac:
            return f"Quelle macro{nom_virgule()} ? Dites par exemple : supprime la macro mode cinéma."
        sauver([m for m in macros if m is not mac])
        return f"Macro « {mac['nom']} » supprimée{nom_virgule()}."
    if _A_BLANC.search(t):
        mac = trouver(texte, macros)
        if not mac:
            return None   # « simule… » sans macro connue : pas pour nous
        lignes = [f"{i}. {e}" + (" (refusée, je ne la lancerais pas)" if interdite(e) else "") for i, e in enumerate(mac["etapes"], 1)]
        return f"Test à blanc, rien n'est exécuté. « {mac['nom']} » ferait : " + " ; ".join(lignes) + "."
    lancement = re.match(r"^(?:jarvis\s+)?(?:lance|execute|demarre|active)\s+(?:la\s+)?macro\b", t) or re.search(r"\bmacro\s+\w", t)
    mac = trouver(texte, macros, exact=not lancement)
    if mac:
        lancer(mac)
        return f"C'est parti{nom_virgule()}, {mac['nom']}."
    return None
