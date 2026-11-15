"""Radars automatiques français pour God's Eye View (Vue de Dieu), sans toucher à l'appli.

Source : liste officielle de la Sécurité routière (radars.securite-routiere.gouv.fr, un seul fichier JSON de ~2 Mo : identifiant, type, coordonnées). OpenStreetMap / Overpass
a été essayé d'abord : les serveurs publics sont souvent saturés (502, délais dépassés) et le fichier n'arrivait pas. Les radars mobiles et les « itinéraires » (tracés, pas des
points) ne sont pas dans la liste affichée. Le fichier `data/gods_eye_view/radars_france.json` est refait au plus une fois par semaine, EN TÂCHE DE FOND ; sans réseau,
l'ancien est gardé. Il est servi à la page par le plugin `jarvisRadarsFrance` de module/vue_de_dieu.py, qui l'ajoute au calque « ALPR » (US / Canada) de l'appli.

Format : liste de [identifiant (texte), latitude, longitude, limite km/h (absente de la liste officielle : ajoutée depuis OpenStreetMap quand un radar OSM est à moins de 50 m, sinon null), sens en degrés (idem), type, référence (null)] ; type parmi « fixe », « discriminant »,
« feu rouge », « passage à niveau », « vitesse moyenne », « urbain ».
Voir docs/VUE_DE_DIEU.md. Test : scratch/outils_test/test_gev_radars_fr_reel.py.
"""

import json
import math
import os
import threading
import time

import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FICHIER = os.path.join(RACINE, "data", "gods_eye_view", "radars_france.json")
VALIDITE_S = 7 * 24 * 3600
URL = "https://radars.securite-routiere.gouv.fr/radars/all?_format=json"
ENTETES = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)", "Accept": "application/json"}
ECARTES = {"itineraire"}   # tracés d'itinéraires (lignes), pas des radars en un point
ESSAIS = 3
OSM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gev_radars_osm_fr.json")   # radars OpenStreetMap (limite, sens) : instantané du 13/11/2026, 3 879 radars, voir enrichir()
RAYON_M = 50   # un radar officiel et un radar OpenStreetMap à moins de 50 m sont le même
_verrou = threading.Lock()
_en_cours = {"actif": False}


def convertir(liste: list) -> list:
    """Liste officielle -> liste compacte ; ignore les itinéraires et tout élément sans identifiant ni coordonnées valides."""
    sortie = []
    for r in liste or []:
        try:
            ident, lat, lon = str(r["id"]).strip(), float(r["lat"]), float(r["lng"])   # identifiants numériques (« 20006 ») ou à lettres (« FE110000 », feux rouges)
        except (KeyError, TypeError, ValueError):
            continue
        if not ident or r.get("type") in ECARTES or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        genre = str(r.get("typeLabel") or "").strip()
        genre = genre[6:] if genre.lower().startswith("radar ") else genre
        sortie.append([ident, round(lat, 5), round(lon, 5), None, None, genre.lower() or "radar", None])
    return sortie


def enrichir(radars: list) -> list:
    """Ajoute la limite de vitesse et le sens (3e et 4e éléments) aux radars officiels grâce au radar OpenStreetMap le plus proche (à moins de RAYON_M, qui a une limite ou un sens).
    La liste officielle ne les publie pas. Les données OpenStreetMap sont un instantané embarqué (OSM, `scratch/outils_test/extraire_radars_osm.py` le refait à partir d'un extrait
    Geofabrik : à relancer de temps en temps) : sans fichier, ou radar sans voisin, la liste est rendue telle quelle."""
    try:
        with open(OSM, encoding="utf-8") as f:
            osm = json.load(f)
    except (OSError, ValueError):
        return radars
    case = lambda lat, lon: (math.floor(lat * 100), math.floor(lon * 100))   # cases d'environ 1 km : on ne compare qu'avec les 9 voisines
    grille = {}
    for o in osm:
        if o[3] or o[4] is not None:
            grille.setdefault(case(o[1], o[2]), []).append(o)
    for r in radars:
        i, j = case(r[1], r[2])
        proche, d_min = None, RAYON_M
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for o in grille.get((i + di, j + dj), ()):
                    d = math.hypot((o[1] - r[1]) * 110540, (o[2] - r[2]) * 111320 * math.cos(math.radians(r[1])))
                    if d <= d_min:
                        proche, d_min = o, d
        if proche:
            r[3], r[4] = proche[3], proche[4]
    return radars


def telecharger(timeout: float = 40.0) -> list:
    """Télécharge la liste officielle (quelques essais espacés) ; liste vide en cas d'échec."""
    for essai in range(ESSAIS):
        if essai:
            time.sleep(10 * essai)
        try:
            r = requests.get(URL, headers=ENTETES, timeout=timeout)
            if r.ok:
                return enrichir(convertir(r.json()))
            print(f"[RADARS FR] HTTP {r.status_code}")
        except (requests.RequestException, ValueError) as e:
            print(f"[RADARS FR] {type(e).__name__}")
    return []


def _age_s() -> float:
    try:
        return time.time() - os.path.getmtime(FICHIER)
    except OSError:
        return float("inf")


def rafraichir(timeout: float = 40.0) -> bool:
    """Refait le fichier ; sans résultat plausible (moins de 1 000 radars), l'ancien est gardé. Renvoie True si le fichier a été remplacé."""
    with _verrou:
        radars = telecharger(timeout)
        if len(radars) < 1000:
            return False
        os.makedirs(os.path.dirname(FICHIER), exist_ok=True)
        tmp = FICHIER + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(radars, f, separators=(",", ":"))
        os.replace(tmp, FICHIER)
        print(f"[RADARS FR] {len(radars)} radars écrits")
        return True


def preparer() -> dict:
    """À appeler juste avant de lancer le serveur de God's Eye View. Lance en tâche de fond le téléchargement si le fichier manque ou a plus d'une semaine.
    Renvoie les variables d'environnement à donner au serveur : le chemin du fichier (qui peut ne pas exister encore : la page patiente)."""
    if _age_s() > VALIDITE_S and not _en_cours["actif"]:
        _en_cours["actif"] = True

        def _fond():
            try:
                rafraichir()
            finally:
                _en_cours["actif"] = False
        threading.Thread(target=_fond, daemon=True).start()
    return {"JARVIS_RADARS_FILE": FICHIER}
