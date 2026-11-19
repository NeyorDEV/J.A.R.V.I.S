"""Recherche de parkings à la voix : « trouve-moi un parking ouvert à Saint-Étienne », « où me garer près de la gare de Lyon ».

Logique pure (testée dans tests/test_gev_parkings.py) : reconnaître la demande, classer les parkings autour d'un point, écrire la phrase.
Les données sont celles de la couche « Parkings · France » de God's Eye View (module/gev_donnees_fr.py, fichier parkings.json) ; l'accès réseau et la parole
sont dans plugins/vue_de_dieu_resolver.py. On ne promet jamais plus que les données : sans comptage en direct, la phrase le dit.
"""
import math
import re

_PARKING = re.compile(r"\b(parkings?|se garer|me garer|garer|stationner|stationnement)\b")
# « montre / affiche / active les parkings » reste la commande de la couche : on ne cherche que sur ces verbes
_CHERCHE = re.compile(r"\b(trouve|trouver|cherche|chercher|recherche|rechercher|indique|donne|propose|ou|y a t il|il y a|existe|connais)\b")
_LIEU = re.compile(r"\b(?:a proximite de|a cote de|pres de|pres du|proche de|autour de|dans|sur|vers|au|aux|en|a)\s+(?P<lieu>[^,.;!?]+?)\s*$")
_QUALIFICATIF = re.compile(r"\s+(?:ouverts?|libres?|gratuits?|disponibles?|pas chers?|s il te plait|stp|maintenant|en ce moment)$")
_PAS_UN_LIEU = re.compile(r"\b(vue de dieu|god s eye|couche|carte|direct|ecran)\b|^(direct|ce moment|maintenant)$")


def demande(t: str):
    """t : phrase en minuscules sans accents. -> {lieu, libre, gratuit, ouvert} ou None si ce n'est pas une recherche de parking avec un lieu."""
    t = re.sub(r"[-'’]", " ", t).strip(" .!?")
    p = _PARKING.search(t)
    if not p or not _CHERCHE.search(t):
        return None
    m = _LIEU.search(t[p.end():])
    if not m:
        return None
    lieu = m.group("lieu").strip()
    while True:
        nouveau = _QUALIFICATIF.sub("", lieu).strip()
        if nouveau == lieu:
            break
        lieu = nouveau
    lieu = re.sub(r"^(?:la ville de|le centre de|le centre ville de|centre ville de)\s+", "", lieu).strip()
    if not lieu or _PAS_UN_LIEU.search(lieu):
        return None
    return {"lieu": lieu, "libre": bool(re.search(r"\b(libres?|disponibles?|places?)\b", t)), "gratuit": bool(re.search(r"\bgratuits?\b", t)), "ouvert": bool(re.search(r"\bouverts?\b", t))}


def distance_km(lat1, lon1, lat2, lon2) -> float:
    a = math.sin(math.radians(lat2 - lat1) / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def classer(parkings, lat, lon, gratuit=False, libre=False, ouvert=False, rayon_km=3.0, n=3) -> list:
    """Les `n` parkings les plus proches : [(distance km, parking)]. Colonnes de parkings.json : 5 gratuit, 13 places libres (None = inconnu), 15 statut.
    Quand on demande « ouvert » ou « libre », un parking dont le comptage en direct confirme des places passe devant (bonus de 500 m) ; un parking sans comptage reste proposé."""
    candidats = []
    for p in parkings:
        if gratuit and not p[5]:
            continue
        if (ouvert or libre) and p[15] in ("ferme", "abonnes"):   # fermé ou réservé aux abonnés : ni ouvert ni libre pour un client de passage
            continue
        if libre and (p[15] == "complet" or (p[13] is not None and p[13] <= 0)):
            continue
        d = distance_km(lat, lon, p[2], p[3])
        confirme = p[13] is not None and p[13] > 0 and p[15] == "ouvert"
        candidats.append((d - (0.5 if confirme and (libre or ouvert) else 0.0), d, p))
    candidats.sort(key=lambda c: c[0])
    proches = [c for c in candidats if c[1] <= rayon_km] or [c for c in candidats if c[1] <= rayon_km * 3]
    return [(d, p) for _, d, p in proches[:n]]


def _distance_dite(d: float) -> str:
    if d < 0.05:
        return "tout près"
    if d < 1:
        return f"{round(d * 100) * 10} mètres"
    return f"{d:.1f}".replace(".", ",") + " kilomètres"


def _etat_dit(p) -> str:
    places = f" sur {p[4]}" if p[4] else ""
    if p[13] is not None:
        if p[15] == "ferme":
            return "fermé"
        if p[15] == "abonnes":
            return "réservé aux abonnés en ce moment"
        if p[13] == 0:
            return "complet"
        return f"{p[13]} place{'s' if p[13] > 1 else ''} libre{'s' if p[13] > 1 else ''}{places}"
    return (f"{p[4]} places, " if p[4] else "capacité inconnue, ") + "disponibilité en direct non communiquée"


def phrase(lieu: str, trouves, libre=False, ouvert=False, gratuit=False) -> str:
    qualif = (" gratuit" if gratuit else "") + (" ouvert" if ouvert else "")
    if not trouves:
        return f"Je ne trouve aucun parking{qualif} près de {lieu} dans les données ouvertes que j'ai."
    morceaux = [f"{p[0]}, à {_distance_dite(d)}, {_etat_dit(p)}" for d, p in trouves]
    texte = f"Près de {lieu}, le plus proche : {morceaux[0]}."
    if len(morceaux) > 1:
        texte += " Ensuite : " + " ; ".join(morceaux[1:]) + "."
    if (ouvert or libre) and not any(p[13] is not None for _, p in trouves):
        texte += " Je n'ai ni les horaires ni le comptage en direct dans cette ville : je ne peux pas garantir qu'ils soient ouverts."
    return texte
