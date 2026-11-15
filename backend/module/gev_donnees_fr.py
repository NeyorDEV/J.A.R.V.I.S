"""Données ouvertes françaises pour les couches ajoutées par JARVIS à God's Eye View (module/gev_couches.js), sans clé, téléchargées EN TÂCHE DE FOND dans data/gods_eye_view/donnees/.

  recharge.json  Bornes de recharge électrique (IRVE, fichier consolidé de data.gouv.fr / transport.data.gouv.fr, ~120 Mo en CSV, refait toutes les semaines)
                 [identifiant, lat, lon, nom, opérateur, nombre de points de charge, puissance max (kW), prises, gratuit (bool), horaires]
  crues.json     Vigilance crues par tronçon (Vigicrues, ministère de la Transition écologique, refait toutes les 20 minutes) [nom, niveau 1 vert à 4 rouge, lignes [[lon, lat], ...]]
  seismes.json   Séismes des 30 derniers jours (EMSC, service FDSN, refait toutes les 10 minutes) [identifiant, lat, lon, profondeur km, magnitude, heure ISO, région]
  air.json       Qualité de l'air européenne (Open-Meteo, modèle CAMS Europe, CC BY 4.0, refait toutes les 2 heures) [ville, lat, lon, indice européen 1 à 6, PM2.5, PM10, NO2, O3, heure]
  vigilance.json Vigilance Météo-France par département (API « Bulletin Vigilance », clé METEOFRANCE_API_KEY abonnée à cette API, Licence Ouverte, refait toutes les 15 minutes)
                 {"maj": ISO, "periodes": [{"e": "J" | "J1", "d": début, "f": fin, "z": {code département: [niveau max 1 à 4, {phénomène: niveau}]}}], "depts": [[code, nom, polygones]]}
                 Contours : départements simplifiés (github.com/gregoiredavid/france-geojson, Licence Ouverte, données IGN / Etalab), téléchargés une fois et gardés 6 mois (departements.json).
Les restrictions de drones (IGN, 90 000 polygones) ne sont PAS téléchargées : le plugin jarvisCouches les demande à l'IGN par fenêtre visible (voir vue_de_dieu.py).
Test : scratch/outils_test/test_gev_donnees_fr.py.
"""

import codecs
import csv
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOSSIER = os.path.join(RACINE, "data", "gods_eye_view", "donnees")
ENTETES = {"User-Agent": "JARVIS-Assistant/1.0 (personal use)"}
URL_IRVE = "https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"
URL_CRUES = "https://www.vigicrues.gouv.fr/services/InfoVigiCru.geojson"
URL_SEISMES = "https://www.seismicportal.eu/fdsnws/event/1/query"
URL_VIGILANCE = "https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours"
URL_DEPARTEMENTS = "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-avec-outre-mer.geojson"
URL_AIR = "https://air-quality-api.open-meteo.com/v1/air-quality"
_etat = {"stop": threading.Event(), "fil": None}

VILLES = [  # (nom, lat, lon) : préfectures et grandes villes de métropole ; Open-Meteo recale chaque point sur sa grille (~11 km)
    ("Paris", 48.857, 2.352), ("Marseille", 43.296, 5.370), ("Lyon", 45.764, 4.836), ("Toulouse", 43.605, 1.444), ("Nice", 43.710, 7.262), ("Nantes", 47.218, -1.554),
    ("Montpellier", 43.611, 3.877), ("Strasbourg", 48.573, 7.752), ("Bordeaux", 44.838, -0.579), ("Lille", 50.629, 3.057), ("Rennes", 48.117, -1.678), ("Reims", 49.258, 4.032),
    ("Saint-Étienne", 45.439, 4.387), ("Le Havre", 49.494, 0.108), ("Toulon", 43.124, 5.928), ("Grenoble", 45.189, 5.724), ("Dijon", 47.322, 5.041), ("Angers", 47.478, -0.563),
    ("Nîmes", 43.837, 4.360), ("Clermont-Ferrand", 45.777, 3.087), ("Le Mans", 48.006, 0.199), ("Aix-en-Provence", 43.530, 5.447), ("Brest", 48.390, -4.486), ("Tours", 47.394, 0.684),
    ("Amiens", 49.894, 2.296), ("Limoges", 45.833, 1.261), ("Metz", 49.119, 6.176), ("Perpignan", 42.699, 2.895), ("Besançon", 47.238, 6.024), ("Orléans", 47.902, 1.909),
    ("Rouen", 49.443, 1.099), ("Caen", 49.182, -0.371), ("Nancy", 48.692, 6.184), ("Mulhouse", 47.750, 7.336), ("Avignon", 43.949, 4.806), ("Poitiers", 46.580, 0.340),
    ("Pau", 43.295, -0.371), ("La Rochelle", 46.160, -1.152), ("Calais", 50.951, 1.858), ("Ajaccio", 41.919, 8.738), ("Bastia", 42.697, 9.451), ("Annecy", 45.899, 6.129),
    ("Biarritz", 43.483, -1.559), ("Troyes", 48.297, 4.074), ("Valence", 44.933, 4.892), ("Chambéry", 45.564, 5.917), ("Quimper", 47.997, -4.097), ("Lorient", 47.748, -3.370),
    ("Vannes", 47.658, -2.760), ("Cherbourg", 49.634, -1.622), ("Brive-la-Gaillarde", 45.158, 1.532), ("Cahors", 44.448, 1.441), ("Albi", 43.929, 2.148), ("Tarbes", 43.233, 0.078),
    ("Carcassonne", 43.213, 2.349), ("Aurillac", 44.926, 2.444), ("Le Puy-en-Velay", 45.043, 3.885), ("Gap", 44.559, 6.079), ("Digne-les-Bains", 44.092, 6.236), ("Bourges", 47.081, 2.398),
    ("Nevers", 46.990, 3.159), ("Auxerre", 47.798, 3.567), ("Chartres", 48.443, 1.489), ("Évreux", 49.027, 1.151), ("Laval", 48.073, -0.770), ("Saint-Brieuc", 48.514, -2.760),
    ("Angoulême", 45.649, 0.156), ("Niort", 46.324, -0.464), ("La Roche-sur-Yon", 46.670, -1.426), ("Châteauroux", 46.811, 1.693), ("Montauban", 44.018, 1.355), ("Agen", 44.203, 0.616),
    ("Mont-de-Marsan", 43.890, -0.500), ("Périgueux", 45.184, 0.722), ("Épinal", 48.173, 6.451), ("Charleville-Mézières", 49.762, 4.724), ("Châlons-en-Champagne", 48.957, 4.363),
    ("Beauvais", 49.430, 2.083), ("Arras", 50.292, 2.777), ("Colmar", 48.079, 7.358), ("Belfort", 47.640, 6.863), ("Vesoul", 47.620, 6.155), ("Lons-le-Saunier", 46.675, 5.555),
    ("Mâcon", 46.306, 4.832), ("Bourg-en-Bresse", 46.206, 5.226), ("Roanne", 46.034, 4.068), ("Vichy", 46.128, 3.426), ("Montluçon", 46.340, 2.603), ("Guéret", 46.171, 1.871),
    ("Tulle", 45.267, 1.768), ("Foix", 42.965, 1.607), ("Rodez", 44.350, 2.575), ("Mende", 44.518, 3.500), ("Privas", 44.735, 4.598), ("Saint-Nazaire", 47.273, -2.214),
    ("Cannes", 43.553, 7.017), ("Saint-Malo", 48.649, -2.026), ("Dunkerque", 51.034, 2.377), ("Valenciennes", 50.357, 3.523), ("Thionville", 49.358, 6.168), ("Bayonne", 43.493, -1.475),
]
_FR = (-23.0, 52.0, -63.0, 56.0)   # (sud, nord, ouest, est) : métropole et outre-mer


def _ecrire(nom: str, donnees) -> None:
    os.makedirs(DOSSIER, exist_ok=True)
    chemin = os.path.join(DOSSIER, nom + ".json")
    tmp = chemin + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, chemin)


def age(nom: str) -> float:
    try:
        return time.time() - os.path.getmtime(os.path.join(DOSSIER, nom + ".json"))
    except OSError:
        return float("inf")


def _f(v, d=None):
    try:
        x = float(str(v).replace(",", "."))
        return x if x == x else d
    except (TypeError, ValueError):
        return d


# --- bornes de recharge ----------------------------------------------------------------------------------------------------------------------------------------------
def regrouper_irve(lignes) -> list:
    """Lignes du CSV consolidé (un point de charge par ligne) -> une entrée par station ; ignore les stations sans position valide en France."""
    stations = {}
    for r in lignes:
        ident = (r.get("id_station_itinerance") or "").strip()
        lat, lon = _f(r.get("consolidated_latitude")), _f(r.get("consolidated_longitude"))
        if lat is None or lon is None or not (_FR[0] < lat < _FR[1] and _FR[2] < lon < _FR[3]) or (r.get("consolidated_is_lon_lat_correct") or "").lower() == "false":
            continue
        if not ident.upper().startswith("FR"):   # « Non concerné », vide… : plusieurs stations partagent cette valeur, on les distingue par leur nom et leur position
            ident = f"{(r.get('nom_station') or '').strip()}|{round(lat, 4)}|{round(lon, 4)}"
        s = stations.get(ident)
        if s is None:
            s = stations[ident] = {"lat": lat, "lon": lon, "nom": (r.get("nom_station") or "").strip(), "op": (r.get("nom_operateur") or r.get("nom_enseigne") or "").strip(),
                                   "pdc": set(), "kw": 0.0, "prises": set(), "gratuit": (r.get("gratuit") or "").lower() == "true", "h": (r.get("horaires") or "").strip()}
        s["pdc"].add((r.get("id_pdc_itinerance") or str(len(s["pdc"]))).strip())
        s["kw"] = max(s["kw"], _f(r.get("puissance_nominale"), 0.0) or 0.0)
        for cle, nom in (("prise_type_2", "T2"), ("prise_type_combo_ccs", "CCS"), ("prise_type_chademo", "CHAdeMO"), ("prise_type_ef", "E/F")):
            if (r.get(cle) or "").lower() == "true":
                s["prises"].add(nom)
    sortie = []
    for ident, s in stations.items():
        kw = s["kw"] / 1000.0 if s["kw"] > 1000 else s["kw"]   # certaines lignes donnent des watts
        sortie.append([ident, round(s["lat"], 5), round(s["lon"], 5), s["nom"][:70], s["op"][:50], len(s["pdc"]), round(kw, 1), " ".join(sorted(s["prises"])), s["gratuit"], s["h"][:60]])
    return sortie


def maj_recharge() -> bool:
    try:
        with requests.get(URL_IRVE, headers=ENTETES, timeout=180, stream=True) as r:
            r.raise_for_status()
            donnees = regrouper_irve(csv.DictReader(codecs.iterdecode(r.iter_lines(), "utf-8", errors="replace")))
        if len(donnees) < 5000:   # un fichier tronqué ne doit pas remplacer un bon
            return False
        _ecrire("recharge", donnees)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Recharge : {type(e).__name__}")
        return False


# --- crues ------------------------------------------------------------------------------------------------------------------------------------------------------------
def convertir_crues(geo: dict) -> list:
    sortie = []
    for f in (geo or {}).get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        niveau = p.get("NivInfViCr")
        if g.get("type") != "MultiLineString" or niveau not in (1, 2, 3, 4):
            continue
        lignes = [[[round(x[0], 4), round(x[1], 4)] for x in ligne if len(x) >= 2] for ligne in g.get("coordinates", [])]
        lignes = [l for l in lignes if len(l) >= 2]
        if lignes:
            sortie.append([str(p.get("lbentcru") or p.get("CdEntCru") or "?")[:60], niveau, lignes])
    return sortie


def maj_crues() -> bool:
    try:
        r = requests.get(URL_CRUES, headers=ENTETES, timeout=90)
        r.raise_for_status()
        donnees = convertir_crues(r.json())
        if len(donnees) < 100:
            return False
        _ecrire("crues", donnees)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Crues : {type(e).__name__}")
        return False


# --- séismes ----------------------------------------------------------------------------------------------------------------------------------------------------------
def convertir_seismes(geo: dict) -> list:
    sortie = []
    for f in (geo or {}).get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        c = g.get("coordinates") or []
        mag = _f(p.get("mag"))
        if len(c) < 2 or mag is None or _f(c[0]) is None or _f(c[1]) is None:
            continue
        sortie.append([str(p.get("unid") or f.get("id")), round(c[1], 4), round(c[0], 4), round(abs(_f(p.get("depth"), 0.0) or 0.0), 1), round(mag, 1), str(p.get("time") or "")[:19], str(p.get("flynn_region") or "").title()[:40]])
    return sortie


def maj_seismes() -> bool:
    try:
        debut = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
        r = requests.get(URL_SEISMES, headers=ENTETES, timeout=60, params={"format": "json", "minlat": 41, "maxlat": 51.5, "minlon": -5.5, "maxlon": 10, "minmag": 1.5, "starttime": debut, "limit": 2000, "orderby": "time"})
        r.raise_for_status()
        _ecrire("seismes", convertir_seismes(r.json()))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Séismes : {type(e).__name__}")
        return False


# --- qualité de l'air -------------------------------------------------------------------------------------------------------------------------------------------------
def convertir_air(reponse) -> list:
    sortie = []
    for (nom, lat, lon), r in zip(VILLES, reponse if isinstance(reponse, list) else [reponse]):
        c = (r or {}).get("current") or {}
        aqi = _f(c.get("european_aqi"))
        if aqi is None:
            continue
        niveau = 1 if aqi <= 20 else 2 if aqi <= 40 else 3 if aqi <= 60 else 4 if aqi <= 80 else 5 if aqi <= 100 else 6   # barème de l'indice européen (EAQI)
        sortie.append([nom, lat, lon, niveau, _f(c.get("pm2_5")), _f(c.get("pm10")), _f(c.get("nitrogen_dioxide")), _f(c.get("ozone")), str(c.get("time") or "")])
    return sortie


def maj_air() -> bool:
    try:
        r = requests.get(URL_AIR, headers=ENTETES, timeout=60, params={"latitude": ",".join(str(v[1]) for v in VILLES), "longitude": ",".join(str(v[2]) for v in VILLES),
                                                                       "current": "european_aqi,pm2_5,pm10,nitrogen_dioxide,ozone"})
        r.raise_for_status()
        donnees = convertir_air(r.json())
        if len(donnees) < 50:
            return False
        _ecrire("air", donnees)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Air : {type(e).__name__}")
        return False


# --- vigilance météo ----------------------------------------------------------------------------------------------------------------------------------------------------
def _anneau(a, tol=0.004):
    sortie, dernier = [], None
    for x, y in a:
        if dernier is None or abs(x - dernier[0]) > tol or abs(y - dernier[1]) > tol:
            dernier = (x, y); sortie.append([round(x, 3), round(y, 3)])
    return sortie if len(sortie) >= 4 else None


def convertir_departements(geo: dict) -> list:
    """GeoJSON des départements -> [code, nom, polygones simplifiés (anneaux [lon, lat])]."""
    sortie = []
    for f in (geo or {}).get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        polys = g.get("coordinates", []) if g.get("type") == "MultiPolygon" else [g.get("coordinates", [])] if g.get("type") == "Polygon" else []
        simples = [[a for a in (_anneau(an) for an in poly) if a] for poly in polys]
        simples = [pl for pl in simples if pl]
        if p.get("code") and simples:
            sortie.append([str(p["code"]), str(p.get("nom") or ""), simples])
    return sortie


def _departements() -> list:
    chemin = os.path.join(DOSSIER, "departements.json")
    if age("departements") < 180 * 86400:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    r = requests.get(URL_DEPARTEMENTS, headers=ENTETES, timeout=90)
    r.raise_for_status()
    d = convertir_departements(r.json())
    if len(d) < 90:
        raise ValueError("départements incomplets")
    _ecrire("departements", d)
    return d


def convertir_vigilance(carte: dict) -> list:
    """Réponse de l'API -> périodes [{"e", "d", "f", "z"}] ; le domaine national « FRA » est ignoré, les zones littorales (code + « 10 ») sont gardées telles quelles."""
    sortie = []
    for per in ((carte or {}).get("product") or {}).get("periods", []):
        zones = {}
        for dom in (per.get("timelaps") or {}).get("domain_ids", []):
            code = str(dom.get("domain_id") or "")
            if not code or code == "FRA":
                continue
            phen = {str(i.get("phenomenon_id")): int(i.get("phenomenon_max_color_id") or 1) for i in dom.get("phenomenon_items", [])}
            zones[code] = [int(dom.get("max_color_id") or 1), phen]
        if zones:
            sortie.append({"e": per.get("echeance"), "d": per.get("begin_validity_time"), "f": per.get("end_validity_time"), "z": zones})
    return sortie


def maj_vigilance() -> bool:
    from module import gev_cles
    cle = gev_cles.lire("METEOFRANCE_API_KEY")
    if not cle:
        return False
    try:
        r = requests.get(URL_VIGILANCE, headers={**ENTETES, "apikey": cle}, timeout=60)
        r.raise_for_status()
        carte = r.json()
        periodes = convertir_vigilance(carte)
        if not periodes:
            return False
        _ecrire("vigilance", {"maj": ((carte.get("product") or {}).get("update_time")), "periodes": periodes, "depts": _departements()})
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Vigilance : {type(e).__name__}")
        return False


# nom -> (mise à jour, validité en secondes)
JEUX = {"vigilance": (maj_vigilance, 900), "seismes": (maj_seismes, 600), "crues": (maj_crues, 1200), "air": (maj_air, 7200), "recharge": (maj_recharge, 7 * 86400)}


def _boucle() -> None:
    while not _etat["stop"].is_set():
        for nom, (maj, validite) in JEUX.items():
            if _etat["stop"].is_set():
                return
            if age(nom) > validite:
                maj()
        _etat["stop"].wait(300)


def demarrer() -> dict:
    """Lance la mise à jour en tâche de fond (une seule fois par vue) ; renvoie la variable d'environnement du serveur de la vue."""
    if _etat["fil"] is None or not _etat["fil"].is_alive():
        _etat["stop"].clear()
        _etat["fil"] = threading.Thread(target=_boucle, daemon=True, name="donnees-fr")
        _etat["fil"].start()
    return {"JARVIS_DONNEES_DIR": DOSSIER}


def arreter() -> None:
    _etat["stop"].set()
