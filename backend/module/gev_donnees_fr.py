"""Données ouvertes françaises pour les couches ajoutées par JARVIS à God's Eye View (module/gev_couches.js), sans clé, téléchargées EN TÂCHE DE FOND dans data/gods_eye_view/donnees/.

  recharge.json  Bornes de recharge électrique (IRVE, fichier consolidé de data.gouv.fr / transport.data.gouv.fr, ~120 Mo en CSV, refait toutes les semaines)
                 [identifiant, lat, lon, nom, opérateur, nombre de points de charge, puissance max (kW), prises, gratuit (bool), horaires]
  parkings.json  Parkings (statique : BNLS, Saemes, Indigo, Saint-Étienne, Orléans, refait chaque semaine ; en direct : Nantes, Aix-Marseille, Tours, Clermont, toutes les 5 minutes)
                 [nom, adresse, lat, lon, places, gratuit 0/1, PMR, bornes électriques, hauteur max cm, tarif 1 h, tarif 24 h, exploitant, lien, places libres ou None, mise à jour, statut]
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
import io
import json
import os
import re
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


# --- bulletins d'estimation du risque d'avalanche (BRA) -----------------------------------------------------------------------------------------------------------------
URL_BRA = "https://files.data.gouv.fr/meteofrance/data/BULLETIN/BRA/"   # archive ouverte de Météo-France : {année}/{mois}/{jour}/xml/{massif}_{horodatage}.xml, sans clé
URL_MASSIFS = "https://www.data.gouv.fr/api/1/datasets/archive-des-bulletins-avalanches/"   # la ressource « geojson » = contours des 36 massifs


def _nom_cle(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").lower().replace("-", " ").replace("'", " ").replace("nn", "n").strip()   # « Embrunnais » (contours) / « Embrunais » (bulletin)


def convertir_massifs(geo: dict) -> list:
    """GeoJSON des massifs -> [code, nom, chaîne de montagnes, polygones simplifiés]."""
    sortie = []
    for f in (geo or {}).get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        polys = g.get("coordinates", []) if g.get("type") == "MultiPolygon" else [g.get("coordinates", [])] if g.get("type") == "Polygon" else []
        simples = [pl for pl in ([a for a in (_anneau(an, 0.002) for an in poly) if a] for poly in polys) if pl]
        if p.get("title") and simples:
            sortie.append([p.get("code"), str(p["title"]), str(p.get("mountain") or ""), simples])
    return sortie


def _massifs() -> list:
    chemin = os.path.join(DOSSIER, "massifs.json")
    if age("massifs") < 180 * 86400:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    meta = requests.get(URL_MASSIFS, headers=ENTETES, timeout=60).json()
    url = next(x["url"] for x in meta.get("resources", []) if x.get("format") == "geojson")
    r = requests.get(url, headers=ENTETES, timeout=60)
    r.raise_for_status()
    m = convertir_massifs(r.json())
    if len(m) < 30:
        raise ValueError("massifs incomplets")
    _ecrire("massifs", m)
    return m


def _liens(url: str) -> list:
    import re
    r = requests.get(url, headers=ENTETES, timeout=30)
    return re.findall(r'href="([^"]+)"', r.text) if r.ok else []


def _extraire_bulletin(xml: str) -> dict:
    """XML d'un bulletin -> champs utiles (niveaux 1 à 5 ; altitude et niveau du versant haut quand le risque change avec l'altitude)."""
    import defusedxml.ElementTree as ET
    racine = ET.fromstring(xml.encode("utf-8"))
    risque = racine.find("./CARTOUCHERISQUE/RISQUE")
    a = risque.attrib if risque is not None else {}
    entier = lambda v: int(v) if str(v).strip().isdigit() else None  # noqa: E731
    resume = (racine.findtext("./CARTOUCHERISQUE/RESUME") or "").strip()
    return {"r": entier(a.get("RISQUEMAXI")), "r2": entier(a.get("RISQUEMAXIJ2")), "r1": entier(a.get("RISQUE1")), "hautr": entier(a.get("RISQUE2")), "alt": a.get("ALTITUDE") or "",
            "com": (a.get("COMMENTAIRE") or "").strip(), "resume": resume, "date": racine.attrib.get("DATEBULLETIN"), "fin": racine.attrib.get("DATEECHEANCE")}


def maj_avalanche() -> bool:
    """Dernier bulletin de chaque massif (dossier du jour ou, hors saison, du dernier jour publié dans les 10 derniers) + contours des massifs."""
    try:
        massifs = _massifs()
        par_nom = {_nom_cle(m[1]): m for m in massifs}
        bulletins, jour = {}, None
        for recul in range(0, 10):
            d = datetime.now(timezone.utc) - timedelta(days=recul)
            base = f"{URL_BRA}{d.year}/{d.month:02d}/{d.day:02d}/xml/"
            fichiers = [x for x in _liens(base) if x.lower().endswith(".xml")]
            if fichiers:
                jour = d.date().isoformat()
                break
        if jour:
            from urllib.parse import unquote
            derniers = {}
            for chemin in fichiers:   # plusieurs versions possibles par massif : on garde l'horodatage le plus récent
                nom = unquote(chemin.rsplit("/", 1)[-1])[:-4]
                massif, _, stamp = nom.rpartition("_")
                if _nom_cle(massif) in par_nom and stamp >= derniers.get(_nom_cle(massif), ("", ""))[0]:
                    derniers[_nom_cle(massif)] = (stamp, chemin)
            for cle, (_, chemin) in derniers.items():
                try:
                    r = requests.get("https://files.data.gouv.fr" + chemin, headers=ENTETES, timeout=30)
                    r.raise_for_status()
                    bulletins[cle] = _extraire_bulletin(r.text)
                except Exception as e:  # noqa: BLE001 — un massif en échec n'empêche pas les autres
                    print(f"[DONNEES FR] Avalanche {cle} : {type(e).__name__}")
        sortie = [[m[0], m[1], m[2], m[3], bulletins.get(_nom_cle(m[1]))] for m in massifs]
        if jour and not bulletins:
            return False
        _ecrire("avalanche", {"jour": jour, "massifs": sortie})
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Avalanche : {type(e).__name__}")
        return False


# --- électricité par région (RTE éco2mix temps réel, ODRÉ) --------------------------------------------------------------------------------------------------------------
URL_ECO2MIX = "https://odre.opendatasoft.com/api/explore/v2.1/catalog/datasets/eco2mix-regional-tr/records"
CENTRES_REGIONS = {"11": (48.69, 2.50), "24": (47.55, 1.68), "27": (47.28, 4.80), "28": (49.10, 0.20), "32": (50.05, 2.80), "44": (48.65, 5.90), "52": (47.50, -0.80),
                   "53": (48.20, -2.90), "75": (44.80, 0.20), "76": (43.70, 2.30), "84": (45.40, 4.90), "93": (43.95, 6.00), "94": (42.15, 9.10)}


def convertir_electricite(enregistrements) -> list:
    """Enregistrements ODRÉ (du plus récent au plus ancien) -> dernière valeur complète de chaque région : [code, nom, lat, lon, heure ISO, consommation, nucléaire, éolien, solaire, hydraulique, thermique, bioénergies, échanges] (MW ; échanges < 0 = export)."""
    vus, sortie = set(), []
    for r in enregistrements:
        code = str(r.get("code_insee_region") or "")
        if code in vus or code not in CENTRES_REGIONS:
            continue
        v = [_f(r.get(k)) for k in ("consommation", "nucleaire", "eolien", "solaire", "hydraulique", "thermique", "bioenergies", "ech_physiques")]
        if any(x is None for x in v[:7]):
            continue
        vus.add(code)
        sortie.append([code, str(r.get("libelle_region") or ""), CENTRES_REGIONS[code][0], CENTRES_REGIONS[code][1], r.get("date_heure"), *[int(x) for x in v[:7]], int(v[7] or 0)])
    return sortie


def maj_electricite() -> bool:
    try:
        r = requests.get(URL_ECO2MIX, params={"limit": 100, "order_by": "date_heure desc", "where": "nucleaire is not null and consommation is not null"}, headers=ENTETES, timeout=60)
        r.raise_for_status()
        regions = convertir_electricite(r.json().get("results", []))
        if len(regions) < 10:
            return False
        _ecrire("electricite", regions)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Électricité : {type(e).__name__}")
        return False


# --- sécheresse : restrictions d'eau par département (VigiEau, beta.gouv.fr) ---------------------------------------------------------------------------------------------
URL_VIGIEAU = "https://api.vigieau.beta.gouv.fr/api/departements"
NIVEAUX_EAU = {"vigilance": 1, "alerte": 2, "alerte_renforcee": 3, "crise": 4}


def convertir_secheresse(liste) -> dict:
    """Réponse VigiEau -> {code département: [niveau global, superficielles, souterraines, eau potable]} (0 = aucune restriction, 4 = crise)."""
    n = lambda v: NIVEAUX_EAU.get(v or "", 0)  # noqa: E731
    return {str(d["code"]): [n(d.get("niveauGraviteMax")), n(d.get("niveauGraviteSupMax")), n(d.get("niveauGraviteSouMax")), n(d.get("niveauGraviteAepMax"))] for d in liste if d.get("code")}


def maj_secheresse() -> bool:
    try:
        r = requests.get(URL_VIGIEAU, headers=ENTETES, timeout=60)
        r.raise_for_status()
        niveaux = convertir_secheresse(r.json())
        if len(niveaux) < 90:
            return False
        _ecrire("secheresse", {"maj": datetime.now(timezone.utc).isoformat(timespec="minutes"), "niveaux": niveaux, "depts": _departements()})
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Sécheresse : {type(e).__name__}")
        return False


# --- événements routiers du réseau routier national (Bison Futé / DIR, DATEX II) ---------------------------------------------------------------------------------------------
URL_TRAFIC = "https://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml"
_D2 = "{http://datex2.eu/schema/2/2_0}"
_XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
CATEGORIES_TRAFIC = {   # type DATEX II -> (catégorie, libellé)
    "Accident": ("incident", "Accident"), "AbnormalTraffic": ("incident", "Traffic jam"), "VehicleObstruction": ("incident", "Vehicle obstruction"), "GeneralObstruction": ("incident", "Obstruction"),
    "AnimalPresenceObstruction": ("incident", "Animal on the road"), "EnvironmentalObstruction": ("incident", "Environmental obstruction"), "InfrastructureDamageObstruction": ("incident", "Infrastructure damage"),
    "WeatherRelatedRoadConditions": ("incident", "Weather-related road conditions"), "NonWeatherRelatedRoadConditions": ("incident", "Road conditions"),
    "MaintenanceWorks": ("travaux", "Maintenance works"), "ConstructionWorks": ("travaux", "Construction works"),
    "RoadOrCarriagewayOrLaneManagement": ("restriction", "Road or lane restriction"), "ReroutingManagement": ("restriction", "Diversion"), "SpeedManagement": ("restriction", "Speed restriction"),
}


def convertir_trafic(xml: str, maintenant=None) -> list:
    """DATEX II -> événements EN COURS (début passé, fin non passée) avec position : [catégorie, libellé, lat, lon, texte, gravité, début, fin, route]."""
    import defusedxml.ElementTree as ET
    maintenant = maintenant or datetime.now(timezone.utc)
    sortie = []
    racine = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    for sit in racine.iter(_D2 + "situation"):
        gravite = (sit.findtext(_D2 + "overallSeverity") or "").strip()
        for rec in sit.iter(_D2 + "situationRecord"):
            type_ = (rec.attrib.get(_XSI) or "").split(":")[-1]
            if type_ not in CATEGORIES_TRAFIC:
                continue
            debut, fin = rec.findtext(".//" + _D2 + "overallStartTime"), rec.findtext(".//" + _D2 + "overallEndTime")
            try:
                if debut and datetime.fromisoformat(debut) > maintenant or fin and datetime.fromisoformat(fin) < maintenant:
                    continue
            except ValueError:
                continue
            lat, lon = rec.findtext(".//" + _D2 + "latitude"), rec.findtext(".//" + _D2 + "longitude")
            if not lat or not lon:
                continue
            textes = [" ".join(v.text.split()) for v in rec.iter(_D2 + "value") if v.text and v.text.strip()]
            route = rec.findtext(".//" + _D2 + "roadNumber") or ""
            sortie.append([*CATEGORIES_TRAFIC[type_], round(float(lat), 5), round(float(lon), 5), " · ".join(dict.fromkeys(textes))[:240], gravite, debut, fin, route.strip()])
    return sortie


def maj_trafic() -> bool:
    try:
        r = requests.get(URL_TRAFIC, headers=ENTETES, timeout=90)
        r.raise_for_status()
        ev = convertir_trafic(r.content)
        if not ev:
            return False
        _ecrire("trafic", ev)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Trafic : {type(e).__name__}")
        return False


# --- sites Seveso (Géorisques, installations classées ; le filtre « statutSeveso » de l'API v1 ne fonctionne pas : on balaie les ~140 pages de 1 000 et on garde les sites Seveso ; les substances stockées viennent de l'API v2, jeton gratuit) --------------------------------
URL_ICPE = "https://www.georisques.gouv.fr/api/v1/installations_classees"
URL_ICPE_V2 = "https://www.georisques.gouv.fr/api/v2/installations_classees/"
_seveso = {"fil": None, "essai": 0.0}
NIVEAUX_SEVESO = {"seveso seuil haut": 2, "seveso seuil bas": 1}
SECTEURS_NAF = {   # division de la nomenclature d'activités (NAF) -> secteur, pour dire à quoi sert le site
    "01": "Agriculture", "02": "Sylviculture", "05": "Extraction de charbon", "06": "Extraction de pétrole et de gaz", "07": "Extraction de minerais métalliques", "08": "Autres industries extractives (carrières)",
    "09": "Soutien aux industries extractives", "10": "Industries alimentaires", "11": "Fabrication de boissons", "13": "Textile", "16": "Travail du bois", "17": "Papier et carton", "18": "Imprimerie",
    "19": "Cokéfaction et raffinage du pétrole", "20": "Industrie chimique", "21": "Industrie pharmaceutique", "22": "Caoutchouc et plastiques", "23": "Verre, ciment et autres minéraux non métalliques",
    "24": "Métallurgie", "25": "Fabrication de produits métalliques", "26": "Produits électroniques", "27": "Équipements électriques", "28": "Machines et équipements", "29": "Automobile", "30": "Autres matériels de transport",
    "32": "Autres industries manufacturières", "33": "Réparation et installation de machines", "35": "Production et distribution d'électricité, de gaz et de vapeur", "36": "Captage et distribution d'eau",
    "37": "Collecte des eaux usées", "38": "Collecte et traitement des déchets", "39": "Dépollution", "46": "Commerce de gros", "47": "Commerce de détail", "49": "Transports terrestres et par conduites",
    "50": "Transports par eau", "52": "Entreposage et services auxiliaires des transports", "64": "Services financiers", "68": "Activités immobilières", "84": "Administration publique",
}


def convertir_seveso(enregistrements) -> list:
    """Installations classées -> sites Seveso en exploitation : [nom, commune, lat, lon, niveau (2 = seuil haut, 1 = seuil bas), régime, adresse, secteur, priorité nationale (0/1), directive IED (0/1), nombre d'inspections, date de la dernière inspection, service d'inspection, code AIOT, substances [[rubrique, nature, quantité], ...] (remplies par l'API v2 si un jeton est configuré)]."""
    sortie = []
    for r in enregistrements:
        niveau = NIVEAUX_SEVESO.get(str(r.get("statutSeveso") or "").strip().lower())
        lat, lon = _f(r.get("latitude")), _f(r.get("longitude"))
        if niveau and lat is not None and lon is not None and not str(r.get("etatActivite") or "").lower().startswith(("cessation", "arrêt", "arret")):
            insp = [str(i.get("dateInspection")) for i in (r.get("inspections") or []) if i.get("dateInspection")]
            adresse = " ".join(x for x in (str(r.get("adresse1") or "").strip(), str(r.get("codePostal") or "").strip(), str(r.get("commune") or "").strip()) if x)
            naf = str(r.get("codeNaf") or "").strip()[:2]
            sortie.append([str(r.get("raisonSociale") or "").strip(), str(r.get("commune") or ""), round(lat, 5), round(lon, 5), niveau, str(r.get("regime") or ""), adresse,
                           SECTEURS_NAF.get(naf, ("Code NAF " + naf) if naf else ""), 1 if r.get("prioriteNationale") else 0, 1 if r.get("ied") else 0, len(insp), max(insp) if insp else "", str(r.get("serviceAIOT") or ""), str(r.get("codeAIOT") or ""), []])
    return sortie


def resumer_rubriques(rubriques) -> list:
    """Rubriques ICPE d'un site (API v2) -> substances dangereuses : les rubriques 4xxx (catégories de la directive Seveso) d'abord, sinon les premières ; [numéro, nature, quantité] (6 au plus)."""
    ru = [r for r in (rubriques or []) if r.get("numeroRubrique")]
    ru.sort(key=lambda r: (not str(r["numeroRubrique"]).startswith("4"), str(r["numeroRubrique"])))
    vues, sortie = set(), []
    for r in ru:
        num = str(r["numeroRubrique"])
        if num in vues:
            continue
        vues.add(num)
        q = f'{_f(r.get("quantiteTotale"), 0):g} {r.get("unite") or ""}'.strip() if r.get("quantiteTotale") not in (None, "") else ""
        sortie.append([num, str(r.get("nature") or "").strip()[:110], q])
        if len(sortie) >= 6:
            break
    return sortie


def _ajouter_substances(sites: list, cle: str) -> int:
    """Une requête de détail (API v2, jeton Géorisques) par site, quelques-unes en parallèle ; un site en échec garde une liste vide. Renvoie le nombre de sites renseignés (-1 si le jeton est refusé)."""
    from concurrent.futures import ThreadPoolExecutor
    entetes = {**ENTETES, "Authorization": "Bearer " + cle}

    def un(site):
        if _etat["stop"].is_set() or not site[13]:
            return 0
        for essai in range(2):
            try:
                r = requests.get(URL_ICPE_V2 + site[13], headers=entetes, timeout=40)
                if r.status_code == 401 or r.status_code == 403:
                    return -1
                r.raise_for_status()
                site[14] = resumer_rubriques(r.json().get("rubriques"))
                return 1 if site[14] else 0
            except Exception:  # noqa: BLE001
                time.sleep(2)
        return 0

    with ThreadPoolExecutor(max_workers=4) as pool:
        res = list(pool.map(un, sites))
    return sum(1 for x in res if x == 1) if -1 not in res else -1


def _balayer_seveso() -> None:
    sites, page = [], 1
    while not _etat["stop"].is_set():
        for essai in range(3):
            try:
                r = requests.get(URL_ICPE, params={"page": page, "page_size": 1000}, headers=ENTETES, timeout=90)
                r.raise_for_status()
                d = r.json()
                break
            except Exception:  # noqa: BLE001
                time.sleep(3 * (essai + 1))
        else:
            print("[DONNEES FR] Seveso : balayage abandonné (réseau)")
            return
        sites += convertir_seveso(d.get("data", []))
        if page >= int(d.get("total_pages") or 0):
            break
        page += 1
        time.sleep(0.2)
    else:
        return
    if len(sites) > 100:   # quelques centaines attendues ; moins = réponse tronquée
        from module import gev_cles
        cle = gev_cles.lire("GEORISQUES_API_KEY")
        if cle:   # substances stockées (rubriques ICPE) : API v2, jeton gratuit
            n = _ajouter_substances(sites, cle)
            print("[DONNEES FR] Seveso : jeton Géorisques refusé (401/403)" if n < 0 else f"[DONNEES FR] Seveso : substances renseignées pour {n} sites")
        _ecrire("seveso", sites)


def maj_seveso() -> bool:
    """Lance le balayage en tâche de fond (4 à 6 minutes) pour ne pas retarder les autres jeux ; un essai par heure au plus."""
    if (_seveso["fil"] is None or not _seveso["fil"].is_alive()) and time.time() - _seveso["essai"] > 3600:
        _seveso["essai"] = time.time()
        _seveso["fil"] = threading.Thread(target=_balayer_seveso, daemon=True, name="seveso-fr")
        _seveso["fil"].start()
    return True


# --- qualité des eaux de baignade (ministère de la Santé, jeu « Qualité des sites de baignade », classement par site) ---------------------------------------------------------------------------
URL_BAIGNADE_JEU = "https://www.data.gouv.fr/api/1/datasets/qualite-des-sites-de-baignade-1/"
URL_BAIGNADE_CSV = "https://static.data.gouv.fr/resources/qualite-des-sites-de-baignade-1/20260709-081710/qualite-sites-baignade.csv"   # repli si l'API de data.gouv.fr ne répond pas


def convertir_baignade(texte: str) -> list:
    """CSV (séparateur « ; ») -> [nom, commune, département, lat, lon, 1 = eau de mer / 0 = eau douce, qualité] ; sans coordonnées valides : écarté."""
    sortie = []
    for r in csv.DictReader(texte.splitlines(), delimiter=";"):
        lat, lon = _f(r.get("latitude")), _f(r.get("longitude"))
        if lat is None or lon is None or not (-25 < lat < 52 and -64 < lon < 56):
            continue
        sortie.append([(r.get("nom_site") or "").strip().title(), r.get("libelle_geographique") or "", r.get("libelle_departement") or "", round(lat, 5), round(lon, 5), 1 if r.get("type_eau_norm") == "COTIERE" else 0, r.get("qualite") or ""])
    return sortie


def maj_baignade() -> bool:
    try:
        url = URL_BAIGNADE_CSV
        try:
            meta = requests.get(URL_BAIGNADE_JEU, headers=ENTETES, timeout=30).json()
            url = next((x["url"] for x in meta.get("resources", []) if x.get("format") == "csv"), url)
        except Exception:  # noqa: BLE001 — l'API de data.gouv.fr est parfois indisponible : on garde l'adresse connue
            pass
        r = requests.get(url, headers=ENTETES, timeout=90)
        r.raise_for_status()
        sites = convertir_baignade(r.content.decode("utf-8-sig"))
        if len(sites) < 2000:
            return False
        _ecrire("baignade", sites)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Baignade : {type(e).__name__}")
        return False


# --- parkings : fichier statique (BNLS, Saemes, Indigo, Saint-Étienne, Orléans) + disponibilité en direct (Nantes, Aix-Marseille, Tours, Clermont) ---------------------------------
# Pas de source nationale unique : chaque ville publie dans son format. Le statique est refait chaque semaine (parkings_statique.json), le direct toutes les 5 minutes ; parkings.json = les deux fusionnés.
# Essayés et écartés : OpenStreetMap (API Overpass trop lente et instable pour un téléchargement automatique), Lyon (flux temps réel derrière un compte), Dijon (jeu retiré).
# Colonnes : [nom, adresse, lat, lon, places, gratuit 0/1, places PMR, bornes électriques, hauteur max cm, tarif 1 h, tarif 24 h, exploitant, lien, places libres (None = inconnu), mise à jour ISO, statut]
# statut : None (inconnu) | "ouvert" | "complet" | "ferme" | "abonnes" (ouvert aux seuls abonnés)
URL_BNLS = "https://www.data.gouv.fr/api/1/datasets/r/e32f7675-913b-4e01-b8c8-0a29733e4407"
URL_SAEMES = "https://www.data.gouv.fr/api/1/datasets/r/59044c4a-54fb-4617-b752-532303180d25"
URL_INDIGO = "https://www.data.gouv.fr/api/1/datasets/r/c87a5804-ed47-4ffb-8d96-9ce3b559e699"
URL_SAINT_ETIENNE = "https://extranet.saint-etienne.fr/extrasig/geoserver/wfs?request=getFeature&typeName=vse:Parking_SaintEtienneMetropole&outputformat=application/json&srsName=EPSG:4326"
URL_ORLEANS = "https://data.orleans-metropole.fr/api/explore/v2.1/catalog/datasets/om-mobilite-parcs-stationnement/exports/json"
URL_NANTES = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_parkings-publics-nantes-disponibilites/exports/json"
URL_NANTES_RELAIS = "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/244400404_parcs-relais-nantes-metropole-disponibilites/exports/json"
URL_AIX = "https://data.ampmetropole.fr/api/explore/v2.1/catalog/datasets/disponibilites-des-places-de-parkings/exports/json"
URL_TOURS = "https://data.tours-metropole.fr/api/explore/v2.1/catalog/datasets/etat-des-parkings-en-ouvrage-en-temps-reel-tours-metropole-val-de-loire/exports/json"
URL_CLERMONT = "https://opendata.clermontmetropole.eu/api/explore/v2.1/catalog/datasets/occupation_parcs_stationnement_metropolitains/exports/json"
VALIDITE_DIRECT = 30 * 60   # au-delà (la doc de Nantes dit 15 minutes), les places libres ne sont plus affichées : une valeur périmée serait pire qu'une valeur absente


def _decoder(contenu: bytes) -> str:
    """UTF-8 (avec ou sans BOM) ; à défaut Windows-1252 (le CSV de Saemes n'est pas en UTF-8)."""
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenu.decode("cp1252", errors="replace")


def _int(v) -> int:
    x = _f(v)
    return int(x) if x is not None and x > 0 else 0


def _parking(nom, adresse, lat, lon, places=0, gratuit=0, pmr=0, elec=0, hauteur=0, t1=None, t24=None, exploitant="", url="", libres=None, maj="", statut=None):
    """Une ligne de parking (16 colonnes) ; None sans position valide en France."""
    lat, lon = _f(lat), _f(lon)
    if lat is None or lon is None or not (_FR[0] < lat < _FR[1] and _FR[2] < lon < _FR[3]):
        return None
    return [str(nom or "").strip().title()[:60], str(adresse or "").strip()[:90], round(lat, 5), round(lon, 5), _int(places), 1 if gratuit else 0, _int(pmr), _int(elec), _int(hauteur),
            _f(t1), _f(t24), exploitant, str(url or "").strip()[:200], libres, maj or "", statut]


def _depuis_bnls(lignes, exploitant: str = "") -> list:
    """Enregistrements au schéma de la Base Nationale des Lieux de Stationnement (CSV, GeoJSON de Saint-Étienne, JSON d'Orléans ; clés en minuscules ou non)."""
    sortie = []
    for brut in lignes:
        r = {str(k).lower(): v for k, v in brut.items()}
        p = _parking(r.get("nom"), r.get("adresse"), r.get("ylat"), r.get("xlong"), r.get("nb_places"), str(r.get("gratuit")).strip().lower() in ("1", "true"), r.get("nb_pmr"),
                     r.get("nb_voitures_electriques"), r.get("hauteur_max"), r.get("tarif_1h"), r.get("tarif_24h"), exploitant or str(r.get("nom_gestionnaire") or ""), r.get("url"))
        if p:
            sortie.append(p)
    return sortie


def convertir_parkings_bnls(texte: str, exploitant: str = "") -> list:
    """CSV de la BNLS (séparateur « ; », même schéma pour Saemes) ; StringIO car certains champs contiennent un retour à la ligne entre guillemets."""
    return _depuis_bnls(csv.DictReader(io.StringIO(texte), delimiter=";"), exploitant)


def convertir_parkings_geojson_bnls(doc: dict, exploitant: str = "") -> list:
    return _depuis_bnls((f.get("properties") or {} for f in (doc or {}).get("features", [])), exploitant)


def convertir_parkings_indigo(doc: dict) -> list:
    """JSON Indigo (profil « parking » à la NeTEx ; position en [latitude, longitude], l'inverse de GeoJSON) ; capacité 0 = inconnue."""
    sortie = []
    for p in (doc or {}).get("places", []):
        try:
            lat, lon = (float(x) for x in p["indicativePointLocation"]["coordinates"][:2])
        except (KeyError, TypeError, ValueError):
            continue
        nom = next((n.get("string") for n in p.get("name", []) if n.get("string")), "")
        ligne = _parking(nom, "", lat, lon, (p.get("characteristics") or {}).get("spacesTotal"), exploitant="Indigo")
        if ligne:
            sortie.append(ligne)
    return sortie


def _dispo(libres, places, statut=None):
    """(libres, statut) cohérents : pas de libres sans comptage, « complet » quand il n'en reste aucune."""
    if libres is None:
        return None, statut
    libres = max(0, int(libres))
    return libres, statut or ("ouvert" if libres > 0 else "complet")


def _recent(horodatage, maintenant) -> bool:
    try:
        t = datetime.fromisoformat(str(horodatage).replace("Z", "+00:00").replace(" ", "T"))
        if t.tzinfo is None:
            return True   # « 2026-11-19 09:05:04 » : le fuseau n'est pas indiqué, on garde la valeur plutôt que de la jeter
        return (maintenant - t).total_seconds() < VALIDITE_DIRECT
    except (TypeError, ValueError):
        return False


def convertir_nantes(enregistrements, exploitant: str = "Naolib", maintenant=None) -> list:
    """Parkings publics et parcs-relais de Nantes (Opendatasoft). Statut : 0 comptage hors service, 1 fermé, 2 abonnés seulement, 5 ouvert ; « complet » sous le seuil grp_complet."""
    maintenant = maintenant or datetime.now(timezone.utc)
    sortie = []
    for r in enregistrements or []:
        loc = r.get("location") or {}
        code, libres = r.get("grp_statut"), r.get("grp_disponible")
        statut = {1: "ferme", 2: "abonnes"}.get(code)
        if code in (0, None) or not _recent(r.get("grp_horodatage"), maintenant):
            libres, statut = None, None
        elif code == 5:
            seuil = _f(r.get("grp_complet"), 0) or 0
            libres, statut = _dispo(libres, None, "complet" if libres is not None and libres <= seuil else None)
        else:
            libres = None   # fermé ou abonnés : les places « horaires » ne sont pas à vendre
        p = _parking(r.get("grp_nom") or r.get("nom_complet"), r.get("adresse"), loc.get("lat"), loc.get("lon"), r.get("grp_exploitation"), exploitant=exploitant, libres=libres, maj=r.get("grp_horodatage") or "", statut=statut)
        if p:
            sortie.append(p)
    return sortie


def convertir_aix(enregistrements, maintenant=None) -> list:
    """Métropole Aix-Marseille-Provence : « tempsreel » dit si le comptage est en direct."""
    sortie = []
    for r in enregistrements or []:
        direct = str(r.get("tempsreel")).lower() == "true" and _f(r.get("voitureplacesdisponibles")) is not None
        libres, statut = _dispo(_f(r.get("voitureplacesdisponibles")) if direct else None, None)
        p = _parking(r.get("nom"), f"{r.get('adresse') or ''} {r.get('commune') or ''}".strip(), r.get("latitude"), r.get("longitude"), r.get("voitureplacescapacite"), url=r.get("site"),
                     exploitant=str(r.get("producteur") or ""), libres=libres, maj=(r.get("datemajpy") or "").replace(" ", "T") if direct else "", statut=statut)
        if p:
            sortie.append(p)
    return sortie


def _hauteur_cm(texte) -> int:
    m = re.search(r"(\d+)[,.](\d+)", str(texte or ""))
    return int(m.group(1)) * 100 + int(m.group(2).ljust(2, "0")[:2]) if m else 0


def convertir_tours(enregistrements) -> list:
    sortie = []
    for r in enregistrements or []:
        loc = r.get("geo_point") or {}
        libres, statut = _dispo(_f(r.get("free_spots")), None)
        p = _parking(r.get("libelle_parking"), f"{r.get('adresse') or ''} {r.get('commune') or ''}".strip(), loc.get("lat"), loc.get("lon"), r.get("capacite"),
                     hauteur=_hauteur_cm(r.get("hauteur_max_premier_niveau")), exploitant="Indigo", url=r.get("url_abonnement_"), libres=libres, maj=r.get("horodatage") or "", statut=statut)
        if p:
            sortie.append(p)
    return sortie


def convertir_clermont(enregistrements, maintenant=None) -> list:
    sortie = []
    for r in enregistrements or []:
        valide = str(r.get("etat") or "").lower() == "valide"
        libres, statut = _dispo(_f(r.get("places_libres")) if valide else None, None)
        p = _parking(r.get("nom"), "", r.get("latitude"), r.get("longitude"), r.get("capacite_maximale"), exploitant="Clermont Auvergne Métropole", url=r.get("lien"),
                     libres=libres, maj=r.get("horodatage") or "" if valide else "", statut=statut)
        if p:
            sortie.append(p)
    return sortie


def fusionner_parkings(*listes, metres: float = 60.0) -> list:
    """Concatène les listes dans l'ordre de priorité ; un parking à moins de `metres` d'un parking d'une liste PRÉCÉDENTE est le même (la BNLS reprend déjà Saemes ; le direct l'emporte sur le statique) :
    écarté. Deux parkings voisins d'une même liste sont conservés."""
    cellules, sortie = {}, []
    for liste in listes:
        nouveaux = []
        for p in liste:
            cx, cy = int(p[3] / 0.001), int(p[2] / 0.001)   # cellule de ~100 m : on ne compare qu'avec les 9 voisines
            if any(abs((q[2] - p[2]) * 111_000) < metres and abs((q[3] - p[3]) * 111_000 * 0.68) < metres for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in cellules.get((cx + dx, cy + dy), ())):
                continue
            nouveaux.append(p)
        for p in nouveaux:
            cellules.setdefault((int(p[3] / 0.001), int(p[2] / 0.001)), []).append(p)
            sortie.append(p)
    return sortie


def _json(url: str, **kw):
    r = requests.get(url, headers=ENTETES, timeout=60, **kw)
    r.raise_for_status()
    return r


def _construire_statique() -> list:
    """Télécharge et fusionne les jeux statiques ; liste vide si la BNLS (la base) est tronquée ; un exploitant en panne n'est pas remplacé par du vide si un fichier complet existe déjà."""
    bnls = convertir_parkings_bnls(_decoder(_json(URL_BNLS).content), "BNLS")
    if len(bnls) < 500:
        return []
    autres, manquantes = [], []
    for nom, url, conv in (("Saemes", URL_SAEMES, lambda r: convertir_parkings_bnls(_decoder(r.content), "Saemes")),
                           ("Indigo", URL_INDIGO, lambda r: convertir_parkings_indigo(json.loads(_decoder(r.content)))),
                           ("Saint-Étienne", URL_SAINT_ETIENNE, lambda r: convertir_parkings_geojson_bnls(r.json(), "Saint-Étienne Métropole")),
                           ("Orléans", URL_ORLEANS, lambda r: _depuis_bnls(r.json(), "Orléans Métropole"))):
        try:
            autres.append(conv(_json(url)))
        except Exception as e:  # noqa: BLE001
            manquantes.append(nom)
            print(f"[DONNEES FR] Parkings {nom} : {type(e).__name__}")
    if manquantes and age("parkings_statique") != float("inf"):
        return []
    return fusionner_parkings(bnls, *autres)


def maj_parkings() -> bool:
    try:
        statique = None
        if age("parkings_statique") > 7 * 86400:
            statique = _construire_statique()
            if statique:
                _ecrire("parkings_statique", statique)
        if not statique:
            with open(os.path.join(DOSSIER, "parkings_statique.json"), encoding="utf-8") as f:
                statique = json.load(f)   # le fichier de la semaine (ou, si la reconstruction a échoué, le dernier bon)
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Parkings (statique) : {type(e).__name__}")
        return False
    direct = []
    for nom, url, conv in (("Nantes", URL_NANTES, convertir_nantes), ("Nantes (parcs-relais)", URL_NANTES_RELAIS, convertir_nantes), ("Aix-Marseille", URL_AIX, convertir_aix),
                           ("Tours", URL_TOURS, convertir_tours), ("Clermont-Ferrand", URL_CLERMONT, convertir_clermont)):
        try:
            direct += conv(_json(url).json())
        except Exception as e:  # noqa: BLE001 — une ville en panne : ses parkings restent affichés avec les données statiques
            print(f"[DONNEES FR] Parkings en direct {nom} : {type(e).__name__}")
    try:
        _ecrire("parkings", fusionner_parkings(direct, statique))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[DONNEES FR] Parkings : {type(e).__name__}")
        return False


# nom -> (mise à jour, validité en secondes)
JEUX = {"parkings": (maj_parkings, 300), "baignade": (maj_baignade, 7 * 86400), "seveso": (maj_seveso, 7 * 86400), "electricite": (maj_electricite, 900), "secheresse": (maj_secheresse, 3 * 3600), "trafic": (maj_trafic, 600), "avalanche": (maj_avalanche, 3600), "vigilance": (maj_vigilance, 900), "seismes": (maj_seismes, 600), "crues": (maj_crues, 1200), "air": (maj_air, 7200), "recharge": (maj_recharge, 7 * 86400)}


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
